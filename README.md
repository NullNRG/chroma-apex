# CHROMA APEX — Adaptive Stable Sorting Toolkit

> **Research preview · v0.1.0** — an open, reproducible, multi-language toolkit for sorting numeric keys and heterogeneous records. Not a verified world-record sorter, and not a newly invented asymptotic sorting class.

CHROMA APEX is intentionally split into two layers:

1. **APEX Native**: packed C11 stable ordering for IEEE-754 `float64`, `uint64`, and `int64` keys. Returns a **permutation of indices**, allowing large objects/payloads to remain stationary. Bounded-counting, bytewise radix, and monotonic fast paths are dispatched based on data characteristics. No external runtime dependency.
2. **APEX XL JavaScript**: schema-driven stable sorting of nested objects (strings, dates, BigInts, token arrays, byte arrays, tuples, nulls, user projections), with an optional disk-backed JSONL tool for datasets larger than memory. Only numeric scalar data uses the native ABI; schema-driven object records use the JS engine.

The library is intended as a **competitive, configurable toolkit**, not a claim that any one strategy wins every workload. Known techniques are explicitly credited in `docs/RESEARCH_PAPER.md` and no third-party sorting implementation is bundled into the core.

## Performance snapshot

Local AMD EPYC 9V74 Linux / Clang-or-GCC Release C++ benchmark; cached numeric keys, stable index order, median of seven repetitions, sorted output verified after warm-up. Time in milliseconds; results vary with CPU and workload.

| Dataset | APEX Native | Boost pdqsort + stable tie key | Relative |
|---|---:|---:|---:|
| 100k random64 | 2.895 | 9.688 | 3.35× faster |
| 100k compact keys | 0.850 | 9.982 | 11.74× faster |
| 100k mostly ordered | 1.047 | **0.736** | 1.42× slower |
| 100k reversed | 0.389 | **0.262** | 1.49× slower |

**Caveat:** key extraction, payload copying, parsing, disk I/O, and parallel sorting are not in these native measurements. Comparison-sorting and radix-based approaches have different applicability; the latter relies on fixed-width numeric keys and additional scratch memory. Earlier object and streaming benchmarks belong to the previous APEX XL release and are *not* a substitute for comparative evaluation of this C core.

Full raw timings: [`bench/local_baseline.csv`](bench/local_baseline.csv). Details and competitor status: [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md).

## Get started

### Compile and test locally (no GitHub Actions)

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
python3 -m unittest discover -s packages/python -p 'test_*.py'
(cd packages/go && go test ./...)
node packages/js/test.js
./build/apex_benchmark 7
```

Dependencies: C11/C++17 compiler, CMake 3.14+. Python 3.10+, Node 18+, and Go 1.20+ only for their respective binding/tests. No downloads, package installation, network calls, or hosted runners required. Boost pdqsort is benchmarked **only if** already available in compiler include paths.

### C

```c
#include "chroma_apex.h"
double weights[] = {3.5, -1, 3.5, 2};
uint32_t indices[4];
apx_stats stats;
int code = apx_order_f64(weights, 4, indices, &stats);
/* indices: [1, 3, 0, 2], stable among equal weights */
```

### C++

```cpp
#include "apex.hpp"
std::vector<double> weights = {2.5, -1, 2.5};
auto indices = chroma_apex::order(weights); // [1,0,2]
```

Compile with the include paths `core/include` and `packages/cpp`, linking `chroma_apex`.

### JavaScript / TypeScript

```js
const { createApexXL } = require('./packages/js/apex_massive');
const sorter = createApexXL();
const records = [
  { id: 0, user: {country:'US'}, score: 6 },
  { id: 1, user: {country:'CA'}, score: 8 }
];
const schema = [
  { path:'user.country', type:'string' },
  { path:'score', type:'number', order:'desc' }
];
const sorted = sorter.sortedCopy(records, schema);
```

The UMD module also attaches `window.ChromaApexXL` in a classic `<script>` tag. See [`packages/js`](packages/js) for more.

### Python

```python
from packages.python.apex_sort import Apex
sorter = Apex() # loads build/libchroma_apex.so or platform equivalent
indices = sorter.order_float64([3.5, -1, 3.5, 2])
records = sorter.sorted_records_by_float64(records, lambda r: r['numeric_key'])
```

### Go / C# / Rust

Bindings and examples: [`packages/go`](packages/go), [`packages/csharp`](packages/csharp), [`packages/rust`](packages/rust). Go and Python are tested locally. **C# and Rust are provided as FFI adapters but not compiled in this environment**; review/build in their target toolchains before deployment.

### Massive JSONL files (Node.js)

```sh
node packages/js/external_jsonl.js input.jsonl output.jsonl examples/schema.json 25000
```

Stable by original line sequence, disk spill and multiway merge, and output is atomically renamed when possible. File size can exceed RAM, but individual JSONL records must fit in memory and the maximum resident memory depends on `chunkRecords`, record size and merge fan-in. The streaming tool is Node-only and not distributed as a browser sorter.

### Visual race

Open [`demo/index.html`](demo/index.html). The standalone demo embeds its own HTML, CSS, JS and any browser kernels, and does not require a server.

## Data types and guarantees

- **C ABI**: exact IEEE-754 `double` with `-∞ < finite < +∞ < NaN`, signed zeros tied, NaNs tied, original order preserved; signed and unsigned 64-bit integer keys. Numeric input is never modified.
- **JS**: stable compound schema keys (nulls-first/last, ascending/descending, nested paths, dates, strings, BigInts, arrays, bytes, custom comparator/projection). String comparison is code-unit order, **not locale collation**. User-supplied custom comparators must define a consistent order.
- **Output**: the primary native artifact is a permutation, not an in-place reorder of heavy record payloads.
- **Memory**: O(n + d) scratch for native radix/counting paths (plus output), where d is histogram width limited to 65,536 entries. Stable C path can use up to ~12n bytes of additional scratch excluding the caller-provided output.
- **Scale**: native indices use `uint32_t`, so a single invocation supports up to 2^32−1 records in theory; practical limits are memory and address space. Use external sort for larger-than-memory workloads.

## Licenses and IP

MIT-licensed original CHROMA APEX source; see [`LICENSE`](LICENSE), [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), and [`docs/LEGAL_AND_PROVENANCE.md`](docs/LEGAL_AND_PROVENANCE.md). Describing a sorting method does not confer exclusive rights to it, and **an MIT license cannot guarantee freedom from third-party patent claims**. Obtain an independent legal review before making commercial patent-clearance assertions.

## Research integrity

The design deliberately reuses well-established *mathematical techniques* (histograms, radix-style numeric keys, monotonicity checks, stable index ordering) in an application-specific dispatcher. That is not copying third-party implementation source code. See `docs/RESEARCH_PAPER.md` for proof sketch and limitations. Neither Typhoon nor IPS⁴o was executed in this local benchmark; optional upstream IPS⁴o support is documented and can be enabled locally. No GitHub Actions or paid runners are used.

## Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md). Priority areas: real multi-core partitioning, binary-columnar composite keys, bounded byte-budget external sorting, portable SIMD evaluation, fully tested bindings, local competitor builds, sanitizer/fuzz validation, memory-mapped IO, and reproducible cross-hardware benchmarking.

## Publication

This repository is prepared for a dedicated GitHub repository. See [`docs/PUBLISH.md`](docs/PUBLISH.md). Creating a separate GitHub repository requires GitHub repository-creation access; do not upload to an unrelated existing project.
