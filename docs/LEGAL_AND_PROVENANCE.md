# Licensing, provenance, and non-infringement limits

**License for CHROMA-written source: MIT.** See `../LICENSE`. This grants broad rights to use, modify, redistribute, and commercialize this implementation subject to including the license notice.

### Copyright vs algorithm ideas

Under U.S. copyright law, copyright protects code expression; not underlying mathematical principles, procedures, systems, or algorithms (17 U.S.C. § 102(b); see https://uscode.house.gov/us/usc/title17/chap1/sec102.html). Writing separate code to implement a general mathematical method is distinguishable from copying a third-party source implementation.

### What we have and have not verified

- The new C source, bindings, and test harness were authored for this project. The inherited CHROMA JS engine and demo came from the prior user project and carry MIT notices.
- No IPS⁴o, Typhoon, Boost pdqsort, driftsort, or third-party sorting *implementation source* is vendored in this repository. The native benchmark optionally *links/includes* system Boost; the user must comply with its independent license.
- The project openly uses established algorithmic ideas. **No claim of independent invention, novel sorting theory, patentability, patent non-infringement or universal superiority is made.**
- MIT contains an express warranty disclaimer, but **does not certify legal clearance**. Patent clearance requires a separate jurisdiction-specific search and professional legal evaluation, especially before commercial claims.
- Generated code provenance and ownership may depend on applicable terms, contracts and local law. The publisher should confirm the copyright holder name before release; `CHROMA APEX contributors` is a placeholder.

### Publication checklist

[ ] Confirm ownership and right to license prior CHROMA sources.
[ ] Confirm copyright notices and third-party references.
[ ] Decide policy for external patented techniques, and obtain independent legal opinion if needed.
[ ] Confirm license naming and default branch before public release.
[ ] Do not include local system Boost headers or upstream competitor source in the published archive.
[ ] Keep raw benchmark outputs immutable and accompanied by exact build metadata.
