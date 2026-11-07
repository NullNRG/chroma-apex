# CHROMA APEX: Stable Numeric Permutation and Schema-Projected Sorting for Large Records

**Technical report / reproducible software artifact — v0.1.0 (2026-11-06)**

## Abstract

Complex-record sorting frequently pays for key extraction, comparison dispatch, cache misses, and moving substantial payloads. CHROMA APEX separates *ordering* from *record materialization*: the runtime first extracts keys and computes a stable permutation of compact indices. The native path normalizes 64-bit scalar keys into an unsigned ordered domain and selects monotonic, histogram, or bytewise stable radix transitions. An independent JavaScript path projects heterogeneous records through a compound schema and optionally performs bounded-chunk external JSONL sorting. Unlike a new asymptotic algorithm, this is a systems-oriented composition and dispatcher of known methods. We provide explicit numerical semantics, proofs of stable ordering, implementation and correctness tests, and reproducible comparisons with conventional C++ and Boost pdqsort. The current artifact is competitive for large numeric and highly duplicated keys, but not on every input and not yet measured against IPS⁴o or Typhoon under matched conditions.

## 1. Problem and design target

For `n` records `R_i` with potentially large payload sizes, sort under key function `K(R_i)` and return a permutation `p` such that for all positions `j`:

`K(R[p[j]]) <= K(R[p[j+1]])`, and, whenever these keys tie, `p[j] < p[j+1]`.

The output is a stable index permutation, allowing clients to choose when or whether to move payloads. The primary performance target is end-to-end time when keys have already been extracted into a packed array; a separate metric must include key projection, marshaling, and materialization costs for specific language bindings.

## 2. Exact numeric order

Let `u` be the IEEE-754 binary64 bit pattern. For non-NaN values, map:

- negative sign: `k = bitwise_not(u)`
- nonnegative sign: `k = u XOR 0x8000000000000000`

Canonicalize signed zero to positive zero before projection; map all NaN payloads to `UINT64_MAX`. This gives an unsigned total ordering `−∞ < finite < +∞ < NaN`, with `±0` tied and all NaNs tied. For signed 64-bit integer values `x`, use its raw bits XOR `0x8000000000000000`; unsigned integers use their raw key.

## 3. Certified adaptive dispatch

First construct normalized keys and record original indices. An O(n) monotonic certificate immediately returns `[0,1,...,n−1]` if already sorted. A second O(n) certificate recognizes nonincreasing keys and emits equal-value runs in original order while reversing the sequence of distinct runs. Otherwise:

- If the 64-bit observed range `max−min+1` is sufficiently compact (`<=65536` and `<=4n`), use a stable dense histogram to compute offsets and scatter indices in input order.
- Otherwise perform stable LSD digit passes on the 64-bit normalized values, skipping byte positions with no variation.

No runtime sampling controls correctness; path selection is based on exact conditions.

## 4. Stability and termination

**Monotonic case:** the order is certified, so returning identity is correct and stable.

**Reverse case:** the normalized input contains nonincreasing keys. Emitting equal-key runs in the original order while reversing the sequence of *distinct* runs gives nondecreasing output and preserves ties.

**Histogram case:** buckets are processed in ascending numeric key order. For each key bucket, input indices are emitted in their original encounter order; therefore the result is stable and ordered.

**Radix case:** stable digit distribution on each ascending-significance byte preserves the relative order of records with equal processed suffixes. After all differing bytes are processed, the order is that of the full unsigned key. Equal 64-bit keys never change their original relative order. At most eight radix passes occur, and all loops have fixed bounds, proving termination.

**Work:** O(n + d) time for dense histogram, O(8n) time for radix, O(n) for detected ordered/reverse cases; O(n + d) auxiliary space excluding the caller-owned output, with `d<=65536`. Key normalization and materialization have distinct additional costs. A generic comparison sort for arbitrary opaque keys continues to have lower bound Ω(n log n) comparisons in the standard model; these fixed-width representations evade that bound only by exploiting key structure.

## 5. Heavy heterogeneous records

APEX XL projects source records into canonical field values, then sorts *indices* by cached schema projections. Supported descriptor classes include strings, dates, numbers, BigInts, booleans, nested paths, byte arrays, tuples, nulls and custom comparator/projection pairs. Its fallback for general opaque compound keys is a conventional comparison sorter on cached projections. There is **no mathematical proof of a faster-than-comparison sorting algorithm for arbitrary complex objects**; the gain comes from avoiding repeated extraction and payload copies.

For larger-than-memory JSONL files, the Node implementation emits stable, sorted spill runs and performs multiway heap merges. It stores original sequence numbers in spill files as a cross-run stable tie-breaker. This is known external-sort theory implemented as a practical reference tool, not a novel asymptotic method.

## 6. Limitations

- Results depend on input size, entropy, key format, CPU caches and memory bandwidth. Radix scratch allocation and normalization hurt tiny inputs and can lose on nearly sorted input.
- The native API is currently single-threaded and handles a single scalar column per call; nested composite schemas are implemented in JavaScript, not a native multi-column columnar kernel.
- Numeric index width limits one invocation to `UINT32_MAX` records. The native core does not offer a GPU or multicore implementation.
- Comparisons to IPS⁴o, Typhoon and modern Rust driftsort remain **unmeasured locally**. No third-party performance claims are repackaged as direct measurements.
- JSONL external sort is byte-preserving for nonempty record lines, not a fully general distributed file sort. Memory bounds depend on record sizes and the selected record-count chunk size.

## 7. Reproducibility

Build with Release CMake and run `./build/apex_benchmark 7`; raw results and build instructions appear in `docs/BENCHMARKS.md`. Run `make test` for locally available language bindings. Tests cover exact stable duplicates and floating-point exceptional values. Environment/compiler versions and benchmark caveats are recorded with results.

## 8. Prior art

Radix sorting, stable counting, decorated-index sorting, cached keys, numeric bit projections, adaptive sorting, run certification, and external multiway merging are established topics. Relevant modern implementations and comparisons include IPS⁴o (Axtmann et al., 2017/2020), pdqsort (Orson Peters), driftsort (Orson Peters and Lukas Bergdoll), and the Typhoon implementation. This report deliberately does not represent these concepts as original theoretical discoveries.

Resources: https://github.com/ips4o/ips4o ; https://github.com/Voultapher/driftsort ; https://github.com/ips4o/ips4o-benchmark-suite
