"""
Match names from any source (VAHAN districts or RTOs) to the district polygons.
No spelling table is used. For each name we try, in order:
  district names:  exact match -> fuzzy spelling match -> geocode and find the polygon containing the point
  RTO names:       exact match -> geocode -> fuzzy
Every match that is not exact is printed so a human can check it.
"""
import difflib
import json
import re
import time

import pandas as pd
from shapely.geometry import Point

import config
from utils import RAW, norm_key, request_with_retry

GEOCODE_CACHE = RAW / "geocode_cache.json"


def _load_cache():
    return json.loads(GEOCODE_CACHE.read_text(encoding="utf-8")) if GEOCODE_CACHE.exists() else {}


def geocode(query):
    """Ask OpenStreetMap Nominatim for [lat, lon] (or None). Answers are cached on disk."""
    cache = _load_cache()
    if query not in cache:
        response = request_with_retry("GET", config.NOMINATIM_URL, timeout=config.NETWORK_TIMEOUT_S,
                                      params={"q": query, "format": "json", "limit": 1})
        time.sleep(config.NOMINATIM_PAUSE_S)
        found = response.json()
        cache[query] = [float(found[0]["lat"]), float(found[0]["lon"])] if found else None
        GEOCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
        GEOCODE_CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return cache[query]


def clean_rto_name(name):
    """Remove office details, vehicle registration codes and the RTO label. Removes bracket text, codes and the word RTO."""
    text = re.sub(config.RTO_BRACKETS_PATTERN, " ", str(name))
    text = re.sub(config.RTO_CODE_PATTERN, " ", text)           # registration codes are matched by a configurable pattern
    text = re.sub(config.RTO_WORD_PATTERN, " ", text, flags=re.I)
    text = re.sub(r"[-,]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def resolve_one(name, boundaries, kind="district", geocode_fn=None):
    """Return (district_key, method). method is exact / fuzzy / geocode / unresolved."""
    geocode_fn = geocode_fn or geocode
    label = clean_rto_name(name) if kind == "rto" else str(name).strip()
    key = norm_key(label)
    keys = list(boundaries["district_key"])
    if not key:
        return None, "unresolved"
    if key in keys:
        return key, "exact"

    def by_spelling():
        scored = sorted(((difflib.SequenceMatcher(None, key, k).ratio(), k) for k in keys), reverse=True)
        if not scored:
            return None
        best = scored[0]
        if best[0] < config.FUZZY_CUTOFF:
            return None
        if len(scored) > 1 and best[0] - scored[1][0] < config.AMBIGUITY_MARGIN:
            return None  # two districts look equally similar: do not guess
        return best[1]

    def by_location():
        suffix = "" if kind == "rto" else " district"
        try:
            point = geocode_fn(f"{label}{suffix}, {config.STATE_NAME}, {config.COUNTRY_NAME}")
        except RuntimeError as err:
            print(f"  [warning] geocoding failed for '{label}': {err}")
            return None
        if not point:
            return None
        hit = boundaries[boundaries.geometry.contains(Point(point[1], point[0]))]
        return hit.iloc[0]["district_key"] if len(hit) == 1 else None

    steps = [("fuzzy", by_spelling), ("geocode", by_location)]
    if kind == "rto":
        steps.reverse()
    for method, step in steps:
        found = step()
        if found:
            return found, method
    return None, "unresolved"


def resolve_names(names, boundaries, kind="district", geocode_fn=None):
    """Resolve many names. Returns a table: name, district_key, method (and prints non-exact ones)."""
    rows = []
    for name in dict.fromkeys(names):          # each distinct name once, keeping order
        key, method = resolve_one(name, boundaries, kind, geocode_fn)
        rows.append({"name": name, "district_key": key, "method": method})
    table = pd.DataFrame(rows, columns=["name", "district_key", "method"])
    label = dict(zip(boundaries["district_key"], boundaries["district"]))
    for row in table[table["method"] != "exact"].itertuples():
        target = label.get(row.district_key, "-")
        print(f"  name check: '{row.name}' -> {target}  [{row.method}]")
    return table
