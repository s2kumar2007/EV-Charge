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

### Complete changed-file list (29 files)

- `.env.example`
- `.gitignore`
- `CHANGES.md`
- `README.md`
- `checks.py`
- `data/raw/vahan_tn_ev_by_district_TEMPLATE.csv`
- `outputs/feasibility.md`
- `pytest.ini`
- `requirements.txt`
- `run_all.py`
- `src/build_scores.py`
- `src/config.py`
- `src/dedupe_chargers.py`
- `src/fetch_chargers.py`
- `src/fetch_indicators.py`
- `src/gap_index.py`
- `src/hotspots.py`
- `src/load_boundaries.py`
- `src/load_population.py`
- `src/load_vahan.py`
- `src/make_map.py`
- `src/resolve_districts.py`
- `src/utils.py`
- `src/validate_chargers.py`
- `tests/conftest.py`
- `tests/test_pipeline.py`
- `tests/test_resolver.py`
- `tests/test_scores.py`
- `tests/test_slice1.py`

## 2026-10-27 - Collect official source tables directly

- Collected MoRTH's district/category annual EV registrations from Lok Sabha
  answer 4552 (19 March 2026), preserving 2025 observation meaning and sources.
- Added a real committed fallback: 37 district rows, 26 complete totals;
  ambiguous PDF cells leave 11 districts missing rather than guessing.
- Collected 38 official 2022 population estimates from Tamil Nadu DES; retained
  them as candidates only because boundary compatibility is not verified.
- Cached source extracts in raw and added committed text snapshots for
  reproducibility. Added import_public_tables.py and five offline tests.
- Carried EV observation year/measure/source through scoring and onto the map.
- Added configurable generic article normalisation without spelling aliases.
- Fixed Folium serialization of GeoJSON-inferred source-date timestamps and
  added a regression case with source-date metadata.
- Verification: 41 tests passed, 1 PySAL integration test skipped because the
  dependency install remains blocked. See feasibility.md for current coverage.

Additional/updated files for this data-collection change:
`src/import_public_tables.py`, `src/config.py`, `src/utils.py`,
`src/load_vahan.py`, `src/build_scores.py`, `src/make_map.py`,
`tests/test_public_tables.py`, `tests/test_pipeline.py`, `README.md`,
`CHANGES.md`, `outputs/feasibility.md`,
`data/samples/vahan_tn_ev_by_district.csv`,
`data/samples/population_official_estimates_candidate.csv`, and the three
JSON source-text snapshots in `data/samples/official_sources/`.

## 2026-10-27 - National pipeline

Added run_india.py, national binary extraction and fingerprinted cache,
dataset-ID input audits, synthetic gating, geodesic deduplication,
district-local road calculations, supply coverage map and source manifest.
Added safe streamed current-snapshot refresh and offline regression tests.
State outputs remain available. National EV/population inputs stay missing.
Files: .gitignore, requirements.txt, src/config.py, src/dedupe_chargers.py,
src/extract_india.py, src/india_data.py, src/pbf_reader.py, src/refresh_india.py,
src/make_map.py, run_india.py, tests/test_india.py, README.md, CHANGES.md,
outputs/feasibility.md and the two national input templates.
