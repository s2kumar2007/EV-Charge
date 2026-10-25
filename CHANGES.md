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
