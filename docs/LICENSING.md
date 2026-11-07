# Licensing and Technical Provenance

## Project license

CHROMA APEX project source and documentation are made available under the MIT License in [../LICENSE](../LICENSE). The license grants broad copying, modification and distribution rights subject to preserving its copyright and permission notice. The license text, including its warranty disclaimer, is part of the legal grant and must not be stripped from redistributed copies.

## External implementations

CHROMA APEX does not vendor the implementations of Boost pdqsort, IPS⁴o, Typhoon, driftsort, Powersort or other competitors. Some benchmark features can reference separately installed third-party headers. Those implementations have their own terms:

- Boost components, including its optional pdqsort header where present: [Boost Software License](https://www.boost.org/LICENSE_1_0.txt).
- IPS⁴o upstream: [project repository and license](https://github.com/ips4o/ips4o).
- Other named sorting systems: consult their official repositories before integration.

Links and comparison tables are citations and interoperability descriptions, not a transfer of third-party code into the project.

## Algorithmic scope

The implementation applies established mathematical and algorithmic methods, including histogram distribution, radix digit passes, cached projections, stable index decoration and external multiway merging. Its engineering design and source code are distinct from a claim of exclusive ownership of those techniques.

Copyright terms are distinct from patents, trademarks and third-party code permissions. An MIT license cannot certify patent non-infringement or freedom to operate in every jurisdiction.
