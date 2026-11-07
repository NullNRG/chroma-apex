# Reproducible Benchmark Protocol

## Objectives

Measure sorting throughput, stability, memory overhead, and predictability without confusing numeric-key kernels with complete record sorting. A performance assertion is meaningful only alongside the workload contract.

## 1. Build and execute

~~~sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2
ctest --test-dir build --output-on-failure
./build/apex_benchmark 7 > /tmp/apex-native.csv
node --expose-gc bench/bench_js.js
node --expose-gc bench/bench_balance.js
~~~

The benchmark supports optional system-provided Boost pdqsort and a separately supplied IPS⁴o header; enabling a competitor does not imply its license is included in CHROMA. No CI service is required for the benchmark.

## 2. Record the workload

For every measurement record N, seed, key representation, original permutation, duplicate ratio, distributions, sorted-run structure, record payload bytes, schema, projected-key cost, threads, CPU, operating system, compiler flags, and repository revision.

Separate at least four experiments:

1. **Numeric kernel:** keys already encoded in a packed array, result permutation only.
2. **Full object ordering:** projection, permutation, and ordered references or materialized records.
3. **Disk external sort:** parse+spill+merge+write with bytes read/written and peak resident memory.
4. **Parallel or accelerator sort:** compute runtime and synchronization with transfer costs identified.

## 3. Fairness controls

- Generate the same immutable input before each contender; restore any mutable working arrays.
- Warm up each implementation before timing. Use enough repetitions to estimate median and variability.
- Randomize or rotate contender order; do not always benchmark APEX first.
- Validate exact keys, stable tie order, and all original records after every run.
- Define memory accounting consistently, including input, output permutation, cached keys and scratch.
- For an inherently unstable competitor, measure either its native semantics or an explicitly documented stable-index adaptation; label the adaptation.
- Compare single-thread with single-thread, and parallel with parallel at equal thread counts.
- Avoid performance claims based on a single virtualized host or one distribution.

## 4. Required dataset matrix

| Axis | Values |
|---|---|
| N | 0, 1, 16, 120, 10k, 100k, 1M, 10M or memory limit |
| Key types | float64, uint64, int64, strings, nested tuples, mixed schemas |
| Distributions | uniform, compact/duplicates, Zipf-like skew, nearly sorted, reverse, runs, isolated swaps |
| Payload sizes | 0, 64, 256, 4096 bytes, larger references |
| Output mode | permutation, new array, in-place record array, output file |
| Resource | time, allocation, peak RSS, throughput, bytes written and read |

## 5. Published data in this repository

bench/local_baseline.csv contains local numeric measurements and does not establish universal performance rankings. bench/local_js_results.json and bench/local_balance_results.json cover different JS workloads. The full interpretation is in [Benchmarks](BENCHMARKS.md); the competitor status and design differences are in [Comparisons](COMPARISONS.md).

No Typhoon, driftsort, Powersort, or equivalent cross-project runtime result is presented as locally measured.

## 6. Validation before publication of new numbers

All measured output permutations must pass bijectivity, ascending key order and stable tie tests. Reject runs with failed correctness checks. Record toolchain versions and hardware metadata alongside raw outputs. Do not use theoretical complexity or benchmark-video operation counts as substitutes for real elapsed time.
