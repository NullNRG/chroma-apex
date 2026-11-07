# CHROMA APEX LLM: CPU Sampler Integration Study

**Scope.** This report evaluates the overhead of choosing the next token in a CPU autoregressive decoder. It does not establish improvements to neural-network computation, model accuracy, weight loading, attention, or GPU inference.

## Design

The sampler takes contiguous float32 logits, optionally limits to the most probable k tokens, computes a temperature-scaled softmax, optionally truncates to a cumulative top-p mass, and draws using a caller-supplied uniform random number. Equal logits are ordered by token index to make ties reproducible. The adaptive algorithm chooses from a linear greedy pass, bounded heap, full stable 32-bit-key radix order, histogram-guided prefix selection, and the standard library's partial/nth ordering for smaller populations.

The native full-vocabulary path is a specialized **established radix technique**, not a novel mathematical sorting family. The adapter follows the general architecture of CHROMA APEX but is not a proof of new algorithmic originality.

## End-to-end token generation

The benchmark runs deterministic randomly initialized PyTorch causal decoders with a persistent growing KV cache, real attention, MLPs and vocabulary logits. The four samplers are APEX adaptive native, a fast direct PyTorch `torch.topk`/softmax path, a tie-normalizing double-precision PyTorch path, and a C++ full stable comparison-sort reference. Results are rotated by method, warmed, and measured for seven rounds. **These are untrained networks and do not measure pretrained Qwen, Llama or Gemma quality or hardware throughput.**

| Decoder | Generated tokens | APEX tokens/s | Fast Torch tokens/s | Tie-normalizing Torch tokens/s | C++ fullsort tokens/s | APEX / fast Torch |
|---|---:|---:|---:|---:|---:|
| Dense, 8K vocabulary | 96 | 998.3 | 970.6 | 808.2 | 706.0 | 1.029× |
| GQA, 16K vocabulary | 96 | 255.3 | 257.9 | 238.5 | 197.7 | 0.990× |
| GQA, 32K vocabulary | 48 | 125.1 | 124.9 | 110.6 | 105.5 | 1.002× |




The numbers above describe **total autoregressive decode time including the neural model**, not sorting-only kernels. The fast PyTorch baseline is the more relevant comparator; gains against the slower tie-normalizing reference must not be presented as general PyTorch speedups. On the 16K model the fast PyTorch sampler is slightly faster, and the 32K result is effectively a tie. All three methods generated exactly the same token IDs in every tested seed.

## Native isolated sampling benchmarks

Compiled C++17 -O3 native sampler vs optimized `std::partial_sort` and `std::nth_element+sort` as well as full `std::sort`; identical logits, top-k/top-p/temperature and no model computation. Microseconds/call; lower is better. The “best standard” value is the minimum among three independently timed standard-library approaches.

| Vocabulary | top-k | top-p | APEX μs | Best standard μs | Standard/APEX |
|---:|---:|---:|---:|---:|---:|
| 8,192 | 1 | 1.00 | 7.1 | 7.0 | 0.99× |
| 8,192 | 40 | 1.00 | 25.2 | 24.4 | 0.97× |
| 8,192 | 1024 | 1.00 | 37.8 | 38.9 | 1.03× |
| 8,192 | 0 | 0.95 | 110.7 | 439.2 | 3.97× |
| 32,768 | 1 | 1.00 | 28.0 | 27.5 | 0.98× |
| 32,768 | 40 | 1.00 | 159.1 | 290.8 | 1.83× |
| 32,768 | 1024 | 1.00 | 321.1 | 470.6 | 1.47× |
| 32,768 | 0 | 0.95 | 731.5 | 2203.5 | 3.01× |
| 128,000 | 1 | 1.00 | 120.2 | 108.1 | 0.90× |
| 128,000 | 40 | 1.00 | 756.7 | 1321.9 | 1.75× |
| 128,000 | 1024 | 1.00 | 1323.7 | 1548.0 | 1.17× |
| 128,000 | 0 | 0.95 | 2785.5 | 9355.3 | 3.36× |

These tests represent independent CPU sampling calls with warm-up and five timing batches. At 8K vocabulary and top-k=40, the best standard implementation can be slightly faster. At large vocabularies and full ordering, radix ordering generally wins in this implementation. Measurements include allocations, but not model execution or host/GPU transfers.

## Correctness

The native suite tests 8 vocabulary sizes, eight distributions including masked/NaN and massive duplicate ties, multiple top-k and top-p settings, five deterministic uniform draws and four temperatures. All output tokens and retained candidate counts matched the full-sort reference; the test also compares against partial_sort and nth_element backends. Each of three decoder configurations generated identical token streams across seven seeds with APEX, both Torch samplers, and the C++ reference.

The optional llama.cpp adapter passed an isolated ABI-shaped C++ smoke test, but **has not been compiled against real upstream llama.cpp headers nor tested with a GGUF checkpoint**.

## Engineering recommendations

1. **On a CPU inference engine**, replace an expensive full token sort only when sampling time is material; use top-k selection for k≪vocabulary instead of ordering every logit. Measure total tokens/sec, not sampler microseconds alone.
2. **On a GPU inference engine**, keep sampling on the device. Transferring 128K logits to a CPU and synchronizing each generated token can overwhelm any CPU sorting savings.
3. **When temperature=0**, use a linear argmax, not a full sort. For top-k small, a bounded selection pass is often sufficient; for large candidate sets, numeric radix can help.
4. The bottlenecks for large pretrained models are typically matmul/attention throughput, quantized weight loading, KV-cache memory, batching and speculative decoding. Sorting alone cannot overcome these costs.
5. Before a claim of improved performance on a real model, reproduce a same-device paired benchmark with real weights, identical prompts, context length, quantization, output token sequence or equivalent sampling distribution, and warm-up.

## Reproducibility

- Host: Linux x86_64 virtual machine, 5 vCPUs (AMD EPYC 9V74), ~6 GiB RAM, **no GPU**.
- Software: GCC/C++17 release build, Python/PyTorch CPU, NumPy.
- Command: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4 && ctest --test-dir build --output-on-failure`.
- Files: `bench/sampler_results.csv`, `bench/dense_results.json`, `bench/gqa_results.json`, `bench/gqa_wide_results.json`.
- No pretrained weights available; external downloads blocked in this execution environment.
- This single-machine benchmark does not determine whether the approach speeds up Qwen, Gemma, Llama, vLLM, or llama.cpp in production.