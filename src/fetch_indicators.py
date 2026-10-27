"""Choose auditable OSM sources and measure roads in each district's local CRS."""
import gzip
import hashlib
import json
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, Point
import config
from build_scores import assign_chargers_to_districts
from utils import RAW, ROOT, PROCESSED, fetch_overpass, ensure_dirs, validate_overpass


def query_for(bounds, kind):
    west, south, east, north = bounds
    prefix = f"[out:json][timeout:{config.OVERPASS_TIMEOUT_S}][bbox:{south},{west},{north},{east}];"
    if kind == "roads":
        return prefix + f"way{config.OSM_ROAD_FILTER};out geom;"
    return prefix + "(" + "".join(f"node{tag};" for tag in config.OSM_POI_FILTERS) + ");out body;"


def derive_indicators(boundaries, roads, pois):
    """None means unavailable. Empty but complete answers mean observed zero."""
    boundaries = boundaries.to_crs(config.WGS84)
    if roads is not None:
        validate_overpass(roads)
    if pois is not None:
        validate_overpass(pois)
    features = []
    for way in (roads or {}).get("elements", []):
        coords = [(p["lon"], p["lat"]) for p in way.get("geometry", [])]
        if len(coords) < 2:
            raise ValueError("An OSM road has missing geometry; its length stays missing.")
        features.append({"source_id": way.get("id"), "geometry": LineString(coords)})
    lines = gpd.GeoDataFrame(features, geometry="geometry", crs=config.WGS84) if features else gpd.GeoDataFrame(geometry=[], crs=config.WGS84)
    if features and lines.source_id.notna().all():
        lines = lines.drop_duplicates("source_id")
    assigned = None
    if pois is not None:
        nodes = pd.DataFrame([{"source_id": e["id"], "latitude": e["lat"], "longitude": e["lon"]} for e in pois["elements"]],
                             columns=["source_id", "latitude", "longitude"]).drop_duplicates("source_id")
        assigned = assign_chargers_to_districts(nodes, boundaries)
    counts = assigned.groupby("district_key").size() if assigned is not None else None
    rows = []
    for district in boundaries.itertuples():
        polygon = gpd.GeoSeries([district.geometry], crs=boundaries.crs)
        local = polygon.estimate_utm_crs()
        if local is None:
            raise ValueError("Cannot choose a local metric CRS for district geometry.")
        projected = polygon.to_crs(local).iloc[0]
        area = projected.area / config.METRES_PER_KM ** 2
        if area <= 0:
            raise ValueError("District area is zero after geometry repair.")
        length = np.nan
        if roads is not None and district.district_key in roads.get("coverage_keys", boundaries.district_key.tolist()):
            # Clip in geographic coordinates first, then project the clipped segments.
            candidates = lines.iloc[lines.sindex.query(district.geometry, predicate="intersects")].copy()
            candidates.geometry = candidates.geometry.intersection(district.geometry)
            clipped = candidates.to_crs(local).geometry
            length = clipped.union_all().length / config.METRES_PER_KM if len(clipped) else 0.0
        count = np.nan
        if pois is not None and district.district_key in pois.get("coverage_keys", boundaries.district_key.tolist()):
            count = int(counts.get(district.district_key, 0))
        rows.append({"district_key": district.district_key, "area_km2": area,
                     "road_km": length, "road_km_per_km2": length / area,
                     "commercial_count": count, "commercial_per_km2": count / area})
    return pd.DataFrame(rows)


def snapshot_date(value):
    return value.get("osm3s", {}).get("timestamp_osm_base") or value.get("snapshot_utc") or config.INDICATOR_UNKNOWN_DATE


def state_cache(boundaries, kind):
    query = query_for(boundaries.total_bounds, kind)
    path = RAW / f"{kind}_{config.STATE_SLUG}_{hashlib.sha256(query.encode()).hexdigest()}.json"
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_overpass(value)
    return value, snapshot_date(value), path.name


def national_extract():
    """Check the local PBF when present; otherwise require one identified cache."""
    from extract_india import source_identity
    from pbf_reader import header_metadata
    path = ROOT / config.INDIA_PBF_FILE
    identity = None
    date = config.INDICATOR_UNKNOWN_DATE
    if path.exists():
        identity = source_identity(path)
        cache = RAW / f"india_pbf_{identity['sha256']}_v{config.INDIA_READER_VERSION}.json.gz"
        if not cache.exists():
            return None
        date = header_metadata(path).get("snapshot_utc") or date
    else:
        candidates = sorted(RAW.glob(config.NATIONAL_EXTRACT_CACHE_PATTERN.format(version=config.INDIA_READER_VERSION)))
        if not candidates:
            return None
        if len(candidates) != 1:
            raise ValueError("Several national caches exist without the original PBF; restore the intended PBF to select its hash.")
        cache = candidates[0]
    with gzip.open(cache, "rt", encoding="utf-8") as stream:
        value = json.load(stream)
    source = value.get("source", {})
    expected = f"india_pbf_{source.get('sha256')}_v{config.INDIA_READER_VERSION}.json.gz"
    if cache.name != expected or (identity is not None and source != identity):
        raise ValueError("National extract cache provenance disagrees with its filename or local PBF.")
    manifest_path = ROOT / config.NATIONAL_EXTRACT_MANIFEST_FILE
    if date == config.INDICATOR_UNKNOWN_DATE and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("osm_source") == source:
            date = manifest.get("osm_header", {}).get("snapshot_utc") or date
    return value, date, cache.name


def clip_national(value, boundaries, kind):
    """Retain real features inside the state, including roads crossing its edge."""
    state = boundaries.to_crs(config.WGS84).geometry.union_all()
    features = []
    for element in value[kind]["elements"]:
        if kind == "pois":
            if state.covers(Point(element["lon"], element["lat"])):
                features.append(element)
        else:
            coords = [(p["lon"], p["lat"]) for p in element.get("geometry", [])]
            if len(coords) < 2:
                raise ValueError("National road cache contains incomplete geometry.")
            line = LineString(coords)
            if not line.intersects(state):
                continue
            clipped = line.intersection(state)
            pieces = [clipped] if clipped.geom_type == "LineString" else list(getattr(clipped, "geoms", []))
            for number, piece in enumerate(pieces):
                if piece.geom_type == "LineString" and not piece.is_empty:
                    features.append({"id": f"{element['id']}:{number}", "geometry": [{"lon": x, "lat": y} for x, y in piece.coords]})
    return {"elements": features}


def choose_sources(boundaries):
    downloads, provenance = {}, {}
    national = None
    national_checked = False
    allowed = {"state_cache", "national_cache", "live_overpass"}
    if not config.INDICATOR_SOURCE_ORDER or set(config.INDICATOR_SOURCE_ORDER) - allowed:
        raise ValueError("Check INDICATOR_SOURCE_ORDER in config.py.")
    for kind in ("roads", "pois"):
        downloads[kind] = None
        provenance[kind] = {"source": config.INDICATOR_MISSING_SOURCE, "snapshot_date": config.INDICATOR_UNKNOWN_DATE, "cache": ""}
        for source in config.INDICATOR_SOURCE_ORDER:
            try:
                found = None
                if source == "state_cache":
                    found = state_cache(boundaries, kind)
                elif source == "national_cache":
                    if not national_checked:
                        national = national_extract()
                        national_checked = True
                    if national is not None:
                        value, date, cache = national
                        found = clip_national(value, boundaries, kind), date, cache
                elif not config.OFFLINE:
                    value = fetch_overpass(query_for(boundaries.total_bounds, kind), kind, config.REFRESH_DOWNLOADS)
                    found = value, snapshot_date(value), ""
                if found is not None:
                    downloads[kind], date, cache = found
                    provenance[kind] = {"source": source, "snapshot_date": date, "cache": cache}
                    break
            except (RuntimeError, ValueError, OSError, KeyError) as err:
                print(f"[WARNING] {kind} source {source} unavailable: {err}")
        print(f"{kind}: {provenance[kind]}")
    return downloads, provenance


def main(boundaries):
    ensure_dirs()
    downloads, provenance = choose_sources(boundaries)
    result = derive_indicators(boundaries, downloads["roads"], downloads["pois"])
    for kind, prefix in (("roads", "road"), ("pois", "commercial")):
        for field, value in provenance[kind].items():
            result[f"{prefix}_{field}"] = value
    result.to_csv(PROCESSED / "district_osm_indicators.csv", index=False)
    return result
