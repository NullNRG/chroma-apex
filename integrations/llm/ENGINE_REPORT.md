# CHROMA APEX LLM: CPU Sampler Integration Study

**Scope.** This report evaluates the overhead of choosing the next token in a CPU autoregressive decoder. It does not establish improvements to neural-network computation, model accuracy, weight loading, attention, or GPU inference.

## Design

The sampler takes contiguous float32 logits, optionally limits to the most probable k tokens, computes a temperature-scaled softmax, optionally truncates to a cumulative top-p mass, and draws using a caller-supplied uniform random number. Equal logits are ordered by token index to make ties reproducible. The adaptive algorithm chooses from a linear greedy pass, bounded heap, full stable 32-bit-key radix order, histogram-guided prefix selection, and the standard library's partial/nth ordering for smaller populations.

The native full-vocabulary path is a specialized **established radix technique**, not a novel mathematical sorting family. The adapter follows the general architecture of CHROMA APEX but is not a proof of new algorithmic originality.

## End-to-end token generation

The benchmark runs deterministic randomly initialized PyTorch causal decoders with a persistent growing KV cache, real attention, MLPs and vocabulary logits. The four samplers are APEX adaptive native, a fast direct PyTorch `torch.topk`/softmax path, a tie-normalizing double-precision PyTorch path, and a C++ full stable comparison-sort reference. Results are rotated by method, warmed, and measured for seven rounds. **These are untrained networks and do not measure pretrained Qwen, Llama or Gemma quality or hardware throughput.**

| Decoder | Generated tokens | APEX tokens/s | Fast Torch tokens/s | Tie-normalizing Torch tokens/s | C++ fullsort tokens/s | APEX / fast Torch |
|---|---:|---:|---:|---:|---:|---:|
| Dense, 8K vocabulary | 96 | 853.8 | 845.7 | 699.6 | 568.3 | 1.009× |
| GQA, 16K vocabulary | 96 | 262.9 | 250.6 | 229.1 | 211.9 | 1.049× |
| GQA, 32K vocabulary | 48 | 128.6 | 130.1 | 118.1 | 103.8 | 0.988× |




The numbers above describe **total autoregressive decode time including the neural model**, not sorting-only kernels. The fast PyTorch baseline is the more relevant comparator; gains against the slower tie-normalizing reference must not be presented as general PyTorch speedups. On these untrained models, small gains and losses vary across repeated executions; the result is essentially near-parity against the faster PyTorch path. All four methods generated exactly the same token IDs in every tested seed.

## Native isolated sampling benchmarks

Compiled C++17 -O3 native sampler vs optimized `std::partial_sort` and `std::nth_element+sort` as well as full `std::sort`; identical logits, top-k/top-p/temperature and no model computation. Microseconds/call; lower is better. The “best standard” value is the minimum among three independently timed standard-library approaches.

| Vocabulary | top-k | top-p | APEX μs | Best standard μs | Standard/APEX |
|---:|---:|---:|---:|---:|---:|
| 8,192 | 1 | 1.00 | 7.0 | 6.9 | 0.99× |
| 8,192 | 40 | 1.00 | 22.9 | 24.3 | 1.06× |
| 8,192 | 1024 | 1.00 | 37.5 | 38.2 | 1.02× |
| 8,192 | 0 | 0.95 | 119.5 | 392.0 | 3.28× |
| 32,768 | 1 | 1.00 | 27.8 | 27.6 | 0.99× |
| 32,768 | 40 | 1.00 | 170.8 | 219.8 | 1.29× |
| 32,768 | 1024 | 1.00 | 308.6 | 470.3 | 1.52× |
| 32,768 | 0 | 0.95 | 672.7 | 2271.9 | 3.38× |
| 128,000 | 1 | 1.00 | 120.4 | 107.7 | 0.89× |
| 128,000 | 40 | 1.00 | 811.2 | 1598.6 | 1.97× |
| 128,000 | 1024 | 1.00 | 1461.3 | 1749.7 | 1.20× |
| 128,000 | 0 | 0.95 | 3089.0 | 9805.3 | 3.17× |

These tests represent independent CPU sampling calls with warm-up and five timing batches. At 8K vocabulary and top-k=40, the best standard implementation can be slightly faster. At large vocabularies and full ordering, radix ordering generally wins in this implementation. Measurements include allocations, but not model execution or host/GPU transfers.

## Correctness

The full native suite verified 47,160 configurations and tests 8 vocabulary sizes, eight distributions including masked/NaN and massive duplicate ties, multiple top-k and top-p settings, five deterministic uniform draws and four temperatures. All output tokens and retained candidate counts matched the full-sort reference; the test also compares against partial_sort and nth_element backends. Each of three decoder configurations with diverse generated tokens produced identical token streams across seven seeds with APEX, both Torch samplers, and the C++ reference.

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
