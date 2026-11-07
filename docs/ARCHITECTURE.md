# Architecture and Design

## 1. Overview

CHROMA APEX has two independent execution stacks joined by an architectural convention: **order small references rather than repeatedly moving large records**.

~~~text
Packed numeric keys ──> C11 numeric ordering ──> uint32 permutation
                                  │
                                  ├─ C++ wrapper
                                  ├─ Python ctypes
                                  ├─ Go cgo
                                  ├─ C# P/Invoke
                                  └─ Rust FFI

Heterogeneous records ──> JS schema projection ──> cached columns
                                                     │
                                  adaptive numeric ──┤
                                  categorical lead ──┤
                                  generic comparator ┤
                                                     ↓
                                           stable permutation
                                                     ↓
                                   optional ordered materialization

Large JSONL ──> bounded record chunks ──> sorted spill runs
                                           ↓
                                multiway merge with sequence IDs
                                           ↓
                                      output JSONL
~~~

The numeric and heterogeneous implementations share an output concept, **not** a single native key representation. The JavaScript engine is not a binding to the C ABI for arbitrary objects.

## 2. Stable permutation contract

For n records, return p of length n such that each integer in [0,n) occurs exactly once. With comparison relation ≼:

1. For every j, key(p[j]) ≼ key(p[j+1]).
2. When keys compare equal, p[j] < p[j+1].

A caller may index existing data through p, build a new view, or materialize a copy. Numeric native inputs are immutable during ordering. JS order() returns a fresh typed index array; sortedCopy() makes a new reference array and sort() mutates the supplied record array.

## 3. Native numeric normalization

The native core converts IEEE-754 binary64 to sortable unsigned 64-bit encodings. Negative values are bitwise complemented, positive values have the top bit flipped; signed zero and NaN values are canonicalized. Signed integer keys have the sign bit flipped, unsigned keys retain their representation.

Resulting domain order:

- infinity < negative finite < zero < positive finite < +infinity < NaN

The first item here denotes negative infinity. Equal numeric encodings are stable by original index.

The dispatcher detects complete ascending or descending order before distribution. For a compact exact key span, it uses a stable dense histogram; otherwise it performs stable bytewise radix passes, skipping byte positions that are constant across the input.

Each dispatch decision preserves **exact** ordering; sampling or probability does not determine correctness.

## 4. Native dataflow and complexity

- Sorted certificate: O(n) work.
- Reverse-run certificate: O(n) work, preserving the encounter order within equal-key runs.
- Compact histogram: O(n + d) time and space for range width d, capped by the implementation threshold.
- Fixed-width radix: O(8n) operations in the worst case, with at most eight nontrivial byte passes.
- Stable output: uint32 permutation, 4n bytes supplied by caller.
- Additional allocation: key buffer plus temporary index storage and histogram. Peak scratch is reported in apx_stats, excluding caller-owned input/output.

The native implementation is currently **single-threaded** and returns only ascending permutations. No native arbitrary comparator API exists.

## 5. Complex-record projection

A JS schema is an ordered list of descriptors (path, type, direction and null handling). Each record is projected once into schema columns; the primary key determines initial grouping or numeric specialization where applicable. For fully general compound keys, the engine uses a cached-key comparison sort.

This path can outperform repeated deep property lookup, but it does not evade comparison-sorting lower bounds for opaque arbitrary keys. Cache locality and the cost of projection govern whether an optimization pays off.

Record payloads are never copied by the ordering stage. Sorted output arrays contain references to the original objects. Input records are not deep-cloned.

## 6. Disk-backed JSONL

The external Node sorter accumulates at most a configured number of records per initial chunk, sorts the chunk, emits numbered spill runs, and performs a bounded-fan-in multiway merge. Each run entry carries original input sequence number; this enforces stability across runs. Temporary work files are removed after success or failure.

Memory is bounded by record count and fan-in, **not by an absolute byte limit**. A very large single line, large nested key, or serialization overhead can still exhaust memory. Output renaming is atomic when supported by the destination filesystem.

## 7. Design boundaries

No universal fastest-sorter claim follows from this architecture. Fixed-width distribution methods have different memory/runtime trade-offs from comparison sorts. Native sorting of packed keys is not equivalent to moving full records, sorting arbitrary nested objects, or sorting disk files. Benchmark each tier separately.

The architectural goal is stable, predictable key semantics and competitive throughput when payload movement and repeated key extraction dominate cost.
