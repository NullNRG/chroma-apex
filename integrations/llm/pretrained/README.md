# CHROMA APEX — Pretrained Language Model Integration

**Status:** executable Hugging Face causal-LM integration; local model-forward and sampler tests passed. Pretrained checkpoint benchmarking is **not yet performed on the current runner** because pretrained checkpoints are not cached and the runner has no network access. No speedup for a named pretrained model is asserted.

The native sampler and PyTorch baseline are run **inside a real autoregressive forward loop**, with an initial prompt prefill followed by one new token per KV-cache update. The backend selects a token directly from each model's actual logits; no synthetic distributions are substituted when running a pretrained checkpoint. A separate `model.generate()` logits-processor adapter is also provided for compatibility.

## Files

- `pretrained_engine.py`: loads Hugging Face checkpoints, performs cached generation, alternates APEX and PyTorch backends, and records full end-to-end generated tokens/sec and sampler overhead.
- `hf_generate_adapter.py`: integration into Transformers' public `generate()` logits-processor interface (higher overhead; compatibility implementation).
- `bench_selectors.py`: reproducible **synthetic-logit** CPU microbenchmark at realistic vocabulary sizes; not a pretrained-model benchmark.
- `test_pretrained_engine.py`: deterministic sampler correctness, KV-cache forward pattern, and interface tests.
- `selector_microbench.json`: raw measured diagnostic results from the current CPU environment.
- `BENCHMARKS.md`: methodology, wins, losses, and strict limitations.

The existing native library is in the parent `integrations/llm` directory and compiled by CMake.

## Setup

Python 3.10+, a supported PyTorch version, `transformers`, `tokenizers`, `numpy`, and a C++17 compiler with CMake are required.

From the root of `chroma-apex`:

```bash
python3 -m pip install 'torch>=2.2' 'transformers>=4.44' numpy tokenizers
cmake -S integrations/llm -B integrations/llm/build -DCMAKE_BUILD_TYPE=Release
cmake --build integrations/llm/build -j
python3 -m unittest discover -s integrations/llm/pretrained -p 'test_*.py'
```

Run against **pretrained weights** (downloaded by Transformers if not cached):

```bash
python3 integrations/llm/pretrained/pretrained_engine.py \
  --models roneneldan/TinyStories-1M roneneldan/TinyStories-33M \
  --tokens 32 --repeats 5 --warmups 2 --top-k 40 --top-p .95 \
  --output pretrained_topk_results.json
```

Compare true full-vocabulary nucleus sampling:

```bash
python3 integrations/llm/pretrained/pretrained_engine.py \
  --models distilbert/distilgpt2 HuggingFaceTB/SmolLM2-135M-Instruct \
  --tokens 32 --repeats 5 --warmups 2 --top-k 0 --top-p .95 \
  --output pretrained_nucleus_results.json
```

For an existing local Transformers checkpoint, pass its directory path and `--local-only`. CPU is the primary target; on GPU APEX would require synchronous logits transfer to host memory, so the adaptive policy chooses device-resident PyTorch by default.

## Backends

| Backend | Description |
|---|---|
| `adaptive` | Uses fixed CPU/device routing derived from local timing experiments; avoids large-vocabulary small-top-k in APEX |
| `apex` | Always calls the CHROMA C++ native selector, including CPU transfer for GPU tensors |
| `torch_optimized` | Device-resident PyTorch top-k / softmax / cumulative selection; no expensive stable tie-normalization |
| `torch_exact` | Explicit full-sort stable-reference sampler with float64 weights |

The native sampler's tie behavior is deterministic (lowest token ID first). PyTorch's optimized top-k does not guarantee identical tie ordering, and float32 vs float64 probabilities can give different token choices at distribution boundaries; `exact_reference_sequence_match_per_round` is recorded rather than asserted for every backend.

## Metrics

- Median generated tokens/sec excludes prompt prefill but includes selection and all forward calls after prefill.
- Median sampler microseconds/token **includes** any GPU-to-CPU logits transfer and tensor synchronization.
- Median forward microseconds/token excludes prompt prefill; prefill time is included separately in `median_end_to_end_seconds_including_prefill`.
- Full model loading, tokenizer download, compilation, and process startup are excluded from timed generation.
- Models and source versions should be pinned before using the results for comparative performance claims.

## Integration boundary

APEX accelerates selection from **already-produced logits**; it does not accelerate matrix multiplication, attention, quantization, KV cache storage, prefill or speculative execution. Heavy pretrained models may see negligible benefit even if their sampler is faster.

The `hf_generate_adapter` can force a chosen token through `generate()` by masking all other logits. It makes `generate()` use the APEX result but incurs a full-vocabulary mask and a subsequent built-in argmax; use `pretrained_engine` to evaluate the lower-overhead direct next-token path.

The package contains no model weights. Model authors' licenses apply to all downloaded checkpoints.
