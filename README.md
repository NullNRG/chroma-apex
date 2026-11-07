# CHROMA APEX

**Stable sorting for packed numeric keys, complex records, and large JSONL datasets.**

CHROMA APEX is a multi-language sorting toolkit built around a simple separation: calculate the order of records without moving their payloads, then materialize only what the application needs. It provides a C11 numeric sorting core with C++, Python, Go, Rust, and C# interfaces, plus a JavaScript engine for heterogeneous records and a Node.js external-file sorter.

The repository contains source code, executable examples, deterministic tests, benchmarks, an interactive sorting visualization, and a technical report.

| Component | Input | Result | Status |
|---|---|---|---|
| Native C11 | float64, uint64, int64 | Stable uint32 index permutation | Tested |
| C++ | Numeric vectors | Stable index vector | Tested |
| Python / Go | Packed numeric arrays | Stable index permutation | Tested |
| JavaScript APEX XL | Nested objects, compound schemas | Permutation / sorted array | Tested |
| Node.js external JSONL | Newline-delimited JSON objects | Stable sorted file | Tested |
| C# / Rust | Numeric arrays via FFI | Stable index permutation | Adapter source provided; target build not verified |

## Why separate ordering from payloads?

Moving 256-byte, 4-KiB, or larger records during sorting can produce unnecessary memory traffic. CHROMA APEX operates on numeric keys or compact index lists. Existing records stay where they are until the caller applies the result. For costly object keys, APEX XL caches the extracted projections rather than repeatedly traversing nested structures in a comparator.

## Quick start

~~~sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
~~~

C11 and CMake 3.14+ are required for the core. C++17 is required for the benchmark and C++ examples.

### C — stable indices

~~~c
#include "chroma_apex.h"

double weights[] = {3.5, -1.0, 3.5, 2.0};
uint32_t order[4];
apx_stats statistics;
int rc = apx_order_f64(weights, 4, order, &statistics);
// rc == APX_OK; order = {1, 3, 0, 2}
~~~

Pass core/include as an include directory and link the chroma_apex library.

### JavaScript — nested records

~~~js
const { createApexXL } = require('./packages/js/apex_massive');
const records = [
  { id: 10, user: { region: 'US' }, score: 4 },
  { id: 11, user: { region: 'CA' }, score: 9 },
  { id: 12, user: { region: 'CA' }, score: 9 }
];
const schema = [
  { path: 'user.region', type: 'string' },
  { path: 'score', type: 'number', order: 'desc' }
];
const engine = createApexXL();
const ordered = engine.sortedCopy(records, schema);
// IDs: [11, 12, 10], retaining original order on ties
~~~

### Node.js — external JSONL

~~~sh
node packages/js/external_jsonl.js input.jsonl output.jsonl examples/schema.json 25000
~~~

For Python, Go, C#, Rust, C++, composite schemas, and the balance-record metric, see **[Usage examples](docs/EXAMPLES.md)**.

## Guarantees

- Stable ascending numeric ordering for the native core; equal keys retain their original relative order.
- IEEE-754 numeric convention: negative infinity, finite values, positive infinity, then NaN; both zeros compare equal, and all NaNs compare equal.
- The native functions do not modify the input key array; they write a permutation of uint32 indices.
- APEX XL supports mixed schema columns, ascending/descending fields, explicit null placement, and key projection. Custom comparators must define a consistent order.
- External JSONL sorting is stable across spill runs by preserving original line sequence.
- Native invocation size is limited to UINT32_MAX records, and practical size is constrained by available memory.

## Measured performance

Native benchmark: AMD EPYC virtual machine, GCC Release, 100,000 precomputed numeric keys, median of seven runs. Both implementations output stable index permutations; values are milliseconds.

| Pattern | APEX Native | Boost pdqsort with stable index tie-break |
|---|---:|---:|
| Random 64-bit-derived keys | **2.895** | 9.688 |
| Compact keys, many duplicates | **0.850** | 9.982 |
| Mostly ordered | 1.047 | **0.736** |
| Descending | 0.389 | **0.262** |

This is a fixed-width numeric benchmark, not a general-object benchmark. The JS composite-key results have different winners depending on workload. No local head-to-head result exists yet for IPS⁴o, Typhoon, Powersort, driftsort, or glidesort.

[Full measurements](docs/BENCHMARKS.md) · [Comparison catalog](docs/COMPARISONS.md) · [Benchmark protocol](docs/BENCHMARK_PROTOCOL.md)

## Documentation

| Document | Contents |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Data model, dispatch, complexity, memory, stable output |
| [API reference](docs/API.md) | Native ABI, language adapters, JavaScript schema API |
| [Examples](docs/EXAMPLES.md) | Usage in C, C++, Python, Go, C#, Rust, JS and Node |
| [Technical paper](docs/RESEARCH_PAPER.md) | Formal problem statement, correctness and complexity |
| [Comparison catalog](docs/COMPARISONS.md) | Sorting families, competitors, trade-offs and evidence |
| [Benchmarks](docs/BENCHMARKS.md) | Recorded native and JS results, including losses |
| [Benchmark protocol](docs/BENCHMARK_PROTOCOL.md) | Reproducible, workload-equivalent evaluation |
| [Validation](docs/VALIDATION.md) | Test coverage and current validation boundaries |
| [Licensing](docs/LICENSING.md) | MIT license scope, dependency relationships and provenance |

The [interactive sorting demonstration](demo/index.html) is a standalone HTML file.

## License

MIT. See [LICENSE](LICENSE) and [Licensing](docs/LICENSING.md). CHROMA APEX is an implementation and engineering toolkit employing established algorithm families; it does not claim a new general sorting complexity bound.

## LLM token sampling integration

A standalone [APEX LLM CPU sampler](integrations/llm/README.md) adds adaptive top-k, top-p, temperature, and greedy token selection. It provides a C++17 library, a PyTorch autoregressive decoder integration, an optional llama.cpp sampler adapter, correctness tests and [reproducible benchmarks](integrations/llm/ENGINE_REPORT.md). The model tests use untrained decoder configurations; no pretrained GGUF or Hugging Face model is included. The CPU-only measurements do not establish GPU or production-model acceleration.

### Pretrained causal-LM integration

An [APEX next-token selector for Hugging Face causal models](integrations/llm/pretrained/README.md) integrates native sampling into an actual KV-cache decoding loop and offers adaptive dispatch between APEX and device-resident PyTorch. The [CPU selection results](integrations/llm/pretrained/BENCHMARKS.md) are diagnostic synthetic-logit measurements; no pretrained checkpoint was executable on the offline test host.

## Browser pretrained inference lab

The [browser inference lab](integrations/llm/browser/index.html) integrates APEX into real model logits selection using a Transformers.js logits processor. Its Gemma 3 and SmolLM2 presets, APEX/reference/native comparisons, and offline selector benchmarks are documented in [browser inference documentation](integrations/llm/browser/README.md). No pretrained-model speedup is claimed until weights are executed on target hardware.
