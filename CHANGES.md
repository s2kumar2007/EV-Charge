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

## Google Maps link integration and external verification retry

- Added configurable, API-key-free Google Maps search/directions links from
  actual charger coordinates, URL encoding, safe external-link attributes
  and a regression test. Regenerated the national map.
- Retried PySAL installation: public package downloads were observed, but
  installation into the Windows user-packages directory was denied. The
  repository-local retry and cache recovery did not supply usable wheels.
- Retried the national extract, map assets and official Census workbook:
  direct requests timed out. No successful live refresh or offline-library
  verification is claimed. National missing values remain missing.
- Changed .gitignore, src/config.py, src/map_links.py, src/make_map.py,
  tests/test_india.py, README.md, CHANGES.md and outputs/feasibility.md.

## 2026-10-27 - Population compatibility, cached indicators and acceptance

- Part A was stopped at its dependency blocker: original PDF exists, but
  pdfplumber cannot be installed and pdftotext is absent. EV CSV unchanged;
  26 complete/11 missing, with no guessed cells or unperformed checks claimed.
- Added a source-spelling population crosswalk: 33 exact-name polygons accepted;
  five population rows need human review. Non-exact proposals stay unverified;
  reviewed many-to-one populations sum only when every contributor is approved
  and present. Duplicated source rows cannot split a population.
- Added the annual-new-registration/2022-population indicator label.
- Added configurable state-cache -> national-cache -> live Overpass source order,
  matching-PBF provenance checks, state/district clipping, district-local CRS
  calculations and source/snapshot/cache columns. All 37 state districts now
  have road and commercial observations from 2026-10-25T21:21:21 UTC.
- Added a standalone HTML script/link asset cache, non-empty validation,
  duplicate reuse and explicit retained failed URLs. MAP_OFFLINE_MODE=False;
  MAP_TILES=None removes basemap tiles. Actual asset downloads remain blocked.
- Added explicit pinned_repo/geoboundaries provider selection for both runners,
  ADM2/ADM1 metadata/download attribution, representative-point state selection
  and provider comparison. Default remains pinned_repo; real alternative
  downloads/comparison remain blocked. Pinned personal-usage/no-licence risk
  is documented. ADM1 and ADM2 licences are retained separately.
- Added run_acceptance.py with observed counts, source dates, EV meaning/year,
  population status, ranks, actual statistic sample sizes, map asset checks,
  synthetic checks and concrete manual tasks. Actual result is PARTIAL.
- Missing PySAL now leaves explicitly untested statistics while allowing maps
  and acceptance to finish. State run: 26 basic ranks, 23 composite ranks,
  220 raw/216 merged chargers, no synthetic data; Moran/Gi* n used = 0.
- 75 offline tests pass; 1 real PySAL integration test is skipped. Updated
  README/feasibility and ignored local logs/intermediate download files.
- Commits were attempted but .git/index.lock writes are denied by this runtime.
  No Git identity was changed and no assistant attribution was added.

Changed/new repository files for this stage:
.gitignore, requirements.txt, README.md, CHANGES.md, outputs/feasibility.md,
data/samples/district_crosswalk.csv, run_acceptance.py, run_india.py,
src/boundary_sources.py, src/cache_map_assets.py, src/config.py,
src/fetch_indicators.py, src/gap_index.py, src/hotspots.py, src/india_data.py,
src/load_boundaries.py, src/load_population.py, src/make_map.py,
tests/test_acceptance.py, tests/test_boundary_sources.py,
tests/test_compatibility.py, tests/test_indicator_sources.py,
tests/test_map_assets.py, tests/test_pipeline.py, tests/test_slice1.py.

## Native India Google Maps integration

- Added a Maps JavaScript API national view using the existing real national
  polygon, indicator and station outputs; 735 polygons and 575 assigned merged
  stations in the supplied snapshot. Missing national EV/population stays missing.
- Added district/ID search, district and station toggles, configurable indicator
  styling, source popups, directions links and explicit API/auth failure messages.
- Stored the user key only in ignored .env. All settings are in config.py;
  .env.example contains a blank placeholder. No key enters tracked source,
  documentation, generated manifests or commit messages. The rendered ignored
  HTML uses a browser key and needs HTTP-referrer/API restrictions.
- Integrated optional generation into run_india.py and added --google-map-only
  to render existing national outputs without repeating extraction/providers.
- Added fake-data/key offline tests for null preservation, ID validation,
  safe script embedding, coordinate errors, file generation and credential logs.
  Generated inline JavaScript passes node --check. Actual browser/API access
  remains unverified because the in-app browser cannot reach the local preview.
- Retried staging and commit after focused tests; .git/index.lock creation is
  still denied. No commits were created and no Git identity was changed.

Files for this Google Maps increment: .env.example, src/config.py,
src/make_google_map.py, src/google_map_template.html, run_india.py,
tests/test_google_map.py, tests/test_india.py, README.md, CHANGES.md,
outputs/feasibility.md. The actual .env and generated outputs stay ignored.

Google Maps final validation: 83 passed, 1 skipped (PySAL integration), Node
syntax and offline fake-Google UI tests passed, and git diff --check passed.
Credential scan: supplied key absent from every trackable file; .env and
generated HTML confirmed ignored. Live Google API auth remains unverified.

## Reconnect follow-through: guarded PDF recovery and national acceptance

- Added complete_ev_counts.py: pdfplumber word-position/cell extraction;
  pdftotext -layout fallback; raw coordinate/unit/backend/hash audits;
  original-measure/category/year gates; baseline, duplicate and printed-total
  checks; missing-cell preservation; and atomic CSV replacement after checks.
- Added ten fake-data offline tests, including an unknown-district regression
  that prevents inheriting the preceding district's values. The real command
  stops safely on missing pdfplumber and Windows error 623 from pdftotext.
- Centralised the original EV measure label in config; no EV CSV values changed.
- Added run_acceptance.py --scope india, national provider comparison option,
  scope-specific labels/manual commands and a browser-key non-disclosure test.
  National demand coverage is explicitly 0/735; supply observations remain real.
- Recorded national source candidates without promoting unverified values,
  licensing or RTO geography. Attempts to retrieve supplied file contents and
  all eleven map assets failed; no successful retrieval is claimed.
- Full suite: 95 passed, 1 PySAL integration skip. Whitespace checks pass.
  Browser validation stopped at Computer Use's URL-policy enforcement failure.
  Git commit retry remains denied; no identity or permissions were changed.

Files in this increment: src/complete_ev_counts.py,
tests/test_complete_ev_counts.py, src/import_public_tables.py, src/config.py,
run_acceptance.py, tests/test_acceptance.py, src/load_boundaries.py,
data/samples/official_sources/national_source_candidates.json,
README.md, outputs/feasibility.md and CHANGES.md.


## 2026-10-27 - Local source files and resilient national map

- Read the three supplied originals. Prepared 640 Census 2011 district
  candidates with a printed India-total check and unverified polygon suggestions.
  The 36-row state directory supplies no district counts. Audited the EV CSV's
  category/fuel totals; its 5,178,162 total has no district rows and is not imported.
- Added an inline SVG national fallback with polygons, stations, search, details,
  indicator colours, zoom/pan and toggles. Google failures retain the local view.
  Added `python run_map.py` to start a persistent server from the user's terminal.
- Fixed generic Unicode accent normalization for ADM1 transliterations.
  State comparison completes: 37 pinned vs 38 geoBoundaries districts.
  Default remains pinned; national provider files are still missing.
- Verified both Folium maps have nonempty local JS/CSS assets (11 libraries each).
  Tiles remain online; Google browser/API authorization is still unverified.
- Original PDF word reader: 17 existing totals verified, nine unverified.
  Stopped without changing EV CSV rows; raw cells/coordinates and a STOP
  receipt are retained. State rerun retains 23 composite ranks.
- Offline regression suite: 104 passed, 1 skipped (real PySAL Gi* integration).
