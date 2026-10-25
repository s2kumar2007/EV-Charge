"""
STEP 3 - Public EV chargers.
Source 1 (always): OpenStreetMap via Overpass (amenity=charging_station).
Source 2 (optional): OpenChargeMap, only if OCM_API_KEY is set in .env.
The search area is the bounding box of the district boundaries, so nothing about the state is hardcoded.
Chargers that fall outside every district are removed later, in the spatial join.
No deduplication yet (that is Slice 1). Raw answers are cached in data/raw/.
"""
import json
import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv

import config
from utils import PROCESSED, RAW, ROOT, ensure_dirs, request_with_retry

OSM_CACHE = RAW / f"osm_chargers_{config.STATE_SLUG}.json"
OCM_CACHE = RAW / f"ocm_chargers_{config.STATE_SLUG}.json"
CHARGERS_OUT = PROCESSED / "chargers_raw.csv"


def overpass_query(bounds):
    west, south, east, north = bounds
    return (f"[out:json][timeout:{config.OVERPASS_TIMEOUT_S}][bbox:{south},{west},{north},{east}];\n"
            '(node["amenity"="charging_station"];way["amenity"="charging_station"];'
            'relation["amenity"="charging_station"];);\nout center tags;')


def fetch_osm_raw(bounds, force=False):
    if OSM_CACHE.exists() and not force:
        print(f"  OSM: using cached file {OSM_CACHE.name}")
        return json.loads(OSM_CACHE.read_text(encoding="utf-8"))
    last_error = None
    for endpoint in config.OVERPASS_ENDPOINTS:
        try:
            print(f"  OSM: asking {endpoint} (can take up to a minute) ...")
            response = request_with_retry("POST", endpoint, data={"data": overpass_query(bounds)},
                                          timeout=config.OVERPASS_TIMEOUT_S + 60)
            data = response.json()
            if "elements" not in data:
                raise ValueError(f"unexpected answer: {str(data)[:200]}")
            OSM_CACHE.write_text(json.dumps(data), encoding="utf-8")
            return data
        except (RuntimeError, ValueError) as err:
            last_error = err
            print(f"  OSM: {endpoint} failed -> {err}")
    raise RuntimeError(f"Could not fetch OpenStreetMap chargers from any Overpass server. Last error: {last_error}")


def parse_ports(val):
    """
    Parse a capacity (OSM) or NumberOfPoints (OCM) value.
    Returns (ports: int, ports_known: bool).
    A valid positive integer returns (val, True).
    Missing, invalid, zero or negative values default to (1, False).
    """
    if val is None or pd.isna(val):
        return 1, False
    try:
        if isinstance(val, str):
            val = val.strip()
            num = int(val)
        elif isinstance(val, (int, np.integer)):
            num = int(val)
        elif isinstance(val, float) and val.is_integer():
            num = int(val)
        else:
            return 1, False
        if num > 0:
            return num, True
    except (ValueError, TypeError, OverflowError):
        pass
    return 1, False


def parse_osm(data):
    rows = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        if "lat" in element:
            lat, lon = element["lat"], element["lon"]
        elif "center" in element:
            lat, lon = element["center"]["lat"], element["center"]["lon"]
        else:
            continue
        ports, ports_known = parse_ports(tags.get("capacity"))
        rows.append({"source": "OSM", "name": tags.get("name") or tags.get("brand") or "",
                     "operator": tags.get("operator") or tags.get("brand") or "",
                     "latitude": lat, "longitude": lon,
                     "source_id": f"{element.get('type')}/{element.get('id')}",
                     "ports": ports, "ports_known": ports_known})
    return rows


def fetch_ocm_raw(api_key, bounds, force=False):
    if OCM_CACHE.exists() and not force:
        print(f"  OCM: using cached file {OCM_CACHE.name}")
        return json.loads(OCM_CACHE.read_text(encoding="utf-8"))
    west, south, east, north = bounds
    params = {"output": "json", "boundingbox": f"({south},{west}),({north},{east})",
              "maxresults": config.OCM_MAX_RESULTS, "compact": "false", "verbose": "false", "key": api_key}
    print("  OCM: requesting chargers ...")
    data = request_with_retry("GET", config.OCM_URL, params=params, timeout=120).json()
    OCM_CACHE.write_text(json.dumps(data), encoding="utf-8")
    return data


def parse_ocm(data):
    rows = []
    for poi in data:
        address = poi.get("AddressInfo") or {}
        if address.get("Latitude") is None or address.get("Longitude") is None:
            continue
        ports, ports_known = parse_ports(poi.get("NumberOfPoints"))
        rows.append({"source": "OCM", "name": address.get("Title") or "",
                     "operator": (poi.get("OperatorInfo") or {}).get("Title") or "",
                     "latitude": address["Latitude"], "longitude": address["Longitude"],
                     "source_id": str(poi.get("ID")),
                     "ports": ports, "ports_known": ports_known})
    return rows


def fetch_chargers(boundaries, force=False):
    """Fetch from OSM (+ OCM if a key exists). boundaries decides the search area."""
    ensure_dirs()
    load_dotenv(ROOT / ".env")
    bounds = tuple(boundaries.total_bounds)           # (west, south, east, north)

    rows = parse_osm(fetch_osm_raw(bounds, force))
    api_key = os.getenv("OCM_API_KEY", "").strip()
    if api_key:
        try:
            rows += parse_ocm(fetch_ocm_raw(api_key, bounds, force))
        except RuntimeError as err:
            print(f"  [warning] OpenChargeMap skipped: {err}")
    else:
        print("  OCM: no OCM_API_KEY in .env -> using OpenStreetMap only.")

    chargers = pd.DataFrame(rows, columns=["source", "name", "operator", "latitude", "longitude",
                                           "source_id", "ports", "ports_known"])
    chargers.to_csv(CHARGERS_OUT, index=False)
    return chargers


def main():
    from load_boundaries import load_boundaries
    chargers = fetch_chargers(load_boundaries())
    print(f"[3/5] Chargers: {len(chargers)} fetched in the search area (some may lie outside the districts).")
    if len(chargers):
        print("  by source:", chargers["source"].value_counts().to_dict())
    else:
        print("  [warning] zero chargers fetched - every district will show 'no chargers'.")
    return chargers


if __name__ == "__main__":
    main()
