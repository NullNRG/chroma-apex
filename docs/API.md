# API Reference

## 1. C11 ABI

Public header: core/include/chroma_apex.h. Build target: chroma_apex shared library.

| Function | Input | Output | Description |
|---|---|---|---|
| apx_order_f64(keys, n, out, stats) | const double* | uint32_t* | Stable ascending binary64 ordering |
| apx_order_u64(keys, n, out, stats) | const uint64_t* | uint32_t* | Stable ascending unsigned 64-bit ordering |
| apx_order_i64(keys, n, out, stats) | const int64_t* | uint32_t* | Stable ascending signed 64-bit ordering |
| apx_status_string(status) | integer status | const char* | Human-readable error |
| apx_abi_version() | none | uint32_t | (major << 16) | minor |

The final column above describes the ABI version encoding as bitwise OR of shifted major and minor components.

Inputs and output must not alias. For nonempty input, keys and out must be valid buffers for n elements. The caller owns out and can pass NULL for stats. Maximum n is UINT32_MAX; the functions return an error for oversized requests or allocation failures.

### Status codes

| Code | Meaning |
|---|---|
| APX_OK = 0 | Success |
| APX_BAD_ARGUMENT = 1 | Null/invalid argument |
| APX_TOO_LARGE = 2 | Index range exceeded |
| APX_NO_MEMORY = 3 | Allocation failed |

### Statistics

apx_stats exposes count (input elements), passes, path (chosen dispatch), and scratch_bytes_peak (maximum extra allocation, excluding input/output). The path enum includes APX_EMPTY, APX_ORDERED, APX_RADIX, APX_COUNTING, and APX_REVERSED. These statistics describe work categories, not hardware instruction counts.

### Floating-point order

The comparator convention is negative infinity < finite numeric values < positive infinity < NaN. Negative and positive zero compare equal; NaN payloads compare equal. Stable ties preserve input order. This differs from IEEE totalOrder in its zero and NaN treatment.

## 2. Language interfaces

| Language | Module | Public entry points |
|---|---|---|
| C++ | packages/cpp/apex.hpp | chroma_apex::order(vector<double>) |
| Python | packages/python/apex_sort.py | Apex.order_float64, order_int64, order_uint64, sorted_records_by_float64 |
| Go | packages/go | OrderFloat64, OrderInt64 |
| C# | packages/csharp/ChromaApex.cs | Apex.Order(double[]), Apex.Order(long[]), Apex.SortedBy<T> |
| Rust | packages/rust/src/lib.rs | order_f64(&[f64]) |
| JavaScript | packages/js/apex_massive.js | createApexXL().order, sort, sortedCopy |

Python, Go and C++ interfaces are covered by local tests. C# and Rust wrappers require platform builds; no certified target-platform testing is recorded for them.

For native bindings, make the shared library visible in the system dynamic-loader path. The Go package uses cgo and compiles a C translation unit; the Python helper searches common local build outputs by default. See the examples for language-specific invocation.

## 3. JavaScript APEX XL

~~~js
const { createApexXL } = require('./packages/js/apex_massive');
const engine = createApexXL();
const indices = engine.order(records, schema, stats);
const sorted = engine.sortedCopy(records, schema, stats);
engine.sort(records, schema, stats); // mutates record-array positions
~~~

Each call uses its own schema and optional mutable stats object. order() returns a Uint32Array. sortedCopy() returns a new Array of original object references. sort() returns the input array.

### Schema descriptors

Every descriptor may set:

| Field | Type | Meaning |
|---|---|---|
| path | string or path-parts array | Dot-separated nested access; omitted for balance/custom |
| type | string | Projection and comparison type |
| order | asc or desc | Direction; asc by default |
| nulls | first or last | Placement of null/missing, last by default |
| project / compare | functions | Required for custom descriptor |

Types: number, date, boolean, string, bigint, balance, array-length, token-sum, string-length, bytes, tuple, json, custom, auto.

- Strings use JavaScript code-unit comparison, not locale-aware collators.
- Dates are converted to timestamps; missing values obey null placement.
- Bytes require Uint8Array-compatible inputs.
- Custom compare(a,b) must return a finite negative, zero, or positive number and be transitive.
- The balance type projects rawWeight + 1.5 * entropySeed.length + (sum(subTokens) % 7); records must have finite valid components.
- A tuple descriptor compares array members in order.
- A multi-column schema is lexicographic in descriptor order; equal projected keys preserve original relative order.

A classic script element can access window.ChromaApexXL; CommonJS exports are available in Node.js.

## 4. External JSONL sorter

Module: packages/js/external_jsonl.js.

~~~js
const { externalSortJsonl } = require('./packages/js/external_jsonl');
const result = await externalSortJsonl(
  'input.jsonl',
  'output.jsonl',
  [{ path:'event.time', type:'date' }, { path:'id', type:'string' }],
  { chunkRecords:25000, fanIn:8 }
);
~~~

Options: chunkRecords (integer >= 2), fanIn (2..128), tempDir, and onProgress callback. Result includes records, initialRuns, mergePasses, output, chunkRecords, fanIn. Input format is one JSON value per nonempty line; schema projection must accept each record.

The implementation uses a working directory of spill files and supports files larger than available RAM as long as chunks and individual records fit.

## 5. Operational errors

Native APIs return status codes instead of throwing. Python raises exceptions for failed native calls or invalid integer ranges. JavaScript throws TypeError/RangeError for invalid schemas and keys. The external Node process reports parsing, I/O, and validation failures through a rejected promise and nonzero CLI exit status.
