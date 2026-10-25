# ChargeGap India - Slice 0

A small Python project that builds an interactive map of **Tamil Nadu districts**
coloured by a basic **EV charging gap score**, with public EV chargers shown as points.

This is a **Slice 0 prototype**: one state, one simple score, no forecasting.

## What it produces

| File | What it is |
|---|---|
| `outputs/tn_gap_map.html` | Interactive map (open in any browser) |
| `outputs/district_gap_scores.csv` | One row per district: EVs, chargers, gap score, rank, data flag |

## Install

Requires **Python 3.10+**.

```bash
cd chargegap
python -m venv .venv
# Windows:      .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python run_all.py      # runs everything, in order
python checks.py       # prints sanity checks (also runs at the end of run_all.py)
```

The first run downloads the boundaries and chargers and saves them in `data/raw/`.
After that the project works **offline**. To refresh a download, delete its file in `data/raw/`.

### Optional: OpenChargeMap
Copy `.env.example` to `.env` and put your key in it:
```
OCM_API_KEY=your_key_here
```
If the key is missing, only OpenStreetMap chargers are used. When both are used,
each charger keeps a `source` column (`OSM` or `OCM`).

### Required by hand: VAHAN EV counts
VAHAN has no clean API, so export the numbers yourself and save them as
`data/raw/vahan_tn_ev_by_district.csv`. A template is created for you at
`data/raw/vahan_tn_ev_by_district_TEMPLATE.csv`.

| column | required | meaning |
|---|---|---|
| `district` | yes | district name |
| `ev_total` | yes | total registered EVs in the district |
| `two_wheeler`, `three_wheeler`, `four_wheeler`, `bus` | no | breakdown (if `ev_total` is blank, these are added up) |
| `population` | no | if present, EVs per 100,000 people are also computed |

Rows whose district is `EXAMPLE` are ignored.
**If the file is missing, or a district has no value, a placeholder number is used and
clearly labelled `synthetic`** (`data_flag` column, map popup, and a warning on the map).

## Project layout

```
chargegap/
  data/raw/         downloads and manual inputs
  data/processed/   intermediate files made by the code
  outputs/          final CSV and HTML map
  src/
    utils.py            shared helpers (paths, name matching, download retries)
    load_boundaries.py  step 1: district polygons
    fetch_chargers.py   step 2: chargers from OpenStreetMap (+ OpenChargeMap)
    load_vahan.py       step 3: EV counts (real or flagged synthetic)
    build_scores.py     steps 4-5: spatial join, gap score, ranking
    make_map.py         step 6: Folium map
  run_all.py        runs everything
  checks.py         sanity checks
```

## Gap score definition

```
gap_score = EVs registered in the district / public chargers in the district
```

- **Higher = more EVs per charger = more underserved.**
- If a district has **0 chargers** no division is done. It is marked `no chargers`,
  shown in a separate purple colour, and ranked as **most underserved** (rank 1 = most underserved).
- Among districts with chargers, rank follows the gap score (highest first).
- If a `population` column is supplied, `evs_per_100k = ev_total / population * 100,000` is also output.

## How it works (plain language)

1. Download district polygons and keep Tamil Nadu.
2. Ask OpenStreetMap for every `amenity=charging_station` in Tamil Nadu.
3. Read the EV counts per district (or use flagged placeholders).
4. For each charger, find which district polygon contains it (point-in-polygon join), and check
   that *assigned + outside = total fetched*.
5. Divide EVs by chargers, rank the districts, save the CSV.
6. Draw the map.

## Data sources and licences

- **OpenStreetMap** (chargers) - (c) OpenStreetMap contributors, licensed under the
  [Open Database Licence (ODbL)](https://www.openstreetmap.org/copyright). Any use or
  publication of results must credit "(c) OpenStreetMap contributors".
- **DataMeet India district boundaries** (Census 2011) -
  <https://github.com/datameet/maps>. Check the licence stated in that repository and
  credit DataMeet.
- **OpenChargeMap** (optional) - <https://openchargemap.org>. Check its data licence and
  attribution terms before publishing.
- **VAHAN** (Government of India vehicle registration dashboard) - exported manually.
  Check the portal's terms of use.

## Limitations

- **OSM charger data is incomplete.** Some chargers are missing, outdated, or have no name/operator.
  A low charger count may partly reflect missing mapping, not missing chargers.
- **VAHAN data is entered manually.** Typos, wrong filters or a different date range will change results.
- **No deduplication yet.** If OSM and OpenChargeMap both list the same station, it is counted twice.
  A single station with several plugs may also appear as several points.
- **No forecast yet.** The score is a snapshot of today, not a prediction.
- **All chargers count equally.** Slow and fast chargers, and public vs. restricted access, are not distinguished.
- **Boundaries are from the 2011 Census.** That file has **32** districts; Tamil Nadu now has 38.
  Newer districts (e.g. Tenkasi, Tirupathur, Ranipet, Chengalpattu, Kallakurichi, Mayiladuthurai)
  have no polygon of their own. The run prints any VAHAN rows that cannot be matched. For Slice 0,
  add their EVs to the parent 2011 district in your VAHAN CSV, and note that you did so.
- District borders and EV counts follow different calendars, so small mismatches are expected.
- Chargers just outside a polygon (for example on the coast) are reported as "outside districts"
  and are not counted in any district.
