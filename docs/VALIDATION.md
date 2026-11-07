# Validation and Implementation Status

## Tested components

| Component | Test entry point | Recorded validation |
|---|---|---|
| Native C11 | ctest (apex_test) | Stable ties, exceptional float64 values, integer cases and return statuses |
| C++ | apex_benchmark | Output permutation verification across distributions and sizes |
| Python | unittest discover | Native ctypes index ordering |
| Go | go test ./... in packages/go | cgo numeric order |
| JavaScript | node packages/js/test.js | Schema projections and stable ordering |
| External JSONL | node packages/js/test_external.js | Spill/merge correctness and stable records |

C# and Rust adapters are present but were not compiled with their target toolchains during the recorded validation. Optional competitor support requires a user-supplied build of the upstream code and is not part of the core test suite.

## Test commands

~~~sh
make test
node packages/js/test_external.js
cmake -S . -B build-sanitize -DCMAKE_BUILD_TYPE=Debug -DCMAKE_C_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined'
cmake --build build-sanitize
ctest --test-dir build-sanitize --output-on-failure
~~~

Sanitizer availability is toolchain dependent; reported sanitizer success does not imply comprehensive security or memory safety.

## Invariants

Every successful ordering path must satisfy:

- Output length equals input length.
- Every original index occurs once.
- Keys are nondecreasing under the specified total order.
- Equal keys appear in original input order.
- The input numeric key buffer remains unchanged.
- Invalid input and allocation failure return a declared error rather than a successful but partial result.

For the streaming pipeline, stable equality is defined by global line sequence, including across spill-run boundaries.

## Known design limits

Native code has one scalar numeric key column per call, no multithreaded runtime, and 32-bit output indices. APEX XL handles nested schemas in JavaScript, with costs that depend on allocations and projection complexity. External JSONL chunks are count-limited rather than byte-limited. This release has no validated universal speed advantage, native multicore speedup, GPU implementation, or matched local IPS⁴o/Typhoon benchmark.

The benchmark results contain both favorable and unfavorable workloads; all performance comparisons must preserve that distinction.
