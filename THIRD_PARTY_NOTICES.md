# Third-party components and benchmark references

## Bundled as original CHROMA source (MIT)

The C kernel, native interface, language adapters, benchmark driver, new tests, docs, and accompanying project files are written for CHROMA. The prior CHROMA XL JavaScript engine and single-file demo are brought forward from the earlier user-owned project with its original MIT license.

## Not bundled

- **Boost pdqsort** — optional header from the user's *system* Boost installation; [Boost Software License 1.0](https://www.boost.org/LICENSE_1_0.txt). The benchmark auto-detects the header; APEX does not copy it or distribute its sources.
- **IPS⁴o** — optional upstream source, [BSD-2-Clause](https://github.com/ips4o/ips4o/blob/master/LICENSE). The benchmark can compile against a separately supplied local header. It has **not** been run as part of the published measurements.
- **Typhoon** — [upstream repository and licensing must be independently checked](https://github.com/search?q=typhoon+sort&type=repositories) before building, linking or distributing any code. No implementation bundled or locally timed.
- **Powersort, driftsort, C++ standard sorting** — competitor families mentioned as prior art, never bundled or relabeled as CHROMA inventions.

The benchmark CSV indicates exactly what ran; no values should be inferred for unexecuted competitors. External projects have independent licenses, claims, and performance characteristics.
