# ChargeGap India - Slices 0 and 1

Techfest 2026-27, IIT Bombay: EV infrastructure mapping for India, with the original state pipeline preserved.

State entry point: `python run_all.py --offline`. Review the current result with
`python run_acceptance.py` and open `outputs/tn_gap_map.html`.
National entry point: `python run_india.py --offline`, after caching the chosen
boundary provider. `BOUNDARY_PROVIDER="pinned_repo"` is the explicit default
for both runners. To use the supplied geoBoundaries provider nationally, set
`BOUNDARY_PROVIDER="geoboundaries"` and first cache its metadata/downloads online;
the old root GeoJSON is not silently treated as the current release.

Current verification: **104 passed, 1 skipped**. State run: **37 polygons,
220 raw chargers, 216 merged stations, 26 basic ranks, 33 accepted populations,
37 road/commercial observations, 23 composite ranks**. No synthetic data.
Acceptance is **PARTIAL**: PDF baseline verification, PySAL, national boundary
comparison and Google browser authorization remain incomplete. Folium JS/CSS
assets are now cached and the state provider comparison completes. See `outputs/feasibility.md`.

Python 3.10+. This is a map and an auditable district comparison, with no
forecast, optimiser or dashboard. All editable source URLs, state settings,
thresholds, colours, weighting judgments and seeds are in `src/config.py`.
No spelling tables or district lists are embedded in the calculation code.

## Install and run (PowerShell)

The Git repository is the **inner** `chargegap` directory. If starting from the
outer workspace, first run `cd .\chargegap`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Optional: copy .env.example to .env and add your own free OpenChargeMap key.
.\.venv\Scripts\python.exe run_all.py --refresh
.\.venv\Scripts\python.exe -m pytest -q -rs
Start-Process .\outputs\tn_gap_map.html
```

Other commands, from the same directory:

```powershell
python run_all.py --slice 0    # original raw-record Slice 0 outputs only
python run_all.py              # both slices, reusing cached downloads
python run_all.py --refresh    # fetch current data; boundaries remain pinned
python run_all.py --offline    # prohibit network calls; use existing caches
python tests/test_resolver.py
python tests/test_scores.py
python tests/test_slice1.py
python src/validate_chargers.py outputs/validation_sample.csv
```

`--refresh` and `--offline` are mutually exclusive. Network failures are retried
and named. A required step failure exits with status 1 and its step label.
Unavailable optional indicators remain missing with a printed warning. No
substitute counts or substitute hotspot statistics are invented.

The Python pipeline runs offline from cached inputs. `MAP_OFFLINE_MODE=False`
by default; set it to `True` to cache external script/link resources next to the
map, or run `python src/cache_map_assets.py outputs/tn_gap_map.html` online.
Each URL is downloaded once with retries, checked for non-empty bytes and
rewritten to a relative `assets/` path only on success. Failed URLs stay online
and are printed. Keep `outputs/assets/` beside the HTML. The asset receipt
records remaining external URLs; acceptance rechecks the actual HTML and files.
Tiles remain online; `MAP_TILES=None` removes the basemap. CSS fonts/images
can still require internet; this feature caches external script/link files,
not every resource referenced within CSS. Browser visual verification is pending.

## Open the national map and inspect supplied data

Run `python run_map.py` in your own PowerShell from this repository and keep
that terminal open. It opens `http://127.0.0.1:8000/india_google_map.html`.
Connection refused means the server is absent; it is not a Google API error.
The agent runtime could start a server, but its browser and HTTP client could
not connect to localhost, so a successful browser render is not yet claimed.

The HTML now draws its 735 district polygons and 575 mapped stations with a
local SVG view before Google loads. It supports district search, indicator
colours, details, visibility switches, wheel zoom, drag and reset without a
CDN. Google replaces it when available; Google load or authorization failure
keeps the local view. Missing values remain grey and unranked. The fallback
has no Google basemap; API authorization still needs browser verification.
Regenerate with `python run_india.py --google-map-only --offline` after changes.

The three originals in `data/raw/supplied_user_files/` are now readable.
Run `python src/import_supplied_data.py` to repeat the audit:

- Census workbook: 640 district totals, year 2011, population sum 1,210,854,977,
  equal to its printed India total. Rural/urban rows are excluded. Candidates
  and unverified polygon-name suggestions are saved under `data/raw/`; none
  attach to newer polygons without geography review.
- State workbook: 36 state/UT directory rows; no district population or EV counts.
- EV CSV: combined 2025-2026 fuel/category table, printed total 5,178,162.
  Category rows and fuel totals reconcile; district rows = 0. It cannot supply
  district demand ranks or the state's annual 2025 registration measure.

National EV and accepted population coverage remain 0/735. Obtain uniform
 district-level registration rows with explicit period/categories and review
Census-to-polygon geography. Never disaggregate a national total. The report
`outputs/india/supplied_data_audit.json` records source hashes and findings.
Original files, credentials and generated maps stay ignored.

## What you must supply or review by hand

1. The original PDF now extracts with pdfplumber word coordinates. The baseline
   check passes 17 existing totals but cannot verify nine: Chengalpattu, Erode,
   Kancheepuram, Krishnagiri, Nagapattinam, Pudukkottai, Salem, Theni, Viluppuram.
   Extraction stopped and preserved every original CSV row. Review the original
   PDF against `data/samples/official_sources/public_ev_pdf_cells.json` and
   `public_ev_pdf_checks.json`; do not replace values until all 26 baseline
   totals verify. Then run `python src/complete_ev_counts.py` and the state
   pipeline. Eleven missing districts remain missing.
2. Review `data/samples/district_crosswalk.csv`: **Sivagangai, Thoothukudi,
   Kanniyakumari, Tiurupathur, Mayiladuthurai**. Only exact normalised names are
   `one_to_one`. Other rows are `needs_human_check`; fuzzy/geocode destinations
   are suggestions, not verified geography. A reviewed non-exact mapping must
   use `many_to_one`, `verified=yes`, a polygon name and documentary evidence.
   Multiple contributors must all be approved before their populations are
   summed; one source row can never be split. Missing contributors leave the
   aggregate missing. The initial crosswalk accepts 33 of 37 polygons; four
   polygons are missing population and Mayiladuthurai has no resolved polygon.
   Exact spelling alone still does not establish historical geography.
3. Install `python -m pip install libpysal esda` in a connected terminal, rerun
   `python run_all.py --offline`, then `python -m pytest -q`. The current Gi*
   integration test is skipped. The real run has 23 eligible districts but
   **0 actually used** for Moran/Gi*: no substitute statistics were generated.
4. Both Folium maps now have all 11 JS/CSS dependencies cached; keep each
   `assets/` directory beside its HTML. Basemap tiles still need internet.
   Regenerating a map with MAP_OFFLINE_MODE=False requires recaching its assets.
5. With internet run `python src/load_boundaries.py --compare`. Both release
   metadata and files named by `gjDownloadURL` are required for ADM2 and ADM1.
   State comparison succeeds: pinned 37 versus geoBoundaries 38. Only pinned:
   Chengalpattu, Kanyakumari, Nilgiris. Only geoBoundaries: Chengalputtu,
   Kanniyakumari, Mayiladuthurai, The Nilgiris. Name differences are not proof
   of equal geometry. National comparison still needs missing pinned state files;
   run `python src/load_boundaries.py --compare --national` online. The default
   remains pinned.
   Review boundary accuracy, coverage, historical year and redistribution rights.
6. Review charger merges in `outputs/validation_sample.csv` and provisional
   AHP judgments. Preserve review files; the pipeline writes a new timestamped
   sample instead of erasing existing answers. Rerun `python run_acceptance.py`.
7. Commits could not be created: this runtime denies `.git/index.lock` writes.
   In your own terminal, after review run `git add .` and
   `git commit -m "feat: add population compatibility and source acceptance checks"`.
   The existing Git identity is left unchanged; no assistant attribution is added.

## Sources, licences and live fetching

| Input | Download/source | Licence and cautions |
|---|---|---|
| District polygons | [udit-001/india-maps-data](https://github.com/udit-001/india-maps-data), exact commit and state slug in config | No explicit dataset licence found; README says collection "for personal usage". Verify permission before redistributing the geometry. New districts may be missing. |
| Chargers, roads, commercial nodes | [OSM Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API), one primary and two fallback servers | [OSM contributors, ODbL](https://www.openstreetmap.org/copyright); public service capacity is limited. Query box is calculated from polygons. |
| Optional charger records | [OpenChargeMap](https://openchargemap.org/site/develop/api), only with `OCM_API_KEY` | Free developer access; retain attribution and check the data provider's individual terms. Current developer/terms pages may require login. Not required for the default run. |
| Name geocoding | [OSM Nominatim](https://nominatim.openstreetmap.org) | ODbL; see [mandatory usage policy](https://operations.osmfoundation.org/policies/nominatim/). Single thread, cached answers, identifying User-Agent, at most one request per second. Intended for a small one-time district/RTO reconciliation, not scheduled bulk geocoding. |
| Population candidate | [IndiaSet Census 2011](https://huggingface.co/datasets/indiaset/census-2011) | Publisher labels compilation CC-BY-4.0, derived from Census of India 2011. Citation: Jaiswal, Ansuman (2026), *India Census 2011 - District Level*. Historic geography is not silently applied to newer polygons. |
| EV registrations | [MoRTH Lok Sabha answer 4552, 19 March 2026](https://sansad.in/getFile/loksabhaquestions/annex/187/AU4552_wCyeso.pdf?source=pqals), or user VAHAN export | Official 2025 annual-registration table collected as a partial real fallback. Not a live feed or fleet total. Retain attribution; explicit redistribution licence has not been established. |

Population downloads use Hugging Face's documented free
[`/rows` API](https://huggingface.co/docs/dataset-viewer/rows), paginating the
published Parquet dataset into cached JSON without a paid API or a Parquet
runtime dependency. URL, citation, column names and licence are editable in
config. A failed download prints the manual `population.csv` alternative.
The dataset itself is a 2011 census snapshot, not live population measurement.

Cache files live in `data/raw/`. New Overpass caches are query-fingerprinted;
new downloads record endpoint, UTC timestamp and query fingerprint. API keys
are excluded from cache metadata and error messages. A legacy Slice 0 charger
cache can still be read, with an explicit unknown-date/provenance warning.
Use `--refresh` online to replace it. Cached readings are not called live data.

## VAHAN file format and safety

The committed `data/raw/vahan_tn_ev_by_district_TEMPLATE.csv` contains headers
only. Use a `district` **or** `rto` column and `ev_total`, or the vehicle-type
columns `two_wheeler,three_wheeler,four_wheeler,bus`. `population` and
`data_flag` are optional. A supplied total takes precedence over component
sums. Missing totals are calculated from supplied type columns; do not omit
categories accidentally. Negative/infinite totals are rejected.

If the raw file is absent, `VAHAN_SAMPLE_FILE` selects an optional committed
sample in `data/samples/`. The collected real fallback is an official 2025
annual-registration snapshot, not a current or cumulative VAHAN export.
Districts without EV counts stay empty and unranked, even if chargers exist.
Zero EVs are an observation; missing EVs are not zero. Rows assigned to one
district have their EV totals added. A repeated population is taken once
(maximum), not added across RTOs; conflicting office populations require review.
Flags are retained; any synthetic input row makes the district synthetic.

District resolution: exact letters-only key -> unambiguous difflib match ->
geocoded point inside one polygon. RTOs remove bracket details, registration
codes and office labels, then use exact -> geocode -> fuzzy. Cutoff and the
minimum difference between first and second fuzzy matches are in config.
Ambiguous/shared-border geocodes remain unresolved. Every non-exact match is
printed and audited. Boundary keys must be unique.

`ALLOW_SYNTHETIC` and `USE_SYNTHETIC_TEST_DATA` are both **False** by default.
Only the explicit test-data switch permits the named `SYNTHETIC_TEST` sample;
its rows are forcibly synthetic even if a file incorrectly claims otherwise.
Missing-value generation, if explicitly enabled, uses the min/max of observed
non-synthetic totals and a fixed seed. Synthetic districts have dashed map
outlines and visible warnings: **SYNTHETIC TEST DATA IN USE - do not use these
results in the submission.** No test-generated counts are used by default.

## Slice 0: basic charging gap

`gap_score = ev_total / units`, where `GAP_UNIT` selects stations (default)
or ports. An absent/invalid/zero/negative/noninteger capacity becomes one
assumed port with `ports_known=False`. Otherwise OSM `capacity` or OCM
`NumberOfPoints` supplies the known positive integer.

With no chargers, `NO_CHARGER_POLICY="smoothed"` uses EVs / max(units,1).
The optional `"first"` policy ranks zero-charger districts first; their ratio
is undefined, not infinity written into CSV. Among ordinary scores, higher
means more underserved. EV-missing districts get no rank. CSV ranks are
nullable integers. Ties use EV totals and an alphabetical district tie rule.

Points on a shared border go to the first sorted district key, once only.
Inside + outside must equal fetched; raw and deduplicated joins each preserve
that identity. Outside-box-neighbour records are kept in unassigned audits.
The Slice 0 file and map layer intentionally retain raw counts; duplicate
records are a known Slice 0 limitation. Slice 1 corrects its selected counts.

## Slice 1A: deduplication and confidence

Coordinates are projected to `estimate_utm_crs()`, never a fixed state CRS.
Distance-connected components are equivalent to DBSCAN with min_samples=1.
Within each component, records merge only when **all** pairs pass the radius
and label rules: conflicting known operators block a merge; two known names
must meet the name threshold; matching known operators can join a missing
name; otherwise a tighter configured distance is required. Complete pair
checks prevent a chain of near points swallowing a distant station.

The merged coordinate is the mean projected point, transformed to WGS84.
Sources are a JSON list. Ports use the **maximum known** count, never a sum;
without known counts the assumption is one, flagged unknown. The audit
identifies each member by source and source ID. Same source IDs are rejected
as an input integrity error.

Confidence is a documented heuristic, not a calibrated probability:

```
source_component = min(number_of_distinct_source_labels / source_target, 1)
name_component = 1 if a name exists else 0
operator_component = 1 if an operator exists else 0
ports_component = 1 if at least one port count is known else 0
spread_component = max(0, 1 - max_distance_from_centre / radius)
confidence = sum(config_weight[c] * component[c]) / sum(config_weight[c])
```

All five editable weights default equally in config; radius defaults to 40 m.
They are visible assumptions needing validation, not measured truths. OCM can
copy OSM, so different source labels do not guarantee independent field
observations. Inspect `dedup_radius_sensitivity.csv` before justifying a radius.
`DEDUP_ENABLED=True` selects merged counts for Slice 1 and reports raw counts
beside them; Slice 0's earlier files remain intact.

## Slice 1B: composite index and rank uncertainty

The four columns and their provenance are saved in `gap_index_methods.json`:

| Indicator | Formula | Direction |
|---|---|---|
| `ev_pressure` | Slice 0 formula using the selected Slice 1 station/port counts and zero-unit policy | Higher unmet demand |
| `evs_per_100k` | EVs / compatible population * 100000 | Higher adoption pressure |
| `road_km_per_km2` | Clipped OSM trunk/primary way km / polygon km2 | Higher corridor-demand proxy |
| `commercial_per_km2` | Distinct OSM shop or fuel/restaurant/marketplace **nodes** / polygon km2 | Higher activity-demand proxy |

Commercial activity intentionally counts nodes only. It is a reproducible OSM
proxy, not a complete business census or a deduplicated business count.
Roads are projected, clipped to each district and coincident segments unioned.
A successful complete OSM answer with no matching features means observed
count zero; a failed/partial answer or absent declared district coverage means
missing. `INDICATOR_SOURCE_ORDER` selects state query-fingerprinted Overpass
cache, matching national extract cache, then live Overpass. Each indicator
records its source, cache and snapshot date; unknown dates are flagged.
Roads are clipped at the state/district border and measured in each district
local UTM CRS chosen automatically. All directions are positive; no indicator is inverted.
Grid headroom is **not included**, because no suitable public district dataset
was supplied. Greater road/activity density expresses demand, not measured
charging utilization or confirmed electrical capacity.

Only districts complete on **all four indicators** fit scaling and receive
scores. Others retain their values and a `missing_indicators` list, without
imputation. The default scale is `(x-min)/(max-min)`. Optional robust scaling
clips at the configured empirical quantiles before that transformation.
Constant columns become zero and receive zero entropy weight.

For scaled nonnegative values `s_ij`, `p_ij=s_ij/sum_i(s_ij)`;
`e_j=-sum_i(p_ij*ln(p_ij))/ln(n)` with `0*ln(0)=0`;
`w_j=(1-e_j)/sum_j(1-e_j)`; composite = `sum_j(w_j*s_ij)`.
Constant columns explicitly have diversity zero. With fewer than two complete
districts or no informative columns, entropy ranking is undefined and left
empty rather than replaced by invented weights.

AHP uses the principal eigenvector of the positive reciprocal matrix in
config. The default all-ones matrix produces equal weights and **needs expert
input**. Saaty's consistency ratio is reported; inconsistent matrices are
rejected. Both scores/ranks are saved. Spearman compares scores using average
ranks for ties, avoiding artificial correlation from alphabetical tie breaks.

Sensitivity samples 1000 Dirichlet weight sets centred on entropy weights,
with configurable concentration/seed; zero-information columns remain zero.
Every district gets minimum, maximum, median rank and share of draws within
TOP_K. Scales and complete-district membership stay fixed during these draws.
These are scenarios for weight uncertainty, not probabilities of actual
infrastructure need. Exact score ties use district keys deterministically.

## Slice 1C: spatial statistics

PySAL `libpysal` Queen contiguity uses shared vertices/edges. Global Moran's I
uses row-standardised neighbours and seeded permutations; expected I and
permutation p-value are saved. Gi* uses `esda.G_Local(star=True)`: it adds a
self weight equal to a Queen neighbour before row standardisation. Missing
index values and districts without neighbours among complete observations
are explicitly excluded, without constructing replacement links.

The Gi* z-score determines high/low direction. PySAL's folded permutation
p-value is retained; the reported two-sided p-value is min(2*p_folded,1).
Raw classes use configurable 90/95/99% thresholds. Benjamini-Hochberg adjusted
p-values and corrected classes are also saved; the map uses corrected classes.
Undefined local variance is not tested. Constant/all-missing indices cannot
produce a spatial statistic. **Few districts make these results indicative,
not conclusive**; the 3x3 test verifies a toy pattern, not real-world validity.

## Outputs and file responsibilities

| File | Purpose |
|---|---|
| `outputs/district_gap_scores.csv` | Original Slice 0 raw-count scores, nullable integer ranks |
| `outputs/tn_gap_map.html` | Original gap layer plus composite, Gi*, confidence-point toggles |
| `outputs/district_gap_scores_deduplicated.csv` | Selected Slice 1 counts and raw per-district comparison |
| `data/processed/chargers_raw.csv` | Fetched source records, no merging |
| `data/processed/chargers_assigned.csv`, `chargers_unassigned.csv` | Original raw point assignments and outside records |
| `data/processed/chargers_deduplicated.csv` | Merged stations, source list, spread and confidence components |
| `data/processed/chargers_merge_audit.csv` | Source IDs assigned to each merged station |
| `data/processed/chargers_deduplicated_assigned.csv`, `chargers_deduplicated_unassigned.csv` | Selected merged point assignments |
| `outputs/dedup_radius_sensitivity.csv` | Radius versus station count, including outside points |
| `outputs/validation_sample.csv` | Seeded sample for human checking; later files are timestamped |
| `data/processed/district_population.csv`, `district_osm_indicators.csv` | Indicator inputs and population provenance |
| `outputs/district_gap_index.csv` | Indicators, both weighting scores/ranks, missing flags and stability |
| `outputs/gap_index_sensitivity.csv` | Rank range, median and top-K share |
| `outputs/gap_index_methods.json` | Sources, scales, weights, AHP consistency and Spearman |
| `outputs/district_hotspots.csv`, `hotspot_statistics.json` | Local raw/FDR results and global Moran summary |
| `outputs/feasibility.md` | Current verification, data gaps and release limits |

`checks.py` reconciles both counts and lists flags, matches, top/best-served
districts, deduplication counts/confidence, radius results, excluded composite
districts, rank ranges and Moran's I. `run_all.py` prints every step and stops
on a named required failure. `.env`, virtual environments and caches are
ignored; samples and the header-only template stay tracked.

## Tests and present feasibility

Tests use invented in-memory inputs and fake network/geocoder functions;
pytest blocks real requests. Temporary generated files stay inside the repo's
ignored `.test_tmp/`. All original scoring tests are retained. The resolver
suite no longer downloads boundaries. Added cases cover deduplication, ports,
confidence, entropy, AHP, seeded ranks, missing values, road clipping, population
safety, FDR, validation precision, cache/retry rules and map output contracts.
The true PySAL 3x3 integration test is skipped **only** if its dependencies are
missing; install requirements to run it, and do not count a skip as validation.

See `outputs/feasibility.md` for the actual test results and live-fetch limits
of this development environment. A generated all-missing map proves the
pipeline handles missing inputs; it does not demonstrate EV demand rankings.

## Limitations before a jury or publication

- OSM coverage is incomplete and does not guarantee public access, working
  status, charging speed, real capacity, or station independence.
- Deduplication is heuristic; nearby distinct stations or copied source data
  can mislead it. Review the audit and sample. Unknown ports remain assumptions.
- District-level aggregation hides within-district access gaps and travel time.
- Historical population, registration windows, modern boundaries and OSM
  timestamps must be aligned; no automatic district split allocation is made.
- Entropy weights reward variation, not causal importance. Complete-case
  exclusions and correlated indicators can bias the apparent priorities.
- Radius/weights are editable modelling assumptions; sensitivity is not
  external validation. Hotspots have low power with small samples.
- Boundary data rights and current geometry accuracy require verification.
- Grid headroom, actual utilization, traffic, charger uptime and future demand
  are absent. No forecasts or engineering deployment recommendations follow.


## Official data collected on 27 October 2026

`data/samples/vahan_tn_ev_by_district.csv` contains the collected official
2025 annual-registration table. Its `ev_total` sums only source categories
with unambiguous numeric separators. If any category has ambiguous cells,
that district's total stays blank. There are 37 source districts, 26 complete
totals (141,606 registrations across those 26 only) and 11 exclusions; **this
sum is not a statewide total**. All source district names resolve; the one
fuzzy match is logged. Generic leading articles are normalised by a configured
rule, with no district-specific spelling list.

The complete retrieved source text is cached in `data/raw/` and reproducible
text snapshots are committed in `data/samples/official_sources/`. The actual
PDF bytes were not downloaded; these files are web-retrieved PDF text, clearly
labelled as such. Rebuild the collected tables with:

```powershell
python src/import_public_tables.py
python run_all.py --offline
```

`data/processed/public_ev_category_extraction_audit.csv` records each original
category cell and its extraction status. `outputs/data_collection_manifest.json`
records the source URLs, coverage and limitations. Original source PDF page
images were not available as actual image bytes through the retrieval tool;
ambiguous cells have not been manually guessed or treated as zero.

`data/samples/population_official_estimates_candidate.csv` contains 38 official
**2022 mid-year population estimates**, collected from the Tamil Nadu DES
Statistical Handbook 2022-23, table 2.1 (printed page 84):
https://des.tn.gov.in/sites/default/files/2025-07/2.VITAL%20STATISTICS.pdf.
These are official estimates, not synthetic values generated by the project
and not Census 2011 enumeration. They attach only through the crosswalk rules
above: newer district splits and expanded districts can differ from the
pinned polygon geography. Source spelling is preserved. The handbook's
explicit redistribution licence has not been established; do not re-label it
as CC-BY-4.0. The previously documented IndiaSet source remains a separate
historic candidate.

Current direct Python downloads still fail DNS resolution. The web retrieval
route collected these official tables, but could not retrieve Overpass JSON.
Live charger refresh remains unavailable here. Roads and places now come
from the national cache, dated 2026-10-25T21:21:21 UTC, clipped to the state.
The map uses existing charger observations, 26 historical basic ranks and
23 complete-case composite ranks. This is a partial real-data run,
not proof that every requested source or live service has been validated.

## India-wide build

Set the intended `BOUNDARY_PROVIDER` explicitly and cache it online before
`python run_india.py --offline` using the supplied India PBF. The pinned
provider downloads its commit-specific file listing and all state files;
geoBoundaries downloads ADM2 through its metadata. The national loader uses
the same provider setting as the state loader. Provider changes require
reviewing national population/EV IDs again. Open outputs/india/india_gap_map.html.
Run `python run_india.py --download-latest` to stream the current free
Geofabrik extract before processing; network access is required. Interrupted
refreshes preserve the previous validated file. `--refresh` re-extracts a
local snapshot. This is snapshot refresh, not live charger uptime or VAHAN.

State outputs remain unchanged. National outputs are under outputs/india and
data/processed/india. The Southern Zone extract overlaps India and is excluded.
Supply coverage is displayed even when EV/population inputs are missing.
No demand rankings or substitute statistics are invented.

National inputs: data/raw/vahan_india_ev_by_district.csv and population_india.csv.
Generated header-only templates specify the required columns. Use polygon IDs
from outputs/india/district_directory.csv, source_url, observation_date and
boundary_compatible=true only after checking geography. EV inputs also require
ev_measure, period_start, period_end. Mixed periods, duplicate IDs, invalid
numbers and unverified geography are rejected or audited. District names are
not unique nationally; dataset IDs are not official LGD codes.

PBF extraction caches use source SHA-256 and reader version. The reader handles
nodes/dense nodes, ways and charger relations, failing explicitly on unsupported
nested relations or incomplete coordinates. National deduplication uses 3D
Earth-centred candidates and ellipsoidal distances. Road/area calculations use
each district's estimated local UTM zone. Only map geometry is simplified.

The run manifest records source hashes, actual OSM header timestamp, counts and
missing-data coverage. Audit outputs include merge membership, radius
sensitivity, validation sample, rejected inputs, roads/POIs, composite sensitivity
and hotspot statistics. Review merges manually before claiming accuracy.

The supplied boundary file has 735 polygons. Retrieved geoBoundaries metadata
describes 2021 geography, lists 736 units and specifies ODbL 1.0. Review that
coverage discrepancy before presenting complete current district coverage.
Sources and configurable URLs: geoBoundaries India ADM2 metadata, Geofabrik
India downloads, and the OpenStreetMap PBF format specification. OSM is ODbL.
National EV/population totals are still separate, unavailable inputs here.

## Google Maps links and remaining external inputs

Charger popups now offer Open in Google Maps and Directions. These use the
existing OSM/OCM coordinates and Google Maps URLs, without an API key or paid
API calls. They open only when clicked. Toggle GOOGLE_MAPS_LINKS_ENABLED in
src/config.py; endpoints and travel mode are editable there.

An embedded Maps JavaScript API map and Places API require credentials and
billing. Places data has storage/display restrictions and is not used as a
cached source for this OSM analysis. Google Maps does not replace district
EV registration or population data. Documentation checked:
https://developers.google.com/maps/documentation/urls/get-started
https://developers.google.com/maps/documentation/javascript/usage-and-billing
https://developers.google.com/maps/documentation/places/web-service/policies

The official national Census 2011 workbook URL is now recorded in config.
It remains historical candidate geography, not automatically compatible with
the supplied 2021 district polygons. RTO data also needs a verified administrative
crosswalk; office-point geocoding cannot establish a catchment population.

## Boundary provider and rights

The pinned repository README describes collection **"for personal usage"**
and names **no data licence**. This is an unresolved redistribution risk,
not permission to redistribute. The current network cannot independently
re-fetch that README; the warning preserves the supplied source description.

`BOUNDARY_PROVIDER` defaults to `"pinned_repo"`; choosing `"geoboundaries"`
is explicit and affects both runners. The alternative downloads and preserves
ADM2/ADM1 metadata JSON, the exact `gjDownloadURL` files, SHA-256 receipts and
attribution text under `data/raw/geoboundaries_IND_*`. ADM2 has no state column:
select the configured state in ADM1 by exact normalised name, then retain
ADM2 polygons whose representative points lie inside it. Do not derive state
membership from a district spelling table or fuzzy state guesses.

Retrieved metadata identifies ADM2 as 2021 geography under ODbL 1.0 and ADM1
as 2011 geography under CC BY 2.5 India. Preserve both licences and consider
their different years. Metadata endpoints:
https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/ and
https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/ .
`python src/load_boundaries.py --compare` prints both counts and exact source
names present in only one provider, saving the comparison JSON if successful.
Downloads and the actual spatial comparison are blocked in this environment;
no alternative state district count is claimed.

## Acceptance report

`python run_acceptance.py` reads actual output files and prints PASS / PARTIAL /
FAIL, including source/snapshot dates, raw/merged known-port counts, EV measure
and year, population coverage, basic/composite ranks, actual spatial-statistic
sample sizes, missing map assets, synthetic use and manual tasks. It writes
`outputs/acceptance_report.json`. Missing evidence is PARTIAL; synthetic data
or impossible charger counts FAIL. It does not infer success from implemented
code or invent missing measurements. `outputs/feasibility.md` is the committed
record of the current run; generated maps, caches and reports stay ignored.

## Native Google Maps view for India

A native Maps JavaScript API view is available in addition to Folium. The
current saved national output contains 735 district polygons and 576 merged
OSM station records; 575 assigned stations are displayed by default. The
unassigned station remains in its audit. This is coverage of the supplied
boundary snapshot, not a claim of every current district or operating charger.
National EV/population inputs remain missing and demand ranks remain empty.

The provided key was stored only in ignored `.env` as `GOOGLE_MAPS_API_KEY`.
Replace it there after rotation. Browser API keys are visible in rendered
HTML/network requests; restrict the key to Maps JavaScript API and authorised
HTTP referrers. Enable Maps JavaScript API and billing in its Google Cloud
project. For local testing allow `http://localhost:8000/*` and
`http://127.0.0.1:8000/*`; use your precise production origin when deployed.
Do not commit `.env` or the generated HTML. No Places API scraping, route
calculation API or extra Google dataset is used.

```powershell
python run_india.py --google-map-only
# Equivalently: python src/make_google_map.py
python -m http.server 8000 --bind 127.0.0.1 --directory outputs/india
```

Open http://127.0.0.1:8000/india_google_map.html in your own browser.
The map fits the national polygons, supports exact district/ID search (including
repeated district names), supply/composite/road/commercial layers, station and
district toggles, escaped source popups and Google Maps directions links.
Missing values display as No data. Empty gap layers remain unranked.

Normal national runs generate both maps when GOOGLE_MAPS_ENABLED=True and the
key is available. `--google-map-only` uses the existing processed snapshot and
can generate HTML without internet or reloading boundary providers. Viewing the
Google basemap requires internet. Its runtime loader is not part of the offline
Folium asset cache. The generated HTML manifest contains counts/provenance but
never the key. Missing keys skip the optional Google view; network/authentication
errors produce a clear page message.

Verification: **83 passed, 1 skipped** across the full suite. Offline Python
renderer tests, generated inline JavaScript syntax checks and a fake Google
Data API execution test pass. The latter checks startup, null-data styling,
ambiguous-name search, station toggles, popup clicks and auth-failure messaging. Browser preview could not reach the local server from the
in-app browser, so actual Google API authorisation/rendering is unverified.
After serving locally, check the browser for any Google Cloud billing, API
activation or HTTP-referrer errors. This cannot be established from a valid-
looking key alone. Git commit retry remains denied by .git/index.lock access.

Official integration references:
https://developers.google.com/maps/documentation/javascript/load-maps-js-api
https://developers.google.com/maps/documentation/javascript/datalayer
https://developers.google.com/maps/api-security-best-practices

## Original PDF recovery and national acceptance commands

`python src/complete_ev_counts.py` now implements the remaining EV recovery
workflow. The primary reader uses pdfplumber word positions inside detected
table-cell rectangles. The fallback uses pdftotext -layout only after primary
failure. Fallback audit coordinates are explicitly labelled character columns
and text lines, never invented PDF-point positions. The audit retains raw
words/cells, source PDF hash and parser backend. Year/measure changes, unknown
district labels, unexpected categories, duplicate cells, baseline disagreements
and printed-total mismatches stop before CSV replacement. Missing cells or
missing expected categories keep their district missing. CSV replacement is
atomic and occurs only after the original complete districts pass.

In the current environment the command is tested but original-PDF execution
is still blocked: pdfplumber cannot be installed because DNS fails, and Git's
bundled pdftotext executable fails to launch with Windows error 623. No EV CSV
values were replaced and no successful coordinate extraction is claimed.

Use `python run_acceptance.py --scope india` for the saved national outputs;
plain `python run_acceptance.py` reports the state. The national report records
610 raw/576 merged records, known ports for 151 raw/146 merged records, and
road/commercial coverage for 735 supplied polygons. It separately records the
Google view's 575 assigned stations. Compatible national EV/population values
remain absent for all 735; there are no national demand ranks. The older
national manifest did not record the selected provider, so provider provenance
is PARTIAL rather than inferred from a filename. Use
`python src/load_boundaries.py --compare --national` to compare national
providers once all downloads are available. State commands and files are kept
separate from the national acceptance scope.

Source discovery is recorded in
`data/samples/official_sources/national_source_candidates.json`. The official
public VAHAN report and a third-party 2024 district/RTO layer were located, but
no compatible national export was imported. The latter's measurement period
meaning, reuse rights and geography remain unverified. Uploaded workbook/CSV
content could not be retrieved; no file contents or values are inferred from
their titles. If those files are already on your computer, copy them to
`data/raw/supplied_user_files/` for local inspection. An RTO office location
alone does not establish a district registration catchment.

Latest full tests: 95 passed, 1 PySAL integration skip. Real map-library retries
failed for all eleven URLs. Computer Use stopped browser validation because it
could not establish the active Windows URL reliably. Git staging/commit remains
blocked by .git/index.lock write permissions; reconnecting alone does not
change the workspace profile's read-only .git access. No security settings or
Git identity were changed to work around that restriction.
