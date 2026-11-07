#!/usr/bin/env bash
# CMake + real pretrained benchmark; Python dependencies must already be installed.
set -euo pipefail
base="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cmake -S "$base" -B "$base/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$base/build" --parallel 2
python3 "$base/pretrained/pretrained_engine.py" "$@"
