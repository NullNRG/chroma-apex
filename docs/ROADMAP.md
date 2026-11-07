# Performance and release roadmap

## Release gates before 1.0

- [x] Explicit stable numeric order, including NaNs, infinities, signed zeros, signed/unsigned 64-bit integers.
- [x] C11 shared library, C++ header, Python and Go tested interfaces, JS heterogeneous-record sorter.
- [x] Deterministic tests with stable tie verification and varied distributions.
- [x] Local Boost pdqsort, `std::sort`, `std::stable_sort` comparisons with raw CSV.
- [x] No GitHub Actions or paid CI dependencies.
- [ ] Run C# and Rust binding tests on corresponding toolchains.
- [ ] Independently build and directly benchmark upstream IPS⁴o and Typhoon on compatible hardware and license terms.
- [ ] Test under ASan/UBSan + Valgrind where available; fuzz NaN payloads and integer boundaries.
- [ ] Implement an exact binary-columnar composite-key backend and compare end-to-end on wide/long mixed schemas.
- [ ] Add reusable arena / caller-supplied scratch allocation for predictable latency and zero malloc hot loops.
- [ ] Add portable multi-threaded and SIMD backends, requiring measured gains and race tests.
- [ ] Add byte-budgeted spill management and transactional failure/recovery policies for multi-TB JSONL.
- [ ] Publish independent hardware tables and memory peak measurements.
- [ ] Obtain an external software-license and patent-risk review before commercial clearance claims.

## Evaluation matrix

Sizes: 0, 1, 16, 120, 10K, 100K, 1M, 10M+.
Patterns: uniform random, high duplicate rate, heavy-tailed, already sorted, reverse, nearly sorted, short runs, sparse noise, skewed, adversarial.
Records: 8-byte numeric keys; 64-byte, 256-byte, 4KB and 64KB payloads; nested heterogeneous composite keys and varlen strings.
Metrics: kernel time, full materialization, key projection, peak RSS, allocations, cache misses, energy if measurable, throughput, stability, and total data movement.
Comparators: pdqsort, std::sort, std::stable_sort, IPS⁴o, Powersort, driftsort, Typhoon (platform allowing), plus specialized counting/radix on eligible domains.

## Contribution rules

Measured improvements must preserve stability and total-order semantics. No renaming conventional families to market them as mathematically original. Provide exact benchmark context and raw results when making performance claims.
