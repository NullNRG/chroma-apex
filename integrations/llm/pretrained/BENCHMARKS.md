# CHROMA APEX Pretrained-Model Evaluation and CPU Sampler Results

## Verified execution environment

- CPU-only PyTorch; no GPU runtime or cached Hugging Face pretrained checkpoints in this environment.
- The runner attempted to load `roneneldan/TinyStories-1M` with `--local-only`; it correctly returned a dependency error because Transformers/tokenizers are not installed. Model download hosts are not accessible from the execution container.
- **Actual pretrained model runs completed: 0.** Nothing in this report represents end-to-end TinyStories, DistilGPT2, SmolLM2, Qwen, or Llama throughput.
- The test model in `test_pretrained_engine.py` is explicitly a randomly initialized test double, *not pretrained*. Its purpose is verifying cache use, sampled-token equality, and the interface.

## Actual measured CPU sampler microbenchmarks

The following measurements are **per-token selection only**, not model inference. Float32 logits were deterministically synthesized, kept on CPU, and reused during warmup and timed passes. PyTorch used one thread. Each method was run in 5 rotated rounds of 100 calls; per-method median wall time per call is reported in microseconds. The native path includes NumPy/ctypes overhead; the PyTorch path includes its tensor operations and scalar extraction.

| Vocabulary and mode | Native APEX (µs) | Optimized PyTorch (µs) | Adaptive (µs) | Adaptive / PyTorch speedup |
|---|---:|---:|---:|---:|
| 8,192, top-40, p=.95 | 36.20 | 63.18 | **36.58** | 1.73x |
| 50,257, top-40, p=.95 | 307.09 | **149.73** | 153.73 | 0.97x |
| 50,257, full-vocab, p=.95 | **972.50** | 4,279.24 | 975.58 | 4.39x |
| 128,256, top-40, p=.95 | 759.21 | **273.75** | 276.96 | 0.99x |
| 128,256, full-vocab, p=.95 | **2,481.20** | 11,267.79 | 2,539.97 | 4.44x |
| 50,257, greedy top-1 | 51.56 | 49.83 | **47.75** | 1.04x |

See `selector_microbench.json` for peaky/tie distributions, individual parameters and exact tokens. Numbers are from one host, are subject to scheduling and thermal variation and are not portable speed claims. Adaptive is a routing heuristic, not learned or universally optimal.

For `top_k=0` and `top_p=1`, categorical sampling **does not require a sort at all**. The optimized PyTorch path uses a direct softmax + cumulative distribution; treating a full sort as a baseline in that configuration would be misleading.

## Expected influence on actual model tokens/sec

The token-selection fraction f of original decode time limits potential speedup. If the sampler alone improves by factor s, the idealized end-to-end factor is

\[ S = 1 / ((1-f) + f/s). \]

For example, if token selection is 5% of full decode and the sampler becomes four times faster, overall throughput increases by no more than about 3.9%, ignoring measurement noise and side effects. If selection dominates a tiny CPU model, improvement can be larger. A GPU model that transfers logits to CPU can be slower.

## Candidate pretrained checkpoints

| Model | Architecture | Vocabulary | Benchmarked here? | Expected consideration |
|---|---|---:|---|---|
| roneneldan/TinyStories-1M | GPT-Neo | 50,257 | No | Small forward pass; sampler could dominate in full-vocab nucleus mode |
| roneneldan/TinyStories-33M | GPT-Neo | 50,257 | No | Larger forward pass should dilute sampler-only gains |
| distilbert/distilgpt2 | GPT-2 | 50,257 | No | Strong ordinary top-k baseline likely beats native APEX alone |
| HuggingFaceTB/SmolLM2-135M-Instruct | Llama-style GQA | 49,152 | No | Larger forward pass; GPU-to-CPU transfer must be avoided |

These are **testing candidates**, not measured inference winners. Checkpoints and model licensing remain under their publishers' terms. Live model comparisons can be executed on CPU or GPU with local or downloadable checkpoints using `pretrained_engine.py`.

## Validation

- 5 Python integration tests pass, including exact sampling parity for vocabularies up to 50,257, fake decoder KV caching, and the Hugging Face-compatible logits processor API.
- Both `apex` and `torch_topk` matched the exact-reference token sequences on three seeded local fake-decoder runs.
- Adaptive routing behavior is covered by tests. The native sampler is the existing tested C++ implementation under `integrations/llm/src/`.

## Limitations

This environment could not execute a pretrained checkpoint. Hugging Face's public `generate()` is often optimized differently from a manually written autoregressive loop, so full deployed engine performance must be compared separately before advertising acceleration. This integration targets CPU sampling; it is not a GPU-resident CUDA, ROCm, WebGPU or llama.cpp mainline integration.
