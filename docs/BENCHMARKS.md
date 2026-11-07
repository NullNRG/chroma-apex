# CHROMA APEX v0.1.0 — Local benchmark audit

**These are actual same-host tests, not record-breaking or cross-paper claims.** Lower elapsed time is better. A speed ratio above 1 means APEX was faster.

## Environment and fairness

Debian 13, x86_64; AMD EPYC 9V74 virtual host with 5 visible vCPUs; GCC/G++ 14.2.0, CMake Release `-O3`; Node.js 22.16.0, Python 3.13.5, Go 1.23.2. Native benchmark uses deterministic `mt19937_64` with identical arrays, seven measured runs, median, warm-up and correctness verification outside the timed section. The measured work is full **stable index permutation from already-computed numeric keys**; it is not full record extraction/copy. APEX does include key normalization and scratch allocation; C++/Boost methods sort stable indices referencing the same keys. Boost pdqsort has explicit index tie-break; `std::stable_sort` uses its own stability with key-only comparator. System Boost supplied the header (not bundled). JS tests include key extraction and reference materialization, rotate execution order, force GC between rounds, and verify identical stable output IDs. Treat local virtual-machine timings as provisional pending repeated multi-hardware tests.

## Native fixed-width numeric keys (milliseconds)

| Records | Pattern | APEX | Boost pdqsort + tie | APEX relative speed |
|---:|---|---:|---:|---:|
| 120 | random64 | 0.0027 | 0.0008 | 0.29× |
| 120 | compact | 0.0013 | 0.0007 | 0.58× |
| 120 | ordered | 0.0002 | 0.0003 | 1.24× |
| 120 | mostly-ordered | 0.0002 | 0.0002 | 1.19× |
| 120 | reverse | 0.0005 | 0.0003 | 0.70× |
| 10,000 | random64 | 0.1803 | 0.7449 | 4.13× |
| 10,000 | compact | 0.0707 | 0.7853 | 11.10× |
| 10,000 | ordered | 0.0145 | 0.0184 | 1.27× |
| 10,000 | mostly-ordered | 0.0763 | 0.0487 | 0.64× |
| 10,000 | reverse | 0.0389 | 0.0253 | 0.65× |
| 100,000 | random64 | 2.8953 | 9.6876 | 3.35× |
| 100,000 | compact | 0.8501 | 9.9824 | 11.74× |
| 100,000 | ordered | 0.1578 | 0.1838 | 1.16× |
| 100,000 | mostly-ordered | 1.0471 | 0.7363 | 0.70× |
| 100,000 | reverse | 0.3888 | 0.2616 | 0.67× |
| 500,000 | random64 | 18.4231 | 56.9527 | 3.09× |
| 500,000 | compact | 4.9897 | 57.1511 | 11.45× |
| 500,000 | ordered | 0.7726 | 1.0031 | 1.30× |
| 500,000 | mostly-ordered | 6.4793 | 4.7055 | 0.73× |
| 500,000 | reverse | 2.0337 | 1.3212 | 0.65× |

### What these timings actually establish

APEX wins markedly on medium/large fixed-width random and highly duplicated numeric keys because it takes advantage of the key domain, and wins some presorted cases. Boost pdqsort wins on tiny randomized arrays, mostly ordered, and reversed arrays in the tested configuration. Comparison sorting supports arbitrary comparators, whereas APEX's fast native path requires a numeric scalar key. Additional memory pressure and cache limitations are not captured by elapsed timing alone.

## Nested composite objects, complete JS operation (milliseconds)

Three nested keys: numeric tier, numeric score and string region; a separate payload string accompanies each record. All methods include projection, ordering and result references. The direct baseline uses nested field access in `Array.sort`; the cached baseline extracts the same three keys once, then sorts indices.

| Records | Input | APEX XL | Direct Array.sort | Cached Array.sort |
|---:|---|---:|---:|---:|
| 10,000 | random | 6.95 | 2.79 | 4.36 |
| 10,000 | ordered | 3.58 | 0.30 | 1.72 |
| 10,000 | noise | 4.02 | 0.54 | 1.43 |
| 100,000 | random | 60.85 | 40.96 | 49.26 |
| 100,000 | ordered | 35.46 | 7.55 | 12.23 |
| 100,000 | noise | 39.83 | 10.41 | 14.25 |
| 300,000 | random | 201.79 | 182.04 | 288.16 |
| 300,000 | ordered | 108.00 | 34.60 | 58.58 |
| 300,000 | noise | 115.96 | 41.17 | 63.90 |

**Verdict:** APEX XL loses several of these complex-key tests, especially those with long sorted runs. The report includes these failures rather than implying dominance across complex data.

## Expensive compound balance metric (milliseconds)

Each record has a 64-number `subTokens` array, entropy seed and ~1 KiB payload string. Metric `rawWeight + entropySeed.length * 1.5 + (sum(subTokens) % 7)`. The direct comparator recomputes the metric repeatedly; APEX and the cached comparator extract once. All methods verify stable output and include materialization.

| Records | APEX XL | Direct comparator | Cached comparator |
|---:|---:|---:|---:|
| 10,000 | 8.35 | 155.33 | 10.56 |
| 100,000 | 100.54 | 2167.79 | 143.26 |

**Verdict:** For costly keys, cached projections are genuinely valuable. The tested APEX path beat the cached comparator, but no theorem guarantees that for all input distributions.

## Competitor status

| Competitor | Direct local benchmark? | Qualification |
|---|---|---|
| `std::sort` / `std::stable_sort` | Yes | Same numeric key arrays / stable ties |
| Boost pdqsort | Yes | System Boost source and explicit stable tie-key |
| IPS⁴o | **No** | Separately obtainable BSD-2-Clause source; CMake accepts local include path |
| Typhoon | **No** | Published figures target different hardware, key types, and OS/memory behavior |
| Powersort / Rust driftsort | **No** | Need pinned native implementations and matching builds |

Relevant original sources: https://github.com/ips4o/ips4o ; https://github.com/Voultapher/driftsort ; https://irl.cs.tamu.edu/projects/streams/ . None of those source implementations is bundled here.

## Re-run all local comparisons

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
./build/apex_benchmark 7 > bench/local_baseline.csv
node --expose-gc bench/bench_js.js
node --expose-gc bench/bench_balance.js
```

For locally obtained IPS⁴o, build with `-DAPX_WITH_IPS4O=ON -DAPX_IPS4O_INCLUDE_DIR=/path/to/ips4o`; record upstream commit, build flags and CPU model. No GitHub Actions are required. Peak RSS, energy, hardware counters, commercial patent clearance and multi-core throughput remain open validation work.
