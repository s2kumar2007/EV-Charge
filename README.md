# ChargeGap India - Slice 0

Builds an interactive map of a state's districts coloured by a basic **EV charging gap score**, with public
chargers as points. One state, one simple score, no forecast. Everything that can change (state, data sources,
thresholds, colours) is in `src/config.py`. The logic files contain no district lists or spelling tables.

## Install and run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run_all.py          # runs everything; first run needs internet
python tests/test_resolver.py   # offline test of the name matching
```
Outputs: `outputs/tn_gap_map.html` (map) and `outputs/district_gap_scores.csv`.

## Where the data comes from
| Data | Source | How |
|---|---|---|
| District boundaries | `udit-001/india-maps-data` (pinned commit) | downloaded automatically |
| Chargers | OpenStreetMap (Overpass), optional OpenChargeMap | downloaded automatically, search area = bounds of the boundaries |
| EV counts | VAHAN export | **you provide** `data/raw/vahan_tn_ev_by_district.csv` (district OR rto level) |
| Name matching | exact -> fuzzy spelling -> OpenStreetMap Nominatim geocoding | automatic, cached |

## VAHAN file
Columns: `district` **or** `rto`, then `ev_total` (or `two_wheeler`, `three_wheeler`, `four_wheeler`, `bus`), optional `population`.
RTO rows are placed in districts by geocoding the RTO name; rows of the same district are added together.
Every name that was not an exact match is printed and saved in `data/processed/vahan_name_resolution.csv`: **check it by eye**.
Districts with no EV count are left empty ("no EV data", not ranked). Nothing is invented unless you set `ALLOW_SYNTHETIC = True`
in `config.py`; then invented values are flagged `synthetic`.

## Gap score
`gap_score = EVs in district / public chargers in district` (higher = more underserved).
Districts with 0 chargers: see `NO_CHARGER_POLICY` in `config.py`.
`smoothed` (default): score = EVs / max(chargers, 1), so a district with a handful of EVs does not outrank a large one.
`first`: every district with 0 chargers ranks above all others.

## Limitations
- OSM charger data is incomplete; one station can appear as several points (no deduplication yet).
- The boundary file is a third-party compilation with mixed source years and may lack the newest districts; the run prints the count.
- Fuzzy and geocoded matches can be wrong. Always read the name check list.
- No forecast, optimiser or dashboard yet.
- Charger types and speeds are not distinguished.

## Licences and attribution
OpenStreetMap data: (c) OpenStreetMap contributors, ODbL. Boundaries: see the `india-maps-data` repository's licence notes.
OpenChargeMap and VAHAN: check their terms before publishing results.
