# Current data collection and feasibility - 27 October 2026

The code for both slices is implemented. A partial real-data run is now
available; full live/composite/hotspot verification is still incomplete.

## Data actually collected

| Data | Coverage | Use in current run |
|---|---|---|
| Official MoRTH/VAHAN district-category EV table, Lok Sabha answer 4552, published 19 March 2026 | 2025 annual NEW registrations; 37 source districts | 26 complete district totals; 11 excluded for ambiguous PDF cells |
| Tamil Nadu DES Statistical Handbook 2022-23, table 2.1 | 38 district mid-year 2022 population estimates | Candidate file only; geography compatibility unverified |
| Pinned third-party district polygons | 37 polygons from pre-existing cache | Used with district-coverage and rights caveats |
| OSM charger observations | 220 raw records from pre-existing cache; no verified retrieval date | Used, explicitly labelled cached rather than refreshed |
| OSM roads/commercial nodes | Live download not available | Missing; never replaced by zeros |

The 26 complete EV totals sum to **141,606** annual registrations. This is a
partial-district sum, **not a statewide total**, active vehicle fleet, or
cumulative registrations. The named source contains all 37 rows, but some
numeric cells lost separators in PDF text extraction. The importer records
raw cells and refuses affected district totals. No synthetic EV values are used.

EV source:
https://sansad.in/getFile/loksabhaquestions/annex/187/AU4552_wCyeso.pdf?source=pqals

Population candidate:
https://des.tn.gov.in/sites/default/files/2025-07/2.VITAL%20STATISTICS.pdf

Source text was collected through web retrieval and cached locally. Original
PDF bytes and readable page-image bytes were not available through this path.
The text snapshots are committed under data/samples/official_sources and a
parser rebuilds the CSVs; no district values are typed into calculation logic.
Government tables are citable factual sources; an explicit redistribution
licence has not been established. They are not labelled CC-BY without evidence.

The 2022 population values are official published estimates, not generated
synthetic figures. They stay out of the index until district geography is
checked. Names alone cannot prove matching boundaries. Source names and
spelling are preserved in the candidate file.

## Verification

- Python 3.11.9 on Windows; source compilation succeeds.
- Latest offline suite: **41 passed, 1 skipped**. The skipped case is the true
  PySAL Gi* integration test; libpysal/esda remain unavailable because direct
  package downloads fail DNS. It has not been counted as a pass.
- Both-slice pipeline regenerates the partial historical gap map, source
  audit and CSVs. Twenty-six basic ranks are based on the collected EV data;
  eleven remain missing. Composite indicators remain incomplete/unranked.
- A real-data source-date timestamp exposed a Folium serialization issue; it
  was fixed and a metadata-bearing map regression test now passes.
- Raw charger reconciliation: 220 = 74 inside + 146 outside.
- Deduplicated reconciliation: 216 = 73 inside + 143 outside at 40 m.
- 57/220 raw records have known ports. Radius sensitivity and human validation
  samples are generated; no claim of externally validated precision is made.
- Folium HTML is generated and its content/layer contracts tested. Eleven
  JS/CSS libraries are not cached; internet is needed to display this preview.
  Browser visual rendering has not been verified. After a connected run the
  vector map libraries can be cached, while basemap tiles remain online.

## Concrete remaining limits

Direct Python requests to official PDF and package hosts still fail DNS.
Web retrieval successfully collected official table text, but its Overpass
request was inaccessible. Consequently current charger refresh, road geometry,
commercial nodes, package installation and full browser inspection are not
complete. No fabricated substitutes or replacement spatial statistics were used.

The default collected EV input is historical annual adoption, not live fleet
pressure. For a full result, resolve ambiguous source cells from a readable
original PDF, obtain compatible population geography, obtain OSM road/POI
responses, install the PySAL dependencies and execute its integration test.
Boundary redistribution rights and the human merge-validation sample also
remain to be checked. No paid API is required for the implemented default route.

## National build verification (27 October 2026)

The India binary extraction completed from the supplied snapshot dated
2026-10-25T21:21:21 UTC: 610 raw charger records, 576 merged stations,
246786 main-road ways and 179302 commercial nodes. These are OSM observations,
not a complete inventory of working public chargers. Ports are known for 151
raw records; other records retain the flagged one-port assumption.

The national test suite reports 54 passed and 1 skipped. The skipped PySAL
integration test still needs libpysal and esda; it is not counted as verified.
Live download connectivity timed out. A safe current-extract refresh command
is implemented and tested with fake network responses, but a successful live
refresh has not been verified in this environment.

National EV and compatible population inputs are absent. National gap and
composite ranks therefore remain empty; the supply map must not be described
as a measured demand-gap ranking. State outputs remain unchanged. National
count reconciliation and source hashes are recorded in outputs/india/run_manifest.json
when the full run completes. The map explicitly warns about missing inputs
and uncached display libraries where relevant.
