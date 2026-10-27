# Changes in this version
- Removed `NAME_ALIASES` (hand-typed spellings). Names are matched by exact -> fuzzy -> geocoding.
- Removed the 2011 boundary file and the planned `NEW_TO_PARENT` table. Newer boundaries are downloaded (pinned commit).
- Removed the hardcoded state box, ISO code, map centre and "38 districts" message. Search area and map view come from the boundaries.
- All settings moved to `src/config.py`.
- Synthetic EV numbers are now OFF by default; missing districts show "no EV data" and are not ranked.
- VAHAN file may be RTO-level; RTOs are placed in districts automatically.
- Default scoring policy changed to "smoothed" (see README).
- Added `.gitignore` (keeps `.env` and caches out of GitHub) and `tests/test_resolver.py`.
- Fixed README path (`cd chargegap`).
- Integer ranks: district_gap_scores.csv saves rank as nullable Int64 (integers, empty when no EV data); checks.py prints integer ranks while GeoJSON keeps float/null for map compatibility.
- Step labels: run_all.py printed steps renamed to sequential 1-7 order, and bracketed module counters ([1/5] to [5/5]) aligned to that order.
- VAHAN data in repo: added committed data/samples/ folder tracked in git with VAHAN_SAMPLE_FILE fallback in load_vahan.py when data/raw/ file is missing.
- Charging ports count: added ports/ports_known columns to chargers, port_count and gap_unit to scores, GAP_UNIT setting ("stations" or "ports"), and capacity defaults to 1 port when unknown.
- Data flag preservation: load_vahan.py preserves input data_flag column, marking a district synthetic if any row is synthetic.
- Synthetic test data: added data/samples/vahan_tn_ev_by_district_SYNTHETIC_TEST.csv and USE_SYNTHETIC_TEST_DATA setting with loud warning.
- Synthetic data tests: added tests in tests/test_scores.py for data_flag preservation, aggregation, and gating.
- Documentation: added Synthetic test data section to README.md explaining test usage and submission restrictions.

## 2026-10-27 - Slices 0 and 1

- Preserved Slice 0 CSV/HTML names and raw-count layer; selected deduplicated
  counts go into a separate CSV with raw counts alongside them.
- Added conservative metric-distance/name/operator merging, max-known ports,
  confidence components, source membership audits, radius sensitivity,
  preserved human validation samples, and reviewed-merge precision reporting.
- Added documented population downloads with an explicit historical-boundary
  review gate and manual compatible-population fallback; never invented values.
- Added cached OSM road clipping and commercial node density. Failed/partial
  data remain missing rather than being treated as zero.
- Added complete-case entropy and editable AHP index, consistency checks,
  score-based Spearman comparison, seeded Dirichlet rank ranges/top-K shares.
- Added PySAL Queen Moran's I/Gi*, raw and BH-corrected classes, and explicit
  missing/island/constant handling with small-sample warnings.
- Added composite, hotspot and confidence map layers; cached JS/CSS assets,
  escaped popups, station/port-aware labels and missing/synthetic warnings.
- Added --refresh, --offline and --slice 0; cache fingerprints, download
  metadata, key-safe errors, a third Overpass endpoint and count checks.
- Removed invented template numbers; enforced synthetic test file gating and
  flags, finite nonnegative EV data, and preserved source data flags.
- Replaced the network-dependent resolver test with fictional polygons;
  retained scoring tests and added Slice 1/cache/map/population tests.
- Expanded README with formulas, assumptions, source licences, exact manual
  work and limitations. See outputs/feasibility.md for actual verification.
