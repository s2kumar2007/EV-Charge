# ChargeGap India - Engineering Roadmap Progress

**Date**: 2 November 2026  
**Branch**: `feat/roadmap-build`  
**Initial Baseline**: 108 tests passing, 0 failures, 1 warning (pytest 8.x, Python 3.11).

## Progress Log
- `e294f39` chore: create branch, venv, install; run pytest; record pass count in PROGRESS.md (108 passed)
- `638f14f` fix: repair any failing tests or environment issues found (silenced external esda DeprecationWarning)
- `d2f0825` chore: add Makefile or check.py target check that runs the commit gate (tests + compileall)
- `bea6c6b` docs: create TODO_MANUAL.md (I must supply: national district EV counts, approve the 5 population mapping rows, OCM_API_KEY and GOOGLE_MAPS_API_KEY in .env, verify corridor guideline figures, operator spot-check)
- `77923f5` test(corridors): failing tests for spacing on a fictional line with known distances
- `44b5194` feat(corridors): load and cache NH/SH geometry from OSM (Chennai-Vellore-Bengaluru first, then Tamil Nadu); fallback manual corridor CSV in data/samples with source noted
- `0f1809c` feat(corridors): snap chargers to corridor in a metric CRS with a configurable buffer
- `850c3e8` feat(corridors): compute consecutive-site spacing and flag stretches above CORRIDOR_MAX_GAP_KM and CORRIDOR_MAX_GAP_HEAVY_KM
- `643f6e3` feat(corridors): run spacing twice, all chargers and confidence >= cutoff, since OSM undercounts
- `f60066e` docs(corridors): guideline figures verified against MoP 2024 notification
- `b177e1a` feat(map): add Highway corridor gaps layer and pipeline step
- `4afa95c` test(forecast): tests using a known synthetic curve defined inside the test only
- `5b43dca` feat(forecast): loader for monthly VAHAN CSV plus data/raw/vahan_monthly_TEMPLATE.csv
- `2c69c98` feat(forecast): logistic/Bass diffusion fit (scipy), 3 to 5 year horizon
- `9e46e6a` feat(forecast): SARIMA via statsmodels (only when the series is long enough), else skipped with a stated reason
- `a964aea` feat(forecast): ensemble plus residual-bootstrap prediction intervals
- `fe5970a` feat(forecast): rolling-origin backtest reporting MAPE and MAE per model to outputs/forecast_backtest.csv
- `47cbaa1` feat(forecast): convert to future EVs per district only where a real district share exists
- `d1ca8ff` test(requirements): Erlang C against hand-computed values
- `4d840d4` feat(requirements): transparent EVs-per-port sizing (configurable), with confidence-weighted existing ports
- `5a7d857` feat(requirements): M/M/c queueing option for a target waiting time, with documented assumptions
- `c60d541` feat(requirements): seeded Monte Carlo over undercount, EV growth and charging behaviour, giving ranges
- `b17bf91` feat(requirements): outputs/charger_requirements.csv with drivers and data_flag columns
- `e2774ea` test(optimiser): tiny fictional instance with a known optimal answer
- `[pending]` feat(optimiser): candidate generation along flagged corridors and in high-gap or Gi* hot districts
