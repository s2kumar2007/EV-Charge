"""Derive road length and commercial node density from cached Overpass downloads."""
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString
import config
from build_scores import assign_chargers_to_districts
from utils import PROCESSED, fetch_overpass, ensure_dirs


def query_for(bounds, kind):
    west, south, east, north = bounds
    prefix = f"[out:json][timeout:{config.OVERPASS_TIMEOUT_S}][bbox:{south},{west},{north},{east}];"
    if kind == "roads":
        return prefix + f"way{config.OSM_ROAD_FILTER};out geom;"
    # This proxy deliberately counts nodes only, avoiding node/polygon doubles.
    return prefix + "(" + "".join(f"node{tag};" for tag in config.OSM_POI_FILTERS) + ");out body;"


def derive_indicators(boundaries, roads, pois):
    """Clip every road to its district, so crossing roads are not counted whole."""
    metric_crs = boundaries.estimate_utm_crs()
    if metric_crs is None:
        raise ValueError("Cannot choose a metric CRS for road lengths and areas.")
    districts = boundaries.to_crs(metric_crs)
    result = boundaries[["district_key"]].copy()
    area = districts.geometry.area / config.METRES_PER_KM ** 2
    if (area <= 0).any():
        raise ValueError("District area is zero after geometry repair.")
    result["area_km2"] = area.to_numpy()
    lengths = dict.fromkeys(result.district_key, 0.0)
    if roads is None:
        result["road_km_per_km2"] = np.nan
    else:
        features = []
        for way in roads["elements"]:
            coordinates = [(p["lon"], p["lat"]) for p in way.get("geometry", [])]
            if len(coordinates) < 2:
                raise ValueError("An OSM road has missing geometry; refusing to treat it as zero length.")
            features.append({"source_id": way["id"], "geometry": LineString(coordinates)})
        if features:
            lines = gpd.GeoDataFrame(features, crs=config.WGS84).drop_duplicates("source_id").to_crs(metric_crs)
            for row in districts.itertuples():
                candidates = lines.iloc[lines.sindex.query(row.geometry, predicate="intersects")]
                # Union removes coincident geometry along the same mapped road.
                clipped = candidates.geometry.intersection(row.geometry)
                lengths[row.district_key] = clipped.union_all().length / config.METRES_PER_KM if len(clipped) else 0
        result["road_km_per_km2"] = result.district_key.map(lengths) / result.area_km2
    if pois is None:
        result["commercial_per_km2"] = np.nan
    else:
        nodes = pd.DataFrame([{"source_id": e["id"], "latitude": e["lat"], "longitude": e["lon"]}
                              for e in pois["elements"]], columns=["source_id", "latitude", "longitude"]).drop_duplicates("source_id")
        assigned = assign_chargers_to_districts(nodes, boundaries)
        counts = assigned.groupby("district_key").size()
        result["commercial_per_km2"] = result.district_key.map(counts).fillna(0) / result.area_km2
    return result


def main(boundaries):
    ensure_dirs()
    downloads = {}
    for kind in ("roads", "pois"):
        try:
            downloads[kind] = fetch_overpass(query_for(boundaries.total_bounds, kind), kind, config.REFRESH_DOWNLOADS)
        except (RuntimeError, ValueError) as err:
            print(f"[WARNING] {kind} unavailable: {err}. Indicator is missing, never zero-filled.")
            downloads[kind] = None
    result = derive_indicators(boundaries, downloads["roads"], downloads["pois"])
    result.to_csv(PROCESSED / "district_osm_indicators.csv", index=False)
    return result
