"""
Highway Corridor Gaps Analysis.

Inputs:
  - Highway corridor alignments (OSM query or fallback CSV in data/samples/)
  - Public EV chargers (deduplicated or raw)
Outputs:
  - outputs/corridor_gaps.csv: Table of consecutive-site highway stretches and gap metrics
  - outputs/corridor_gaps.geojson: LineString segments of flagged gaps for map overlays
Assumptions:
  - Metric projection (config.CORRIDOR_METRIC_CRS, default EPSG:32644) used for distances.
  - Chargers within config.CORRIDOR_BUFFER_METERS (default 5000 m) are snapped to corridor.
  - Guideline thresholds (20 km regular / 100 km heavy duty) are marked UNVERIFIED pending gazette confirmation.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import wkt
from shapely.geometry import LineString, Point
from shapely.ops import substring

import config
from utils import OUTPUTS, PROCESSED, RAW, SAMPLES, ensure_dirs, request_with_retry

CORRIDOR_CACHE = RAW / config.CORRIDOR_CACHE_FILE
CORRIDOR_FALLBACK = SAMPLES / config.CORRIDOR_FALLBACK_FILE


def load_corridors(force_fetch: bool = False) -> gpd.GeoDataFrame:
    """
    Load major highway corridor geometries:
    1. Reads cached OSM GeoJSON in data/raw/ if present.
    2. Falls back to audited manual corridor geometries in data/samples/.
    Returns GeoDataFrame in EPSG:4326.
    """
    ensure_dirs()
    if not force_fetch and CORRIDOR_CACHE.exists():
        try:
            gdf = gpd.read_file(CORRIDOR_CACHE)
            if not gdf.empty and "corridor_id" in gdf.columns:
                print(f"  [corridors] Loaded {len(gdf)} corridors from cache: {CORRIDOR_CACHE.name}")
                return gdf.to_crs(4326) if gdf.crs is not None else gdf.set_crs(4326)
        except Exception as err:
            print(f"  [warning] Failed reading cached corridors: {err}; using fallback.")

    if CORRIDOR_FALLBACK.exists():
        print(f"  [corridors] Loading fallback corridor alignments from {CORRIDOR_FALLBACK.name}")
        df = pd.read_csv(CORRIDOR_FALLBACK)
        geometries = [wkt.loads(g) for g in df["geometry_wkt"]]
        gdf = gpd.GeoDataFrame(df.drop(columns=["geometry_wkt"], errors="ignore"), geometry=geometries, crs="EPSG:4326")
        return gdf

    raise FileNotFoundError(f"Neither cached corridor file {CORRIDOR_CACHE} nor fallback {CORRIDOR_FALLBACK} found.")


def snap_chargers_to_corridor(
    corridor_geom: LineString,
    chargers_df: pd.DataFrame,
    buffer_meters: float = config.CORRIDOR_BUFFER_METERS,
    metric_crs: Optional[str] = config.CORRIDOR_METRIC_CRS,
) -> pd.DataFrame:
    """
    Snap chargers within buffer_meters of corridor_geom and compute distance along corridor.
    If metric_crs is provided, projects from EPSG:4326 to metric_crs for accurate distance.
    Returns sorted DataFrame of snapped chargers with distance_along_m and offset_m.
    """
    if chargers_df.empty:
        return pd.DataFrame(columns=list(chargers_df.columns) + ["distance_along_m", "offset_m"])

    df = chargers_df.copy()
    if "longitude" not in df.columns or "latitude" not in df.columns:
        raise ValueError("chargers_df must contain 'longitude' and 'latitude' columns.")

    # Create points geometry
    points = [Point(xy) for xy in zip(df["longitude"], df["latitude"])]

    if metric_crs:
        # Geographic coordinates in EPSG:4326 -> project to metric_crs
        chargers_gdf = gpd.GeoDataFrame(df, geometry=points, crs="EPSG:4326").to_crs(metric_crs)
        corridor_series = gpd.GeoSeries([corridor_geom], crs="EPSG:4326").to_crs(metric_crs)
        corridor_proj = corridor_series.iloc[0]
        points_proj = chargers_gdf.geometry
    else:
        # Already in Cartesian metric units
        corridor_proj = corridor_geom
        points_proj = pd.Series(points)

    # Filter within buffer
    buffer_geom = corridor_proj.buffer(buffer_meters)
    mask = points_proj.map(buffer_geom.contains)
    if not mask.any():
        return pd.DataFrame(columns=list(df.columns) + ["distance_along_m", "offset_m"])

    snapped_df = df[mask].copy().reset_index(drop=True)
    snapped_points = points_proj[mask].reset_index(drop=True)

    # Calculate along-corridor distance and perpendicular offset
    distances = [float(corridor_proj.project(pt)) for pt in snapped_points]
    offsets = [float(corridor_proj.distance(pt)) for pt in snapped_points]

    snapped_df["distance_along_m"] = distances
    snapped_df["offset_m"] = offsets

    # Sort strictly along corridor
    snapped_df = snapped_df.sort_values("distance_along_m").reset_index(drop=True)
    return snapped_df


def calculate_corridor_spacing(
    corridor_id: str,
    corridor_name: str,
    corridor_geom: LineString,
    snapped_chargers: pd.DataFrame,
    max_gap_km: float = config.CORRIDOR_MAX_GAP_KM,
    max_gap_heavy_km: float = config.CORRIDOR_MAX_GAP_HEAVY_KM,
    metric_crs: Optional[str] = config.CORRIDOR_METRIC_CRS,
) -> Tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """
    Calculate spacing between consecutive charging sites along corridor and flag gaps.
    Evaluates:
      - Origin to 1st charger
      - Consecutive chargers (i to i+1)
      - Last charger to Terminus
    Flags stretches exceeding max_gap_km (regular) and max_gap_heavy_km (heavy duty).
    Returns (gaps_df, gaps_gdf).
    """
    if metric_crs:
        corridor_series = gpd.GeoSeries([corridor_geom], crs="EPSG:4326").to_crs(metric_crs)
        corridor_proj = corridor_series.iloc[0]
    else:
        corridor_proj = corridor_geom

    total_length_m = float(corridor_proj.length)

    # Build sequence of waypoints along corridor
    waypoints = [{"label": f"{corridor_name} (Origin)", "distance_m": 0.0, "confidence": 1.0}]
    for _, row in snapped_chargers.iterrows():
        site_name = str(row.get("name") or row.get("id") or "Public Charger")
        waypoints.append({
            "label": site_name,
            "distance_m": float(row["distance_along_m"]),
            "confidence": float(row.get("confidence", 0.5)),
        })
    waypoints.append({"label": f"{corridor_name} (Terminus)", "distance_m": total_length_m, "confidence": 1.0})

    rows = []
    geoms = []

    for i in range(len(waypoints) - 1):
        w_from = waypoints[i]
        w_to = waypoints[i + 1]
        start_m = w_from["distance_m"]
        end_m = w_to["distance_m"]
        gap_m = max(0.0, end_m - start_m)
        gap_km = round(gap_m / 1000.0, 2)

        is_regular = gap_km > max_gap_km
        is_heavy = gap_km > max_gap_heavy_km

        if is_heavy:
            drivers = f"Gap {gap_km} km exceeds heavy-duty ({max_gap_heavy_km} km) & regular ({max_gap_km} km) thresholds"
        elif is_regular:
            drivers = f"Gap {gap_km} km exceeds regular threshold ({max_gap_km} km)"
        else:
            drivers = f"Adequate spacing ({gap_km} km <= {max_gap_km} km)"

        # Slice geometry along corridor
        if gap_m > 0:
            seg_proj = substring(corridor_proj, start_m, end_m)
        else:
            seg_proj = corridor_proj.interpolate(start_m)

        if metric_crs and not seg_proj.is_empty:
            seg_geo = gpd.GeoSeries([seg_proj], crs=metric_crs).to_crs("EPSG:4326").iloc[0]
        else:
            seg_geo = seg_proj

        seg_confidence = min(w_from["confidence"], w_to["confidence"])

        rows.append({
            "corridor_id": corridor_id,
            "corridor_name": corridor_name,
            "segment_index": i + 1,
            "from_location": w_from["label"],
            "to_location": w_to["label"],
            "start_km": round(start_m / 1000.0, 2),
            "end_km": round(end_m / 1000.0, 2),
            "gap_km": gap_km,
            "flag_regular_gap": is_regular,
            "flag_heavy_gap": is_heavy,
            "guideline_status": config.CORRIDOR_GUIDELINE_STATUS,
            "confidence": seg_confidence,
            "drivers": drivers,
            "data_flag": "real",
        })
        geoms.append(seg_geo)

    gaps_df = pd.DataFrame(rows)
    gaps_gdf = gpd.GeoDataFrame(gaps_df, geometry=geoms, crs="EPSG:4326")
    return gaps_df, gaps_gdf
