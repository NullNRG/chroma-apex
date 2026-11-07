# Sorting Algorithm Comparison Catalog

## Scope

The following catalog compares execution models and applicability. It does **not** transfer performance numbers between machines, languages, or different sorting contracts. For APEX Native, the common contract is **stable ascending index permutation from precomputed fixed-width keys**; direct in-place sorting of records is a different workload.

**Evidence labels:** *Measured* = local same-host benchmark in bench/local_baseline.csv or the associated JS results. *Published* = implementation characteristics from named project documentation or scholarly publications. *Unmeasured* = no same-host speed result for this library.

## 1. Numeric and data-movement methods

| Implementation/family | Stable by default? | Data model | Relevant trade-off | Evidence |
|---|---|---|---|---|
| CHROMA APEX Native | Yes | float64/int64/uint64, permutation | Fast fixed-width paths; extra scratch and key normalization | Measured |
| Stable dense counting | Yes when implemented as ordered scatter | Compact integer keys | Linear in n + key range; poor when span enormous | Architectural comparison |
| LSD radix sorting | Yes when every digit pass is stable | Fixed-width digitizable keys | Multiple full scans; bandwidth/scratch cost | Architectural comparison |
| MSD radix / American flag sort | Varies | Integer/string prefixes | Can reduce work on prefixes; often unstable/in-place | Published family |
| Spreadsort (Boost) | Not necessarily | Scalar integers/floats/strings | Hybrid distribution/comparison model | Published |
| Ska sort | Usually not stable | Fixed-width and composite radix keys | High-performance radix-focused C++ | Published |
| IPS²Ra | Not guaranteed | Parallel integer keys | Cache-conscious in-place radix and parallelism | Published |
| Google Highway vectorized sort | Varies | Supported SIMD primitive key types | Vector instructions and platform-specific throughput | Published |

## 2. General comparison sorts

| Implementation/family | Stable? | Strength | Key difference from APEX | Evidence |
|---|---|---|---|---|
| C++ std::sort | No requirement | Generic comparators, in-place-style, optimized | Direct comparison model | Measured, stable tie-key adaptation |
| C++ std::stable_sort | Yes | General stable comparison sorting | Supports opaque types; extra memory | Measured |
| Boost pdqsort | No | Pattern defeating, branch-efficient partitioning | Opaque comparators; stable tie-key added in benchmark | Measured |
| IPS⁴o | No by default | Parallel in-place samplesort, cache locality | Sample partitioning, multicore | Unmeasured here |
| PS⁴o | No by default | Parallel samplesort | Different memory profile | Published |
| Powersort | Yes | Nearly optimal merge schedule on runs | Strong partially ordered datasets | Unmeasured here |
| TimSort | Yes | Adaptive natural-run merges | Generic comparison/run structure | Published |
| Rust driftsort | Yes | Adaptive stable general sorting | Handles opaque comparators natively | Unmeasured here |
| Rust ipnsort | No | Pattern-defeating unstable sorting | No stable-output guarantee | Published |
| Glidesort | Yes | Adaptive stable quick/merge hybrid | Generic Rust comparator, run adaptation | Unmeasured here |
| Fluxsort | Yes | Branchless stable quick/merge hybrid | Comparator-based and adaptive | Unmeasured here |
| Quadsort | Yes | Branchless merges and adaptive runs | Generic comparison sorting | Published |
| Crumsort | No | In-place adaptive branchless hybrid | Lower scratch, no stability | Unmeasured here |
| Grailsort | Yes | Stable block-merge approach | Lower-extra-memory option | Published |
| Sorting networks / bitonic | Depends on tie treatment | Fixed compare network, SIMD/GPU batching | Very different size and execution constraints | Published |

## 3. Large datasets and alternative execution

| Implementation/model | Primary use | Comparison consideration |
|---|---|---|
| CHROMA APEX external JSONL | Stable record-count chunks and disk-backed multiway merge | Includes JSON parsing, serialization, spill IO |
| Database ORDER BY / DuckDB-style external sort | Out-of-core query engines | Query execution, compression, spilling and vectorized operators |
| Parallel sort / oneDPL | Multiple CPU threads or SYCL accelerator | Extra runtime, memory transfer and scheduling |
| GPU sorting (CUB / rocPRIM family) | Large device-resident numeric keys | Host/device transfer can dominate small workloads |
| External merge sort | Storage-bound files | Block IO, merge fan-in, file-descriptor limits |
| Typhoon | High-throughput specialized key sorting | Published results depend on specialized OS and memory behavior; unmeasured here |

## 4. Why apples-to-apples benchmarking is hard

Stable output can be imposed on an unstable algorithm using original indices as secondary keys; that changes key width, comparator complexity, memory traffic and semantics. In-place record sorting, index permutation, and out-of-core sorting must not be mixed in one speed ranking.

For fair comparisons, record at least:

- Stable versus unstable output; index permutation versus payload movement.
- Full projection/marshaling/materialization versus precomputed-key kernel.
- Key width and distribution, record size, ties, original order, N.
- CPU, number of cores, RAM/NUMA, compiler flags, exact upstream revision.
- Allocations, peak resident memory, bytes moved, throughput, confidence intervals.
- Thread counts and power mode for multicore benchmarks.

## 5. Local findings

The same-host numeric benchmark includes std::sort, std::stable_sort, Boost pdqsort (when system Boost is available), and APEX. At N = 100,000, APEX beats the stable-tie pdqsort baseline on randomized fixed-width and compact key domains, but loses on some mostly ordered and descending inputs. Complex JS records show mixed results: cached comparisons win on several simple schemas, while APEX can win when the compound metric is expensive.

The source files in bench/ and the separate [Benchmarks](BENCHMARKS.md) report are the evidence for these claims. None of the unmeasured competitors has been assigned a fabricated runtime.

## 6. Primary technical references

- [IPS⁴o original paper](https://arxiv.org/abs/1705.02257) and [implementation](https://github.com/ips4o/ips4o)
- [Engineering In-place (Shared-memory) Sorting Algorithms](https://doi.org/10.1145/3505286)
- [pdqsort implementation and design](https://github.com/orlp/pdqsort)
- [Powersort](https://powersort.github.io/)
- [Rust stable/unstable slice sorting documentation](https://doc.rust-lang.org/std/primitive.slice.html)
- [driftsort introduction](https://github.com/dzaleskis/sort-research/blob/main/writeup/driftsort_introduction/text.md)
- [Glidesort](https://github.com/orlp/glidesort)
- [Fluxsort](https://github.com/scandum/fluxsort) and [Crumsort](https://github.com/scandum/crumsort)
- [Boost Sort](https://www.boost.org/doc/libs/release/libs/sort/doc/html/index.html)
- [Intel oneDPL parallel API](https://www.intel.com/content/www/us/en/docs/onedpl/developer-guide/2022-7/parallel-api.html)

This catalog is an engineering comparison, not a patent-search report.
