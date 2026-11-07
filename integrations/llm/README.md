# CHROMA APEX LLM Sampling Engine

A CPU-only numeric logits sampler and minimal autoregressive decoder test engine derived from the CHROMA APEX project. It accelerates *sampling and candidate ordering*, not model matrix multiplications, attention, KV-cache allocation, tensor kernels, or prompt prefill.

This is a reproducible experimental integration, **not** a claim of a world-record inference engine.

## Components

| Directory | Purpose | Validation |
|---|---|---|
| `src/`, `include/` | C++17 native CPU sampler C ABI | Correctness and timings measured |
| `examples/decoder_engine.py` | Working PyTorch decoder with KV cache; optional local Transformers models | Three seeded decoder shapes tested |
| `adapters/llama_cpp_sampler.*` | Optional llama.cpp custom sampler bridge | Compiled only against an ABI-shaped stub; full upstream integration not tested |
| `bench/` | Native same-host microbenchmarks and decoder measurements | CSV and JSON results included |
| `tests/` | Native exactness tests, decoder tests and stub adapter smoke test | Validated locally |

## Build

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j4
ctest --test-dir build --output-on-failure
```

The C++ sampler has no third-party runtime dependencies. The optional decoder runner uses Python 3, NumPy and **CPU PyTorch**. The compiled shared library must be available under `build/libapex_llm.so` (Linux). On other operating systems, supply its path when constructing `ApexSampler`.

## Benchmark

```sh
./build/apex_llm_benchmark > bench/sampler_results.csv
python examples/decoder_engine.py --model dense-small --tokens 96 --rounds 7
python examples/decoder_engine.py --model gqa-medium --tokens 96 --rounds 7
python examples/decoder_engine.py --model gqa-wide --tokens 48 --rounds 7
python tests/test_decoder.py
```

Model configurations are deterministic randomly initialized decoder networks, not pretrained LLMs and not capable of meaningful natural-language responses. They exercise real autoregressive attention/MLP, a growing KV cache, a vocabulary projection, and identical token sampling across three implementations. Tests explicitly compare output token IDs across seeds and reference algorithms.

To benchmark an **actual locally available pretrained model**, install `transformers` and run:

```sh
python examples/decoder_engine.py --hf-model /absolute/path/to/local/hf-model \
  --prompt "Explain stable sorting." --tokens 128 --rounds 7
```

This is a CPU-only Transformers path requiring compatible local weights, tokenizer and model code supported by Transformers. **No Hugging Face pretrained checkpoint was available for testing here.** It is not a GGUF model loader. A GGUF checkpoint requires a matching llama.cpp runtime and the optional adapter, not the Transformers path.

## API

```c
#include "apex_llm.h"
uint32_t token;
apx_llm_stats stats;
int status = apx_llm_sample(logits, vocab_size, 0.8f, 40, 0.95f,
                            0.42, &token, &stats, 0);
```

The `uniform_01` parameter is supplied by the caller's RNG for deterministic comparisons. The last parameter selects algorithm: `0` adaptive APEX, `1` full `std::sort`, `2` `std::partial_sort`, `3` `std::nth_element` followed by `std::sort`. All paths implement the same top-k / temperature / top-p distribution and stable token-ID tie order. The returned index is a **candidate array position**; when caller arrays are not token-ID indexed, map the result to the token ID.

NaNs and negative infinity are masked. Positive infinities form a uniform distribution; signed zeros compare equal. Temperature `0` chooses the maximum logit with lowest token ID. `top_k=0` uses the full vocabulary.

## llama.cpp adapter

`adapters/llama_cpp_sampler.cpp` exports `llama_sampler_init_chroma_apex(top_k, top_p, temperature, seed)`. It can be inserted in a llama.cpp sampling chain **in place of** its top-k/top-p/temperature/distribution segment, after applicable penalties/grammar. Build it only when the original llama.cpp public headers and library are present, with `-DAPX_WITH_LLAMA_CPP=ON` and the appropriate include/library paths. It has not been exercised in a running llama.cpp model. Its RNG stream and sampler processing may differ from upstream; test equivalence and throughput before deploying. Models using GPU-resident sampling must not copy large vocabularies to a CPU sampler solely to use this library.

The adapter is not compatible with every upstream configuration, such as arbitrary typical/DRY/min-p/Mirostat pipelines; it implements only greedy, top-k, temperature and top-p.

## Limits and interpretation

Sorting is a **small portion of decoding** when model compute/memory bandwidth dominates. A CPU sampler is unlikely to improve a fully GPU-resident pipeline because copying the logits to the CPU incurs device synchronization and transfer overhead. The native reference tests compare actual token IDs and stability. All performance numbers are from one unisolated virtualized AMD EPYC CPU and can change substantially by workload.

See [report](ENGINE_REPORT.md) for detailed measurements, alternative optimized baselines and limitations.

## License

MIT, consistent with CHROMA APEX. See [LICENSE](LICENSE). No llama.cpp code or pretrained model weights are bundled.