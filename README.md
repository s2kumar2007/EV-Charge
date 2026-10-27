# ChargeGap India - Slices 0 and 1

Techfest 2026-27, IIT Bombay: EV infrastructure map for one Indian state.
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

The Python pipeline can run offline after caching its required inputs. Map JS
and CSS are downloaded into `data/raw/map_assets/` and copied to
`outputs/assets/`; keep that directory beside the HTML when sharing the map.
After those libraries are cached, district vectors and charger circles work
without internet. Basemap tiles, fonts and optional CSS images may still need
internet; the project does not bulk-download OSM tiles. If JS/CSS downloads
failed, the map displays an explicit internet-required banner.

## What you must supply or review by hand

1. Export real VAHAN EV totals and save `data/raw/vahan_tn_ev_by_district.csv`.
   Record the export date, vehicle/fuel filters, time window and whether totals
   mean cumulative registrations. A stable public unauthenticated VAHAN API is
   not assumed, and this project does not bypass login or CAPTCHA. Registration
   totals do not measure road traffic, usage, or the active vehicle fleet.
2. Check `data/processed/vahan_name_resolution.csv`, especially fuzzy/geocoded
   matches and unresolved names. RTO totals describe the office's registrations;
   geocoding its office is only a proxy for the relevant district.
3. Supply compatible population in the VAHAN column or in
   `data/raw/population.csv` (`district,population`). Record year, source and
   licence. Alternatively verify that the downloaded 2011 census totals match
   the polygons, then set `POPULATION_BOUNDARIES_VERIFIED = True`. Matching a
   name does **not** prove that its boundaries have not changed.
4. Review boundary accuracy, current district coverage and redistribution
   permissions; the pinned compilation is not an official boundary authority.
5. Fill `checked_ok` (yes/no) and `notes` in `outputs/validation_sample.csv`,
   then run the validation script. It reports correct reviewed merges divided
   by reviewed merges, plus coverage. This is neither recall nor proof of all
   stations' correctness. Later runs preserve reviewed samples and create a
   separately named sample. Cluster IDs belong to the associated run/audit.
6. Replace provisional equal AHP judgments with documented expert comparisons
   if presenting that weighting scheme as expert-based. Review deduplication
   radius, label thresholds and confidence weights before submission.

## Sources, licences and live fetching

| Input | Download/source | Licence and cautions |
|---|---|---|
| District polygons | [udit-001/india-maps-data](https://github.com/udit-001/india-maps-data), exact commit and state slug in config | No explicit dataset licence found; repository says it curates others' data for personal use. Verify permission before redistributing the geometry. New districts may be missing. |
| Chargers, roads, commercial nodes | [OSM Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API), one primary and two fallback servers | [OSM contributors, ODbL](https://www.openstreetmap.org/copyright); public service capacity is limited. Query box is calculated from polygons. |
| Optional charger records | [OpenChargeMap](https://openchargemap.org/site/develop/api), only with `OCM_API_KEY` | Free developer access; retain attribution and check the data provider's individual terms. Current developer/terms pages may require login. Not required for the default run. |
| Name geocoding | [OSM Nominatim](https://nominatim.openstreetmap.org) | ODbL; see [mandatory usage policy](https://operations.osmfoundation.org/policies/nominatim/). Single thread, cached answers, identifying User-Agent, at most one request per second. Intended for a small one-time district/RTO reconciliation, not scheduled bulk geocoding. |
| Population candidate | [IndiaSet Census 2011](https://huggingface.co/datasets/indiaset/census-2011) | Publisher labels compilation CC-BY-4.0, derived from Census of India 2011. Citation: Jaiswal, Ansuman (2026), *India Census 2011 - District Level*. Historic geography is not silently applied to newer polygons. |
| EV registrations | User's VAHAN export | Verify VAHAN export/reuse terms and retain provenance. No EV data are bundled as real observations. |

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
sample in `data/samples/`. There is currently **no real sample export**.
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
A successful empty OSM answer means observed count zero; a failed/partial
answer means missing. All directions are positive; no indicator is inverted.
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
