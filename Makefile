.PHONY: all test bench clean
all:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
	cmake --build build -j2
test: all
	ctest --test-dir build --output-on-failure
	LD_LIBRARY_PATH="$(CURDIR)/build:$${LD_LIBRARY_PATH}" python3 -m unittest discover -s packages/python -p 'test_*.py'
	(cd packages/go && go test ./...)
	node packages/js/test.js
	node packages/js/test_external.js
bench: all
	./build/apex_benchmark
clean:
	rm -rf build
