# Feasibility and verification - 27 October 2026

Both slices are implemented, but a fully live, submission-ready result is
**not yet verified**. Missing inputs have not been invented.

## Executed here

- Python 3.11.9 on Windows; source compiles.
- Offline tests: 36 passed, 1 skipped. The skipped test is the real PySAL Gi*
  3x3 integration test; `libpysal`/`esda` are unavailable on this machine.
- Installing those packages was attempted and failed with DNS resolution
  errors. Do not treat the skipped test as a pass. Install requirements and
  rerun the complete suite on a connected machine.
- Both-slice offline pipeline completed using the pre-existing real OSM and
  boundary caches. Those source observations were not newly downloaded here.
- The pinned boundary file contains 37 districts, with mixed historic metadata;
  newest districts may be missing. Boundary count is not hardcoded in logic.
- 220 raw records = 74 inside + 146 outside boundary districts.
- At the configured 40 m radius: 216 merged stations = 73 inside + 143 outside;
  4 raw records removed statewide/search-box-wide. Only one removed raw record
  was inside the state polygons. 57/220 raw records have known port counts.
- Radius sensitivity (search box, including outside points): 10 m -> 218,
  25 m -> 216, 40 m -> 216, 75 m -> 215, 100 m -> 215 stations. This is evidence
  of sensitivity, not proof that 40 m is optimal.
- No real VAHAN export is present. All 37 districts have missing EV totals and
  remain unranked. Synthetic flags/generation are OFF. No population, road,
  commercial or composite values have been fabricated; no Moran/Gi* statistic
  is reported for these all-missing indices.
- Required outputs, audits, validation sample and Folium HTML are generated.
  Map content/layer contracts are tested with fictional data. Browser visual
  rendering is not independently verified here.
- Eleven Folium/Branca JS/CSS libraries are not yet cached; this HTML currently
  needs internet to load those dependencies. It says so visibly. After a
  successful online run they are cached/copied beside the HTML. Basemap tiles
  still require internet by design, with no bulk tile downloads.

## Free-source feasibility

OSM/Overpass supplies a reproducible live-fetch route for chargers, roads and
commercial nodes with a primary and two fallback endpoints, retry messages and
query-specific caches. Live refresh was attempted from this environment; DNS
resolution failed. A cache-based run is not described as a fresh fetch.

No paid API is required. Optional OCM uses a user's free developer key.
Nominatim reconciliation is cached, single-threaded and limited to one request
per second, intended for small one-time name reconciliation. Review its usage
policy linked in README before operating it repeatedly.

Population candidate: IndiaSet's Census 2011 district compilation
(https://huggingface.co/datasets/indiaset/census-2011), publisher-labelled
CC-BY-4.0. The published schema and free paginated JSON API documentation were
reviewed. Actual dataset download and this dataset's endpoint response remain
unverified because DNS blocked local downloads. URL/licence/citation live in
config. Historic counts are not used until boundary compatibility is explicitly
verified; manual `data/raw/population.csv` is the fallback. No population source
has been used to produce actual per-capita scores in this run.

The retained boundary repository has no explicit dataset licence visible and
its README describes curation for personal usage. Its geometry should not be
represented as cleared for public redistribution. Resolve source rights and
check current district accuracy before public release. OSM data are ODbL;
OCM records can have individual provider terms; VAHAN reuse terms need checking.

## Remaining hand work / release checks

1. On a connected machine, install requirements and run `python -m pytest -q
   -rs`; the PySAL integration test must execute, not skip.
2. Supply the real VAHAN export, including source date and filters. This cannot
   be replaced by an assumed public free VAHAN API or invented counts.
3. Supply/review population totals compatible with the boundary vintage.
4. Run `python run_all.py --refresh` to obtain current OSM data, population
   snapshots and browser libraries. Then repeat with `--offline` and inspect
   map layers in a browser. Validate live Overpass/Hugging Face/OCM responses.
5. Review fuzzy/geocoded matches, merge audit and human validation sample.
   Record expert AHP judgments and justify modelling settings if presenting
   them as authoritative. Resolve boundary data licence/accuracy.

No grid-headroom, forecast, optimiser or dashboard was added. Confidence and
weight/radius choices are transparent editable modelling assumptions; none are
presented as measured data or a guarantee of station correctness.
