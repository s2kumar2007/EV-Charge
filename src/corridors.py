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
    max_gap_km: float = 20.0,
    max_gap_heavy_km: float = 100.0,
    metric_crs: Optional[str] = "EPSG:32644",
) -> Tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Calculate spacing between consecutive charging sites along corridor and flag gaps."""
    raise NotImplementedError("Skeleton for test")
