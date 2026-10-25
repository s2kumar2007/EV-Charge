"""
STEP 2 - Public EV chargers.

Source 1 (always): OpenStreetMap via the Overpass API (amenity=charging_station).
Source 2 (optional): OpenChargeMap, only if OCM_API_KEY is set in a .env file.

We do NOT remove duplicates in Slice 0. Every charger keeps a "source" column.
Raw answers are cached in data/raw/, so later runs work offline.
"""
import json
import os

import pandas as pd
from dotenv import load_dotenv

from utils import PROCESSED, RAW, ROOT, ensure_dirs, request_with_retry

OSM_CACHE = RAW / "osm_chargers_tn.json"
OCM_CACHE = RAW / "ocm_chargers_tn.json"
CHARGERS_OUT = PROCESSED / "chargers_raw.csv"

# Two public Overpass servers; if the first is busy we try the second.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# "Find every charging station (point, building outline or relation) inside the
#  Tamil Nadu state boundary (ISO code IN-TN)". "out center" gives one point
#  for outlines, so everything ends up as a coordinate.
OVERPASS_QUERY = """
[out:json][timeout:180];
area["ISO3166-2"="IN-TN"]->.tn;
(
  node["amenity"="charging_station"](area.tn);
  way["amenity"="charging_station"](area.tn);
  relation["amenity"="charging_station"](area.tn);
);
out center tags;
"""

# Rough rectangle around Tamil Nadu, used only for the OpenChargeMap request.
TN_BBOX = "(8.0,76.2),(13.6,80.4)"  # (south,west),(north,east)


def fetch_osm_raw(force=False):
    """Return the raw Overpass JSON, from cache if we have it."""
    if OSM_CACHE.exists() and not force:
        print(f"  OSM: using cached file {OSM_CACHE.name}")
        return json.loads(OSM_CACHE.read_text(encoding="utf-8"))

    last_error = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            print(f"  OSM: asking {endpoint} (this can take up to a minute) ...")
            response = request_with_retry("POST", endpoint, data={"data": OVERPASS_QUERY}, timeout=240)
            data = response.json()
            if "elements" not in data:
                raise ValueError(f"unexpected answer: {str(data)[:200]}")
            OSM_CACHE.write_text(json.dumps(data), encoding="utf-8")
            return data
        except (RuntimeError, ValueError) as err:
            last_error = err
            print(f"  OSM: {endpoint} failed -> {err}")
    raise RuntimeError(
        "Could not fetch OpenStreetMap chargers from any Overpass server. "
        f"Last error: {last_error}. Try again in a few minutes."
    )


def parse_osm(data):
    """Turn raw Overpass elements into a list of simple charger rows."""
    rows = []
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        # Points have lat/lon directly; outlines have a computed "center".
        if "lat" in element:
            lat, lon = element["lat"], element["lon"]
        elif "center" in element:
            lat, lon = element["center"]["lat"], element["center"]["lon"]
        else:
            continue  # no usable location
        rows.append({
            "source": "OSM",
            "name": tags.get("name") or tags.get("brand") or "",
            "operator": tags.get("operator") or tags.get("brand") or "",
            "latitude": lat,
            "longitude": lon,
            "source_id": f"{element.get('type')}/{element.get('id')}",
        })
    return rows


def fetch_ocm_raw(api_key, force=False):
    """Return raw OpenChargeMap JSON (cached)."""
    if OCM_CACHE.exists() and not force:
        print(f"  OCM: using cached file {OCM_CACHE.name}")
        return json.loads(OCM_CACHE.read_text(encoding="utf-8"))
    params = {
        "output": "json", "countrycode": "IN", "boundingbox": TN_BBOX,
        "maxresults": 5000, "compact": "false", "verbose": "false", "key": api_key,
    }
    print("  OCM: requesting chargers ...")
    response = request_with_retry("GET", "https://api.openchargemap.io/v3/poi/", params=params, timeout=120)
    data = response.json()
    OCM_CACHE.write_text(json.dumps(data), encoding="utf-8")
    return data


def parse_ocm(data):
    """Turn raw OpenChargeMap records into the same simple row format."""
    rows = []
    for poi in data:
        address = poi.get("AddressInfo") or {}
        if address.get("Latitude") is None or address.get("Longitude") is None:
            continue
        operator = (poi.get("OperatorInfo") or {}).get("Title") or ""
        rows.append({
            "source": "OCM",
            "name": address.get("Title") or "",
            "operator": operator,
            "latitude": address["Latitude"],
            "longitude": address["Longitude"],
            "source_id": str(poi.get("ID")),
        })
    return rows


def fetch_chargers(force=False):
    """Fetch from OSM (+ OCM if a key exists) and return one table. No deduplication."""
    ensure_dirs()
    load_dotenv(ROOT / ".env")  # reads OCM_API_KEY from the .env file if present

    rows = parse_osm(fetch_osm_raw(force))
    api_key = os.getenv("OCM_API_KEY", "").strip()
    if api_key:
        try:
            rows += parse_ocm(fetch_ocm_raw(api_key, force))
        except RuntimeError as err:
            # OCM is optional: report loudly but keep going with OSM only.
            print(f"  [warning] OpenChargeMap skipped: {err}")
    else:
        print("  OCM: no OCM_API_KEY in .env -> using OpenStreetMap only.")

    columns = ["source", "name", "operator", "latitude", "longitude", "source_id"]
    chargers = pd.DataFrame(rows, columns=columns)
    chargers.to_csv(CHARGERS_OUT, index=False)
    return chargers


def main():
    chargers = fetch_chargers()
    print(f"[2/5] Chargers: {len(chargers)} fetched in total.")
    if len(chargers):
        print("  by source:", chargers["source"].value_counts().to_dict())
    else:
        print("  [warning] zero chargers fetched - every district will show 'no chargers'.")
    print(f"  saved -> {CHARGERS_OUT}")
    return chargers


if __name__ == "__main__":
    main()
