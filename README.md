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
Outputs: `outputs/tn_gap_map.html` (map) and `outputs/district_gap_scores.csv` (includes `charger_count`, `port_count`, `gap_score`, `gap_unit`, and integer `rank`).

## Where the data comes from
| Data | Source | How |
|---|---|---|
| District boundaries | `udit-001/india-maps-data` (pinned commit) | downloaded automatically |
| Chargers | OpenStreetMap (Overpass), optional OpenChargeMap | downloaded automatically, search area = bounds of the boundaries |
| EV counts | VAHAN export | `data/raw/` (local) or `data/samples/` (committed fallback) |
| Name matching | exact -> fuzzy spelling -> OpenStreetMap Nominatim geocoding | automatic, cached |

## VAHAN file and data folders
The project looks for VAHAN EV count data in two locations:
- `data/raw/`: Place your local `vahan_tn_ev_by_district.csv` here. This folder is ignored by git so raw or proprietary files are never committed.
- `data/samples/`: Sample data committed and tracked in git. If the file in `data/raw/` is missing, `load_vahan.py` falls back to `data/samples/` using the file specified by `VAHAN_SAMPLE_FILE` in `src/config.py`.

Columns: `district` **or** `rto`, then `ev_total` (or `two_wheeler`, `three_wheeler`, `four_wheeler`, `bus`), optional `population`.
RTO rows are placed in districts by geocoding the RTO name; rows of the same district are added together.
Every name that was not an exact match is printed and saved in `data/processed/vahan_name_resolution.csv`: **check it by eye**.
Districts with no EV count are left empty ("no EV data", not ranked). Nothing is invented unless you set `ALLOW_SYNTHETIC = True`
in `config.py`; then invented values are flagged `synthetic`.

## Synthetic test data
The repository includes `data/samples/vahan_tn_ev_by_district_SYNTHETIC_TEST.csv`, which contains invented EV counts strictly for testing.
- To enable it when no real VAHAN file is available, set `USE_SYNTHETIC_TEST_DATA = True` in `src/config.py`.
- When enabled, the interactive map displays a synthetic warning and dashed district outlines, and the run prints a loud warning.
- **Important**: This file contains invented data and must never be used in the submission.

## Gap score
`gap_score = EVs in district / public chargers (or ports) in district` (higher = more underserved).
The unit is controlled by `GAP_UNIT` in `src/config.py`:
- `stations` (default): gap score = EVs / public charging stations (`charger_count`).
- `ports`: gap score = EVs / public charging ports (`port_count`).
Both `charger_count` and `port_count` appear in `outputs/district_gap_scores.csv`, along with a `gap_unit` column.

Districts with 0 chargers: see `NO_CHARGER_POLICY` in `config.py`.
`smoothed` (default): score = EVs / max(chargers or ports, 1), so a district with a handful of EVs does not outrank a large one.
`first`: every district with 0 chargers ranks above all others.

## Limitations
- OSM charger data is incomplete; one station can appear as several points (no deduplication yet).
- Charger capacity (number of ports): uses the `capacity` tag in OpenStreetMap and `NumberOfPoints` in OpenChargeMap when given as a positive integer. If missing or invalid, it defaults to 1 port (tracked via `ports_known` in `data/processed/chargers_raw.csv`).
- The boundary file is a third-party compilation with mixed source years and may lack the newest districts; the run prints the count.
- Fuzzy and geocoded matches can be wrong. Always read the name check list.
- No forecast, optimiser or dashboard yet.
- Charger types and speeds are not distinguished.

## Licences and attribution
OpenStreetMap data: (c) OpenStreetMap contributors, ODbL. Boundaries: see the `india-maps-data` repository's licence notes.
OpenChargeMap and VAHAN: check their terms before publishing results.
