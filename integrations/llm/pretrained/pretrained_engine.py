"""Pretrained causal-LM decode runner with a drop-in CHROMA APEX CPU sampler.

This is a real model.forward() -> logits -> sampler -> next token -> KV cache
loop.  Pretrained weights are loaded from Hugging Face or from an existing
local checkpoint; the script never generates or substitutes random model
weights.  Measured results are only emitted after a checkpoint has loaded.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import statistics
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import torch

DEFAULT_MODELS = [
    "roneneldan/TinyStories-1M",
    "roneneldan/TinyStories-33M",
]
SCRIPTDIR = Path(__file__).resolve().parent
DEFAULT_LIBS = [
    SCRIPTDIR.parent / "build" / "libapex_llm.so",
    SCRIPTDIR.parent / "build" / "libapex_llm.dylib",
    SCRIPTDIR.parent / "build" / "apex_llm.dll",
    # also support a standalone pretrained/ directory with its own build
    SCRIPTDIR / "build" / "libapex_llm.so",
    SCRIPTDIR / "build" / "libapex_llm.dylib",
    SCRIPTDIR / "build" / "apex_llm.dll",
]


class Stats(ctypes.Structure):
    _fields_ = [
        ("candidate_count", ctypes.c_uint32),
        ("retained_count", ctypes.c_uint32),
        ("strategy", ctypes.c_uint32),
    ]


class ApexSelector:
    """Select a token with the compiled apx_llm_sample C ABI.

    A CUDA or MPS tensor must first be copied to CPU.  This transfer and its
    implicit synchronization are INCLUDED in end-to-end measured time.
    """
    def __init__(self, library: str | Path | None = None, strategy: int = 0):
        search = [Path(library)] if library else DEFAULT_LIBS
        path = next((p for p in search if p.exists()), None)
        if path is None:
            raise FileNotFoundError(f"APEX native sampler not found: {[str(p) for p in search]}; build integrations/llm with CMake")
        self.library = ctypes.CDLL(str(path.resolve()))
        self.sample_fn = self.library.apx_llm_sample
        self.sample_fn.argtypes = [
            ctypes.POINTER(ctypes.c_float), ctypes.c_uint32, ctypes.c_float,
            ctypes.c_uint32, ctypes.c_float, ctypes.c_double,
            ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(Stats), ctypes.c_int,
        ]
        self.sample_fn.restype = ctypes.c_int
        self.strategy = strategy

    def select(self, logits: torch.Tensor, k: int, p: float, temp: float, u: float) -> int:
        x = np.ascontiguousarray(logits.detach().to(device="cpu", dtype=torch.float32).numpy().ravel())
        if x.size == 0 or x.size >= 2**32:
            raise ValueError("invalid vocabulary size")
        output = ctypes.c_uint32()
        stats = Stats()
        rc = self.sample_fn(
            x.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), x.size,
            temp, k, p, u, ctypes.byref(output), ctypes.byref(stats), self.strategy,
        )
        if rc != 0:
            raise RuntimeError(f"apx_llm_sample failed (status {rc})")
        return output.value


class TorchTopKSelector:
    """Baseline using device-resident torch.topk (no full vocabulary sort).

    Uses the same uniform variate as APEX and float64 weights to limit
    numerical drift, but may differ on exact ties from APEX's token-ID rule.
    The tensor-to-Python scalar synchronization is included in its timing.
    """
    def select(self, logits: torch.Tensor, k: int, p: float, temp: float, u: float) -> int:
        x = logits.detach().to(torch.float32).reshape(-1)
        x = torch.where(torch.isnan(x), -float("inf"), x)
        if not torch.isfinite(x).any() and not torch.isposinf(x).any():
            raise ValueError("all logits masked")
        if temp == 0 or k == 1:
            return int(torch.argmax(x).item())
        if k != 0 and k < x.numel():
            values, indices = torch.topk(x, k, sorted=True)
        else:
            values, indices = torch.sort(x, descending=True, stable=True)
        valid = values > -float("inf")
        values, indices = values[valid], indices[valid]
        if values.numel() == 0:
            raise ValueError("all logits masked")
        if torch.isposinf(values).any():
            indices = indices[torch.isposinf(values)]
            masses = torch.ones(indices.numel(), device=indices.device, dtype=torch.float64)
        else:
            values = values.double()
            masses = torch.exp((values - values[0]) / temp)
        cumul = torch.cumsum(masses, 0)
        keep = int(torch.searchsorted(cumul, cumul[-1] * p, right=False).item()) + 1
        j = int(torch.searchsorted(cumul[:keep], cumul[keep - 1] * u, right=True).item())
        return int(indices[min(j, keep - 1)].item())


class TorchOptimizedSelector:
    """Lean PyTorch baseline; closely mirrors typical top-k/softmax sampling.

    Does not repair exact ties or preserve float64 weighted sampling, so
    token sequences may differ slightly from APEX on tied/near-boundary cases.
    """
    def select(self, logits: torch.Tensor, k: int, p: float, temp: float, u: float) -> int:
        x = logits.detach().reshape(-1).float()
        if temp == 0 or k == 1:
            return int(torch.argmax(x).item())
        # With top_k=0 and top_p=1 there is no truncation: direct categorical
        # sampling avoids an unnecessary full vocabulary ordering.
        if k == 0 and p == 1.0:
            weights = torch.softmax(torch.where(torch.isnan(x),-float('inf'),x), dim=0)
            if torch.isnan(weights).any():
                # +infinity logits require a uniform distribution on +inf IDs.
                positive = torch.isposinf(x)
                if not positive.any():
                    raise ValueError('all logits masked')
                weights = positive.to(torch.float32) / positive.sum()
            cumulative = torch.cumsum(weights, dim=0)
            return min(x.numel()-1, int(torch.searchsorted(cumulative, cumulative[-1]*u, right=True).item()))
        if k and k < x.numel():
            values, indices = torch.topk(x, k, sorted=True)
        else:
            values, indices = torch.sort(x, descending=True)
        if torch.isnan(values).any():
            values = torch.where(torch.isnan(values), -float('inf'), values)
        valid = values > -float('inf')
        if not valid.all():
            values, indices = values[valid], indices[valid]
        if values.numel() == 0:
            raise ValueError('all logits masked')
        if torch.isposinf(values).any():
            good = torch.isposinf(values)
            indices = indices[good]
            probs = torch.ones(indices.numel(),dtype=torch.float32,device=indices.device)
        else:
            probs = torch.softmax(values / temp,dim=0)
        cumulative = torch.cumsum(probs,dim=0)
        keep = min(len(cumulative), int(torch.searchsorted(cumulative,cumulative[-1]*p,right=False).item())+1)
        pos = int(torch.searchsorted(cumulative[:keep],cumulative[keep-1]*u,right=True).item())
        return int(indices[min(pos,keep-1)].item())


class AdaptiveSelector:
    """CPU/GPU-aware initial routing from measured work profiles.

    This is a deterministic policy, not a magic speed claim. It avoids GPU-to-CPU
    copies and falls back to the device-resident optimized selector when a
    small top-k can be selected without a full vocabulary sort.
    """
    def __init__(self, library=None):
        self.torch = TorchOptimizedSelector()
        self.native = ApexSelector(library)
        self.routes = {"apex":0, "torch_optimized":0}

    def route(self, logits: torch.Tensor, k: int, p: float, temp: float) -> str:
        n = logits.numel()
        if logits.device.type != 'cpu':
            return 'torch_optimized'
        if temp == 0 or k == 1:
            return 'torch_optimized'
        # Full-vocabulary sort is expensive in PyTorch; native packed ordering
        # was faster for n >= 50K in the local CPU microbench.
        if k == 0 and p < 1.0 and n >= 8192:
            return 'apex'
        # On small logits (tested at n=8192), calling the native selector
        # costs less than PyTorch's topk + masking + sampling operations.
        if n <= 8192 and (k == 0 or k <= 64):
            return 'apex'
        # Large-vocabulary, small-top-k: skip APEX's extra data pass.
        return 'torch_optimized'

    def select(self, logits: torch.Tensor, k: int, p: float, temp: float, u: float) -> int:
        route=self.route(logits,k,p,temp)
        self.routes[route]+=1
        return (self.native if route=='apex' else self.torch).select(logits,k,p,temp,u)


class TorchExactSelector:
    """Slow, deterministic full-sort reference with stable ID tie-breaking."""
    def select(self, logits: torch.Tensor, k: int, p: float, temp: float, u: float) -> int:
        x = logits.detach().to(dtype=torch.float32, device="cpu").numpy().reshape(-1)
        good = np.nonzero(~np.isnan(x) & (x != -np.inf))[0]
        if len(good) == 0:
            raise ValueError("all logits masked")
        # Maximum tie breaks by lowest token ID.
        if temp == 0 or k == 1:
            return int(good[np.argmax(x[good])])
        # Stable lexicographic ordering on key (-logit, token ID).
        ix = good[np.lexsort((good, -x[good].astype(np.float64)))]
        if k > 0:
            ix = ix[:k]
        vals = x[ix]
        if np.isposinf(vals).any():
            ix = ix[np.isposinf(vals)]
            mass = np.ones(len(ix), dtype=np.float64)
        else:
            z = vals.astype(np.float64)
            mass = np.exp((z - z[0]) / temp)
        cumulative = np.cumsum(mass)
        keep = int(np.searchsorted(cumulative, cumulative[-1] * p, side="left")) + 1
        j = int(np.searchsorted(cumulative[:keep], cumulative[keep - 1] * u, side="right"))
        return int(ix[min(j, keep - 1)])


SELECTOR_NAMES = ("adaptive", "apex", "torch_topk", "torch_optimized", "torch_exact")


def get_selector(which: str, lib: str | Path | None = None):
    return {
        "apex": lambda: ApexSelector(lib),
        "adaptive": lambda: AdaptiveSelector(lib),
        "torch_topk": TorchTopKSelector,
        "torch_optimized": TorchOptimizedSelector,
        "torch_exact": TorchExactSelector,
    }[which]()


def sync_device(device: torch.device):
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    elif device.type == "mps":
        torch.mps.synchronize()


@dataclass
class Trace:
    ids: list[int]
    # Measured seconds, excludes model load and tokenizer load.
    prefill_s: float
    forward_s: float
    selection_s: float
    decode_s: float
    total_s: float


def decode_trace(model: Any, token_ids: torch.Tensor, selector: Any, *,
                 max_new_tokens: int = 24, top_k: int = 40, top_p: float = 0.95,
                 temperature: float = 0.8, seed: int = 0,
                 stop_eos: bool = False, eos_token_id: int | None = None) -> Trace:
    """A real autoregressive model-forward loop, works with HF causal LMs.

    One model forward is performed for prefill; after each selected token, the
    next forward is run with only that token and previous past_key_values.
    The model is never called with full history after prefill.
    """
    if token_ids.ndim != 2 or token_ids.shape[0] != 1 or token_ids.shape[1] == 0:
        raise ValueError("token_ids must be a nonempty [1, sequence] tensor")
    if max_new_tokens < 1 or top_k < 0 or not 0 < top_p <= 1 or temperature < 0:
        raise ValueError("invalid generation settings")
    if model.training:
        raise ValueError("model must be in eval() mode")
    device = token_ids.device
    rng = np.random.default_rng(seed)
    generated = []
    attention_mask = torch.ones_like(token_ids, dtype=torch.long)
    prefill_s = forward_s = select_s = 0.0
    sync_device(device)
    begin = time.perf_counter()
    with torch.inference_mode():
        sync_device(device)
        t0 = time.perf_counter()
        output = model(input_ids=token_ids, attention_mask=attention_mask, use_cache=True)
        sync_device(device)
        prefill_s = time.perf_counter() - t0
        past = output.past_key_values
        logits = output.logits[0, -1, :]
        for j in range(max_new_tokens):
            u = float(rng.random())
            sync_device(device)
            t0 = time.perf_counter()
            next_id = selector.select(logits, top_k, top_p, temperature, u)
            sync_device(device)
            select_s += time.perf_counter() - t0
            generated.append(int(next_id))
            if j + 1 == max_new_tokens or (stop_eos and eos_token_id is not None and next_id == eos_token_id):
                break
            next_token = torch.tensor([[next_id]], device=device, dtype=torch.long)
            attention_mask = torch.cat((attention_mask, torch.ones_like(next_token)), dim=-1)
            sync_device(device)
            t0 = time.perf_counter()
            output = model(input_ids=next_token, attention_mask=attention_mask,
                           past_key_values=past, use_cache=True)
            sync_device(device)
            forward_s += time.perf_counter() - t0
            past = output.past_key_values
            logits = output.logits[0, -1, :]
    sync_device(device)
    total = time.perf_counter() - begin
    return Trace(generated, prefill_s, forward_s, select_s, forward_s+select_s, total)


def load_pretrained(name: str, device: str = "auto", local_only: bool = False,
                    torch_dtype: str = "auto"):
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:
        raise RuntimeError("Install transformers and tokenizers to load actual pretrained models") from e
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    target = torch.device(device)
    tokenizer = AutoTokenizer.from_pretrained(name, local_files_only=local_only, trust_remote_code=False)
    kwargs = {"local_files_only": local_only, "trust_remote_code": False}
    if torch_dtype != "auto":
        kwargs["dtype"] = getattr(torch, torch_dtype)
    model = AutoModelForCausalLM.from_pretrained(name, **kwargs).eval().to(target)
    return model, tokenizer, target


def benchmark_pretrained(name: str, *, device="auto", local_only=False,
                         prompt="Once upon a time, a little robot", tokens=24,
                         warmups=1, repeats=3, seed=43, k=40, p=.95, temp=.8,
                         lib=None, selectors=("adaptive", "apex", "torch_optimized", "torch_exact"),
                         threads=4):
    torch.set_num_threads(threads)
    model, tokenizer, d = load_pretrained(name, device, local_only)
    inputs = tokenizer(prompt, return_tensors="pt").input_ids.to(d)
    samplers = {s: get_selector(s, lib) for s in selectors}
    measured = {s: [] for s in selectors}
    # Warmups should not be included in speed measurements.
    for method in selectors:
        for _ in range(warmups):
            decode_trace(model, inputs, samplers[method], max_new_tokens=min(tokens, 8),
                         top_k=k, top_p=p, temperature=temp, seed=seed)
    for repeat in range(repeats):
        # Rotated execution order reduces warmup / thermal / scheduling bias.
        rotated = selectors[repeat % len(selectors):] + selectors[:repeat % len(selectors)]
        for method in rotated:
            trace = decode_trace(model, inputs, samplers[method], max_new_tokens=tokens,
                                 top_k=k, top_p=p, temperature=temp, seed=seed+repeat)
            measured[method].append(trace)
    cases = {}
    for method, traces in measured.items():
        cases[method] = {
            "median_generated_tokens_per_second_excluding_prefill": round(statistics.median(len(t.ids)/t.decode_s for t in traces),3),
            "median_sampler_microseconds_per_token": round(statistics.median(t.selection_s/len(t.ids)*1e6 for t in traces),3),
            "median_forward_microseconds_per_token_excluding_prefill": round(statistics.median(t.forward_s/max(1,len(t.ids)-1)*1e6 for t in traces),3),
            "median_end_to_end_seconds_including_prefill": round(statistics.median(t.total_s for t in traces),6),
            "generated_token_ids_first_round": traces[0].ids,
            "decoded_sample_first_round": tokenizer.decode(traces[0].ids, skip_special_tokens=True)[:300],
        }
    parity = {}
    if "torch_exact" in measured:
        for method in selectors:
            if method != "torch_exact":
                parity[method] = [
                    a.ids == b.ids for a,b in zip(measured[method], measured["torch_exact"])
                ]
    return {
        "checkpoint": name, "pretrained_weights_loaded": True,
        "device":str(d), "dtype":str(next(model.parameters()).dtype),
        "model_class":model.__class__.__name__, "parameters": sum(x.numel() for x in model.parameters()),
        "prompt":prompt, "prompt_token_count":inputs.shape[1],
        "generated_tokens_requested":tokens, "seed":seed,"warmups":warmups,
        "repeats":repeats,"threads":threads,
        "sampling":{"top_k":k,"top_p":p,"temperature":temp},
        "backend_results":cases,"exact_reference_sequence_match_per_round":parity,
        "adaptive_dispatch_counts":getattr(samplers.get("adaptive"),"routes",{}),
        "notes":["CPU APEX incurs device-to-host synchronization on GPU.",
                 "Apex native and torch reference share uniform samples, not PyTorch multinomial RNG.",
                 "Timings exclude model and tokenizer loading; include per-step sampling data movement."]
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--local-only", action="store_true", help="Require already-cached weights; never download")
    parser.add_argument("--prompt", default="Once upon a time, a little robot")
    parser.add_argument("--tokens", type=int, default=24)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=40)
    parser.add_argument("--top-p", type=float, default=.95)
    parser.add_argument("--temperature", type=float, default=.8)
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--lib", default=None)
    parser.add_argument("--output", default="pretrained_results.json")
    args=parser.parse_args(argv)
    reports=[]; failures={}
    for name in args.models:
        print(f"Benchmarking pretrained checkpoint: {name}", flush=True)
        try:
            report=benchmark_pretrained(name,device=args.device,local_only=args.local_only,
                                        prompt=args.prompt,tokens=args.tokens,
                                        repeats=args.repeats,warmups=args.warmups,
                                        seed=args.seed,k=args.top_k,p=args.top_p,
                                        temp=args.temperature,lib=args.lib,
                                        threads=args.threads)
            reports.append(report)
            for method, value in report["backend_results"].items():
                print(f"  {method}: {value['median_generated_tokens_per_second_excluding_prefill']} tok/s")
        except Exception as exc:
            print(f"  FAILED: {type(exc).__name__}: {exc}",file=sys.stderr)
            failures[name]=f"{type(exc).__name__}: {exc}"
    payload={"results":reports,"failures":failures,"pretrained_model_count_tested":len(reports)}
    Path(args.output).write_text(json.dumps(payload,indent=2)+"\n")
    print(f"Wrote {args.output}")
    return 0 if reports else 2


if __name__=="__main__":
    raise SystemExit(main())
