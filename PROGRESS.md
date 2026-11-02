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
- `[pending]` feat(map): "Corridor gaps" layer plus outputs/corridor_gaps.csv and GeoJSON, with legend and popups
