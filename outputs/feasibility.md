# Latest completion checks - 27 October 2026

This section supersedes the earlier PDF/PySAL blockers below.

- Part A completes: all 37 district totals are now present, preserving all 26
  previously complete values. 2025 sum = 174,477 annual new EV registrations.
  Word positions recover rows lacking borders at page breaks. All original PDF
  coordinates remain audited. No printed district/state total rows exist in the
  annexure; printed-total comparisons are recorded as not available, not invented.
- State offline pipeline completes with 37 basic ranks and 33 composite ranks;
  four polygons remain population-incomplete. The five population mapping rows
  are still unapproved and printed for human review.
- The existing project virtual environment contains esda 2.9.0/libpysal 4.14.1.
  Actual Moran I=0.04443963065913198, p=0.056, n=33; Gi* n=33, 999 permutations.
  Small-sample warning retained. Fixed an offline dependency-test isolation issue
  revealed by running the real integration. Project-environment tests: 108 passed.
- Both Folium maps retain all 11 JS/CSS assets locally after recaching. Tiles
  remain online. Native Google browser verification remains blocked: Computer Use
  stopped because it could not reliably identify the current Windows browser URL.
  No further browser actions were taken after that stop.
- National EV/population compatibility remains 0/735. The supplied combined EV
  table cannot be disaggregated. The 640 Census 2011 district candidates require
  geography review. Missing pinned national state files still require a connected
  terminal; default provider remains unchanged. Synthetic data: NO.

Manual actions still open: verify the five population rows with geography
sources; supply compatible district EV counts for India and review Census extent
mappings. Run `python src/load_boundaries.py --compare --national` online to cache
missing pinned files. Run `python run_map.py` locally and verify Google rendering
and authorization. Review charger merges, AHP judgments and boundary rights.
Use your terminal to commit if the agent still cannot write the Git index.

---

# Latest verification - 27 October 2026

This update supersedes earlier blocked-access notes below. Acceptance remains
PARTIAL; no source values are invented or automatically disaggregated.

- Browser showed ERR_CONNECTION_REFUSED, then timeout after the agent started
  a server. Agent HTTP clients also cannot connect to localhost. Added
  `python run_map.py` for the user's terminal and a dependency-free SVG
  fallback. Google HTML regenerated: 735 polygons, 575 stations. Offline
  fake-API tests cover fallback and Google UI behavior. Successful Google
  browser rendering/authorization is not claimed.
- All three supplied files are readable. Census 2011 has 640 district totals
  summing to its printed India population 1,210,854,977. Candidates and unverified
  national crosswalk suggestions are local CSVs; accepted = 0. State directory:
  36 rows. EV CSV: combined 2025-2026 table, total 5,178,162, no district rows;
  category/fuel sums reconcile, imported = 0.
- Fixed accent normalization. State comparison: pinned 37, geoBoundaries 38.
  Pinned-only names: Chengalpattu, Kanyakumari, Nilgiris. geoBoundaries-only:
  Chengalputtu, Kanniyakumari, Mayiladuthurai, The Nilgiris. Default unchanged.
  National comparison cannot download missing pinned state files. ADM1/ADM2
  metadata, geometry receipts and attribution are cached.
- Both Folium maps have all 11 JS/CSS assets local and nonempty. Tiles stay online.
- PDF reader works: 2,720 raw cells retain PDF word coordinates. Baseline check:
  17 PASS, nine STOP/unverified. Every baseline EV CSV row is preserved; 26
  complete and 11 missing remain. Review raw cells/checks before replacing totals.
- State offline run completes: 37 polygons, 220 raw/216 merged chargers,
  33 accepted populations, 37 road/commercial observations, 23 composite ranks.
  Moran/Gi* actual n=0, eligible=23; esda is missing. Synthetic data: NO.
- Tests: 104 passed, 1 skipped. The skipped integration requires PySAL/esda.

Manual work: run `python run_map.py` in your terminal; verify Google API rendering
once the local view opens. Supply district-level EV rows with one explicit
period/measure; review Census geography and the five state population mappings.
Review the nine PDF baseline failures. Install esda and cache pinned national
state files online, then rerun the comparison. Review charger merges, AHP
judgments and boundary redistribution rights. Commit from your terminal if
Git writes remain restricted to the agent.

---

# Current verification - 27 October 2026

Acceptance: **PARTIAL**. The state CLI completes offline using real supplied
sources. Missing values are retained. No synthetic data are in use. Source
completion and external validation are not claimed merely because code exists.
This section replaces the earlier feasibility snapshot.

| Check | Current observed result | Status |
|---|---|---|
| State boundaries | 37 polygons; pinned_repo remains the default | PASS loading; rights unresolved |
| Chargers | 220 raw, 216 deduplicated; 57 raw and 56 merged records have known ports | PASS internal counts; manual merge validation pending |
| Charger assignment | Raw: 74 inside + 146 outside = 220; merged: 73 inside + 143 outside = 216 | PASS |
| EV input | 26 complete, 11 missing; 2025 annual NEW registrations, all original vehicle categories, not cumulative fleet | PARTIAL |
| Basic district ranks | 26 | PARTIAL coverage |
| Population | 38 official 2022 estimate rows; 33 polygons accepted by exact-name crosswalk; 4 polygons have no accepted population | PARTIAL |
| Roads | 37 observed densities; national_cache, snapshot 2026-10-25T21:21:21+00:00 | PASS source/geometry checks |
| Commercial places | 37 observed densities; same national_cache and snapshot | PASS source/geometry checks |
| Composite index | 23 ranked, 14 missing indicators | PARTIAL |
| Moran I / Gi* | 23 eligible; 0 actually used; statistics remain missing because PySAL is absent | PARTIAL, small-sample warning |
| Map | outputs/tn_gap_map.html generated; 11 external JS/CSS URLs; offline assets: no | PARTIAL; browser visual check pending |
| Synthetic data | NO; both synthetic switches disabled | PASS |

## A: original PDF extraction is blocked

`data/raw/AU4552_original.pdf` exists (687838 bytes). The active Python has no
pdfplumber; both package installation attempts failed to find an available
distribution, and the bundled pdftotext fails to launch with Windows DLL relocation error 623. No other PDF parser was substituted.
The existing EV CSV is unchanged relative to Git HEAD after newline normalisation (all rows and values match); the 26
complete totals still sum to 141606. That partial sum is not a state total.

No word-coordinate audit or PDF total cross-check has been completed. Do not
claim any of the 11 ambiguous districts were recovered. By hand in a connected
terminal run `python -m pip install pdfplumber`, then resume Part A. Extraction
must retain every cell/coordinate, preserve the original year/categories and
annual-new-registration measure, compare every existing complete district and
stop on disagreement before replacing any CSV. Printed row/state totals must
also be checked wherever present. The PDF itself does not need downloading again.

## B: population compatibility

The committed `data/samples/district_crosswalk.csv` preserves source spelling.
Only normalised exact names have one_to_one. Five rows need human review:

| Population source row | Resolver proposal | Current state |
|---|---|---|
| Sivagangai | Sivaganga | fuzzy; suggestion, not verified |
| Thoothukudi | Thoothukkudi | fuzzy; suggestion, not verified |
| Kanniyakumari | Kanyakumari | fuzzy; suggestion, not verified |
| Tiurupathur | Tirupathur | fuzzy; suggestion, not verified |
| Mayiladuthurai | No resolved polygon | geocoding unavailable offline |

Polygons without accepted population: Kanyakumari, Sivaganga, Thoothukkudi,
Tirupathur. Four fuzzy destinations are proposals, not proof of compatibility.
Geocode requests could not run; no geocode suggestions are claimed.

A non-exact row can be accepted only as many_to_one with verified=yes, the
exact polygon label and documentary evidence. All contributors to a shared
polygon must be approved; values are summed only when every required value
is present. One source row cannot be duplicated or split. Source-name equality
still cannot prove unchanged historical boundaries. The indicator label is
"annual new EV registrations per 100,000 people (2022 population estimate)".
A compatible manual population input retains its previous precedence.

## C: national OSM cache reused for the state

Source priority is configurable: matching state Overpass cache, matching
national extraction cache, live Overpass. Cache identity checks compare the
PBF SHA-256 and reader version. Without the original PBF, one uniquely
identified cache can be read; a matching manifest supplies its date, otherwise
the snapshot date stays unknown and acceptance is partial. Both indicators record source, snapshot date
and cache filename in data/processed/district_osm_indicators.csv and the index.
Roads are clipped at state and district borders and measured in each district's
automatically chosen local metric CRS. Nodes are assigned once on shared borders.
A complete empty observation can be zero; missing/failed/partial data are not
zero-filled. Offline tests check cross-border road splitting and missing coverage.

The national cache was previously extracted from the supplied India PBF and
contains 246786 trunk/primary roads and 179302 commercial nodes. These are OSM
features, not a complete traffic or business census. State charger records
remain the legacy cached observations with unknown retrieval date; roads'
2026 snapshot date is not assigned to those charger records.

## D: offline map resources

src/cache_map_assets.py reads actual script/link attributes, deduplicates URLs,
checks non-empty cache/destination files and retains original URLs on failure.
The downloader uses shared retry settings; fake byte responses test success,
reuse, empty responses and failures without internet. MAP_OFFLINE_MODE defaults
to False; cache_map_assets.py can also process an existing HTML file directly.
Tiles stay online; MAP_TILES=None removes the basemap. CSS fonts/images referenced
inside those files are outside the script/link cache scope.

By hand with internet run:
`python src/cache_map_assets.py outputs/tn_gap_map.html`.
All 11 library URLs remain external; actual successful downloads and browser
visual rendering have not been verified here.

## E: boundary rights and providers

The supplied pinned-repository README describes collection "for personal usage"
and names no data licence. Redistribution rights remain unresolved. Direct
re-fetching of the pinned README failed here; this warning is not a newly
verified legal conclusion. Ask the publisher for permission or choose a provider
whose terms and accuracy you can satisfy.

BOUNDARY_PROVIDER defaults to pinned_repo and now governs both runners.
The geoBoundaries path preserves ADM2/ADM1 metadata, exact gjDownloadURL files,
SHA-256 receipts and attribution under data/raw. State membership uses exact
ADM1 state selection and district representative points, not a missing state
attribute or hand-typed district list. The comparison command prints counts
and source names present only in one provider without changing the default.

Metadata could be retrieved through web lookup: ADM2 represents 2021 and names
ODbL 1.0; ADM1 represents 2011 and names CC BY 2.5 India. Preserve both releases'
terms and year differences. Actual Python downloads fail connection attempts.
`python src/load_boundaries.py --compare` could not load the alternative; no
state comparison count or successful download is claimed. With internet run
that command and review its printed name/count comparison before switching.
The supplied root ADM2 snapshot is not silently asserted to match current
metadata. A fresh full national run was not performed: the explicit default
pinned provider requires its repository listing/all state files to be cached.
Previously generated national outputs remain separate historical outputs.

Metadata:
https://www.geoboundaries.org/api/current/gbOpen/IND/ADM2/
https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/

## F: acceptance and remaining manual checks

Run `python run_acceptance.py`. It prints evidence-backed PASS/PARTIAL/FAIL
for the requested metrics, records actual Moran/Gi* sample sizes, rechecks map
files/URLs and writes outputs/acceptance_report.json. Unknown evidence remains
PARTIAL. Synthetic inputs and impossible raw/merged counts fail acceptance.
Missing PySAL dependencies now leave untested outputs and let map/report
generation finish, without producing substitute statistics.

Latest offline suite: **95 passed, 1 skipped**. The single skip is the real PySAL Gi*
integration test. Added fake-data tests cover crosswalk proposals/aggregation,
source priority/date/clipping, asset caching, provider metadata/selection and
acceptance statuses; the existing tests also pass. The state CLI completed
with no synthetic values. No browser-rendering claim is made.

Remaining manual actions:

1. Install pdfplumber in a connected terminal and resume the audited PDF extraction.
2. Verify the five population crosswalk rows above; do not approve based on spelling alone.
3. Install `python -m pip install libpysal esda`, rerun the state CLI and tests.
4. Cache map assets using the command above; inspect the map in a browser.
5. Run the provider comparison online, review licences/geography and choose explicitly.
6. Review charger merge samples and provisional AHP judgments.
7. Commit the reviewed changes in your terminal. Git staging/commit was attempted
   after the first tested stage but this runtime denies .git/index.lock creation.
   Existing user Git identity was not changed, and no commits were created.
   After review: `git add .` then
   `git commit -m "feat: add population compatibility and source acceptance checks"`.

Runtime caches, maps, logs, temporary downloads and virtual environments are
ignored. Samples, crosswalk, source code, tests and this report remain trackable.

## Native Google Maps national view

Added outputs/india/india_google_map.html using existing processed national
outputs: 735 polygons, 576 merged observations, 575 inside a loaded district
and displayed. The unassigned observation remains excluded by default and
is retained in the audit. This is the supplied boundary snapshot, not complete
current administrative or charger coverage. No missing national demand values
were populated. Snapshot timestamp is carried from the existing national manifest.

The browser key is stored in ignored .env; it is never printed by the generator
or written into tracked files/manifests. The generated ignored HTML necessarily
loads Google with a browser key; restrict its API and HTTP referrers and rotate
the key shared in chat. Its project's billing/API activation cannot be inferred.

Generate without recalculation: python run_india.py --google-map-only.
Serve with python -m http.server 8000 --bind 127.0.0.1 --directory outputs/india,
then open http://127.0.0.1:8000/india_google_map.html. The in-app browser cannot
reach the preview server; actual Google Maps authorisation and visual rendering
remain unverified. Offline fake-data/key renderer tests and Node syntax checks
pass. The UI explains internet/billing/API/referrer failures; it does not claim
successful authentication based on the shape of the supplied key.

A commit retry after the focused passing tests again failed on .git/index.lock
permission. The key remains ignored and existing Git identity is unchanged.

Final full suite: 83 passed, 1 skipped in 9.12s. The eight Google Maps tests
include a fake Google API execution test for startup, missing layer values,
duplicate district-name search, charger toggles/popups and auth failure.
Generated JavaScript passes node --check; git diff --check passes.
A scan of every tracked/unignored file found no actual supplied key. Both
.env and outputs/india/india_google_map.html are confirmed ignored.

## Continued completion attempt after reconnect

Implemented src/complete_ev_counts.py with ten offline tests using fake
word coordinates and table cells. It tries pdfplumber word/cell geometry
first, falls back only to pdftotext -layout, records coordinate units and raw
cells, preserves the exact existing year/measure/category definitions and
stops before replacing CSV on disagreement. Tests cover existing-value and
printed-total checks, ambiguous separators, absent categories and unknown
district labels. The existing web-table importer now shares the measure label
from config. Real execution remains blocked: pip reports getaddrinfo failure;
pdftotext is present in Git's installation but raises Windows error 623.
No recovered district values or coordinate-audit completion is claimed.

Added national acceptance scope: python run_acceptance.py --scope india.
Actual saved-run observations: 735 polygons; 610 raw/576 merged records;
known ports for 151 raw/146 merged records; 735 road and commercial densities
using the 2026-10-25T21:21:21 UTC snapshot. National EV/population coverage is
0/735, composite ranked=0; Moran/Gi* remain untested. Google view: 735 polygons
and 575 assigned stations; browser authorisation unverified. The older boundary
manifest lacks a provider field and is explicitly partial. No state population
year, PDF task or map-file path is incorrectly reused in national acceptance.

Retried every external Folium script/link URL with a bounded connection test:
all eleven failed; original URLs remain intact and failures are recorded in
the asset receipt. No successful offline map-library cache is claimed.
Computer Use stopped itself because it could not determine the current Windows
browser URL reliably, so no further browser automation was attempted this turn.

The national source-candidate file records the official public VAHAN report,
a third-party 2024 district/RTO layer and the three supplied filenames. These
are not imported counts or verified geographic crosswalks. Library content
retrieval/download failed; searching this project and its parent found no
local copies of the supplied workbooks/CSV. Do not infer district coverage or
measure definitions from filenames. Copy local originals into
 data/raw/supplied_user_files/ for inspection if available.

Final checks for this increment: 95 passed, 1 skipped (real PySAL Gi*).
Git diff whitespace checks pass. Existing EV rows and totals remain unchanged.
Commit retry still fails because .git/index.lock writes are denied; no commits,
permission changes or identity changes were made. Current source changes are
listed in outputs/changed_files.txt for review.

Manual actions that remain necessary:
- Install a working pdfplumber/pdftotext and run python src/complete_ev_counts.py.
- Provide/read the supplied source files locally; obtain compatible national
  district EV/population inputs before claiming national demand ranks.
- Review five population crosswalk rows and charger merge/AHP evidence.
- Enable working network access for PySAL, boundary and map-asset downloads.
- Inspect Google Maps in your browser with API/billing/referrer settings enabled.
- Commit in your own terminal or make .git writable in the workspace profile.
