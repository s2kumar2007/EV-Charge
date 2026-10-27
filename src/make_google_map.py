"""Render a native Google Maps national view from already processed real data."""
import argparse
import html
import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode
import geopandas as gpd
import pandas as pd
from dotenv import load_dotenv
import config
from utils import ROOT, PROCESSED, OUTPUTS, save_json


def safe_json(value):
    """Source labels cannot break out of an embedded JSON script element."""
    return json.dumps(value, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def prepare_payload(boundaries, chargers, index=None, coverage=None, manifest=None):
    if boundaries.empty:
        raise ValueError("No national district polygons are available.")
    if boundaries.crs is None:
        raise ValueError("National boundary CRS is missing.")
    boundaries = boundaries.to_crs(config.WGS84).copy()
    if boundaries.district_key.isna().any() or boundaries.district_key.duplicated().any():
        raise ValueError("National district keys must be unique and present.")
    wanted = set(config.GOOGLE_MAPS_POPUP_FIELDS) | set(config.GOOGLE_MAPS_LAYERS)
    # Release-specific IDs avoid ambiguous repeated district names across India.
    for table in (coverage, index):
        if table is None or table.empty:
            continue
        if table.district_key.duplicated().any():
            raise ValueError("Duplicate national district IDs in map indicators.")
        columns = [c for c in table if c in wanted and c not in ("district", "district_key")]
        boundaries = boundaries.drop(columns=[c for c in columns if c in boundaries], errors="ignore").merge(
            table[["district_key", *columns]], on="district_key", how="left", validate="one_to_one")
    keep = [c for c in boundaries if c in wanted or c in ("district", "district_key", "geometry")]
    polygons = json.loads(boundaries[keep].to_json(drop_id=True))
    rows = chargers.copy()
    total = len(rows)
    if not config.GOOGLE_MAPS_INCLUDE_UNASSIGNED_CHARGERS and "district_key" in rows:
        rows = rows[rows.district_key.notna()].copy()
    features = []
    for record in rows.to_dict("records"):
        try:
            lat, lon = float(record["latitude"]), float(record["longitude"])
        except (TypeError, ValueError, KeyError) as err:
            raise ValueError("A charger has invalid coordinates; no location was guessed.") from err
        if not (math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("A charger has invalid coordinates; do not guess its location.")
        properties = {key: record.get(key) for key in config.GOOGLE_MAPS_CHARGER_FIELDS}
        # Pandas serialisation makes missing scalars JSON null, including nullable IDs.
        properties = json.loads(pd.Series(properties).to_json())
        features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": properties})
    bounds = [float(value) for value in boundaries.total_bounds]
    if not all(math.isfinite(value) for value in bounds):
        raise ValueError("Cannot derive a map view from invalid national bounds.")
    return {"districts": polygons, "chargers": {"type": "FeatureCollection", "features": features}, "bounds": bounds,
            "summary": {"districts": len(boundaries), "charger_records": total, "mapped_chargers": len(features),
                        "districts_with_ev": int(boundaries.ev_total.notna().sum()) if "ev_total" in boundaries else 0,
                        "snapshot_utc": (manifest or {}).get("osm_header", {}).get("snapshot_utc"),
                        "boundary_source": (manifest or {}).get("boundary_source")}}


def render_document(payload, api_key):
    if not api_key or not api_key.strip():
        raise ValueError(f"Set {config.GOOGLE_MAPS_API_KEY_ENV} in .env to generate the Google Maps view.")
    options = {"layers": config.GOOGLE_MAPS_LAYERS, "defaultLayer": config.GOOGLE_MAPS_DEFAULT_LAYER,
               "palette": config.MAP_PALETTE, "missingColour": config.NO_DATA_COLOUR,
               "outlineColour": config.OUTLINE_COLOUR, "outlineWeight": config.OUTLINE_WEIGHT,
               "polygonOpacity": config.POLYGON_OPACITY, "markerRadius": config.MARKER_RADIUS,
               "markerColour": config.SOURCE_COLOURS[config.INDIA_OSM_SOURCE],
               "initialZoom": config.GOOGLE_MAPS_INITIAL_ZOOM, "mapType": config.GOOGLE_MAPS_MAP_TYPE,
               "loadTimeoutMs": config.GOOGLE_MAPS_LOAD_TIMEOUT_MS,
               "popupFields": config.GOOGLE_MAPS_POPUP_FIELDS, "chargerFields": config.GOOGLE_MAPS_CHARGER_FIELDS,
               "searchUrl": config.GOOGLE_MAPS_SEARCH_URL, "directionsUrl": config.GOOGLE_MAPS_DIRECTIONS_URL,
               "urlVersion": config.GOOGLE_MAPS_URL_VERSION, "travelMode": config.GOOGLE_MAPS_TRAVEL_MODE,
               "note": config.GOOGLE_MAPS_NOTE}
    url = config.GOOGLE_MAPS_API_URL + "?" + urlencode({"key": api_key.strip(), "callback": "initChargeGapGoogleMap", "loading": "async", "v": config.GOOGLE_MAPS_API_VERSION})
    template = (Path(__file__).parent / config.GOOGLE_MAPS_TEMPLATE_FILE).read_text(encoding="utf-8")
    return template.replace("__CHARGEGAP_DATA__", safe_json(payload)).replace("__CHARGEGAP_OPTIONS__", safe_json(options)).replace("__CHARGEGAP_API_URL__", html.escape(url, quote=True))


def main(processed=None, output=None, api_key=None):
    if not config.GOOGLE_MAPS_ENABLED:
        return {"status": "disabled"}
    processed = PROCESSED / config.INDIA_OUTPUT_FOLDER if processed is None else Path(processed)
    output = OUTPUTS / config.INDIA_OUTPUT_FOLDER if output is None else Path(output)
    load_dotenv(ROOT / ".env")
    api_key = os.getenv(config.GOOGLE_MAPS_API_KEY_ENV, "") if api_key is None else api_key
    if not api_key.strip():
        print(f"Google Maps view skipped: set {config.GOOGLE_MAPS_API_KEY_ENV} in .env. Existing Folium output remains available.")
        return {"status": "missing API key"}
    boundary_path = processed / config.GOOGLE_MAPS_BOUNDARY_INPUT
    charger_path = processed / config.GOOGLE_MAPS_CHARGER_INPUT
    for path in (boundary_path, charger_path):
        if not path.exists():
            raise FileNotFoundError(f"Missing national map input: {path}. Run the national pipeline first.")
    def optional_csv(name):
        path = output / name
        return pd.read_csv(path, dtype={"district_key": str}) if path.exists() else None
    manifest_path = output / config.GOOGLE_MAPS_MANIFEST_INPUT
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    payload = prepare_payload(gpd.read_file(boundary_path), pd.read_csv(charger_path),
                              optional_csv(config.GOOGLE_MAPS_INDEX_INPUT), optional_csv(config.GOOGLE_MAPS_COVERAGE_INPUT), manifest)
    output.mkdir(parents=True, exist_ok=True)
    target = output / config.GOOGLE_MAPS_INDIA_FILENAME
    target.write_text(render_document(payload, api_key), encoding="utf-8")
    report = {"status": "generated; browser/API authorisation unverified", "file": target.name, **payload["summary"]}
    save_json(target.with_suffix(".manifest.json"), report)
    print(f"Google Maps view generated: {target}; districts={report['districts']}; mapped chargers={report['mapped_chargers']}. API authorisation requires browser verification.")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed")
    parser.add_argument("--output")
    args = parser.parse_args()
    main(args.processed, args.output)
