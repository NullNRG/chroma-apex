# Usage Examples

All examples use the repository's source layout. Build the native shared library once with CMake before running the FFI examples.

## C — stable order of weights

~~~c
#include "chroma_apex.h"
#include <stdint.h>
#include <stdio.h>
int main(void) {
    double keys[] = {5.0, -2.0, 5.0, 1.0};
    uint32_t positions[4];
    apx_stats stats = {0};
    if (apx_order_f64(keys, 4, positions, &stats) != APX_OK) return 1;
    for (int j=0; j<4; ++j) printf("%u ", positions[j]);
    // 1 3 0 2
    return 0;
}
~~~

## C++ — index large payloads instead of moving them

~~~cpp
#include "apex.hpp"
#include <vector>
#include <string>
struct Record { double score; std::string largePayload; };
std::vector<Record> rows = {{8.0, "A"}, {3.0, "B"}, {8.0, "C"}};
std::vector<double> keys;
for (const auto& row : rows) keys.push_back(row.score);
auto permutation = chroma_apex::order(keys);
// Iterate rows[permutation[i]] without relocating their payloads.
~~~

## Python — reusable native sorter

~~~python
from packages.python.apex_sort import Apex

engine = Apex()
rows = [{"name": "C", "weight": 4.0},
        {"name": "A", "weight": 1.0},
        {"name": "B", "weight": 4.0}]
result = engine.sorted_records_by_float64(rows, lambda r: r["weight"])
print([r["name"] for r in result])  # ['A', 'C', 'B']
~~~

## Go — cgo numeric binding

~~~go
package main
import (
    "fmt"
    apex "chromaapex"
)
func main() {
    positions, err := apex.OrderFloat64([]float64{5, 2, 5, 1})
    if err != nil { panic(err) }
    fmt.Println(positions) // [3 1 0 2]
}
~~~

Run the snippet in a Go program whose go.mod requires/replaces the local packages/go module, or place it within a separate package in that module.

## C# — P/Invoke

~~~csharp
using ChromaApex;
var order = Apex.Order(new double[] {3.5, -1, 3.5, 2});
// order: 1, 3, 0, 2
~~~

Place the compiled shared native library in the process loader path. This adapter has not been executed in the recorded environment.

## Rust — FFI

~~~rust
use chroma_apex::order_f64;
fn main() {
    let indices = order_f64(&[4.0, -2.0, 4.0]).unwrap();
    assert_eq!(indices, vec![1, 0, 2]);
}
~~~

Requires native library discovery at link and runtime; adapter compilation is not part of the recorded tests.

## JavaScript — lexicographic complex keys

~~~js
const { createApexXL } = require('./packages/js/apex_massive');
const sorter = createApexXL();
const rows = [
  { id: 0, meta: { level: 2, city: 'Oslo' }, bytes: new Uint8Array([2,1]) },
  { id: 1, meta: { level: 1, city: 'Rome' }, bytes: new Uint8Array([1,5]) },
  { id: 2, meta: { level: 2, city: 'Oslo' }, bytes: new Uint8Array([2,0]) }
];
const schema = [
  { path: 'meta.level', type: 'number' },
  { path: 'meta.city', type: 'string' },
  { path: 'bytes', type: 'bytes' }
];
const indices = sorter.order(rows, schema);
console.log([...indices]); // [1, 2, 0]
~~~

## Original multi-attribute balance metric

~~~js
const { createApexXL } = require('./packages/js/apex_massive');
const records = [
  { id: 0, rawWeight: 8, entropySeed: 'abc', subTokens: [1, 2] },
  { id: 1, rawWeight: 3, entropySeed: 'a', subTokens: [0, 1] },
  { id: 2, rawWeight: 8, entropySeed: 'abc', subTokens: [1, 2] }
];
const sorted = createApexXL().sortedCopy(records, [{ type:'balance' }]);
console.log(sorted.map(r=>r.id)); // [1, 0, 2]
~~~

## Streaming file sort

The repository includes examples/data.jsonl and examples/schema.json.

~~~sh
node packages/js/external_jsonl.js examples/data.jsonl /tmp/chroma-sorted.jsonl examples/schema.json 25000
~~~

For programmatic use, import externalSortJsonl as shown in the [API reference](API.md). For datasets with very large single objects, measure actual peak resident memory, not just the chunk-record count.

## Running tests

~~~sh
make test
node packages/js/test_external.js
~~~

See [Validation](VALIDATION.md) for coverage and [Benchmarks](BENCHMARKS.md) for measurement data.
