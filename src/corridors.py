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
    buffer_meters: float = 5000.0,
    metric_crs: Optional[str] = "EPSG:32644",
) -> pd.DataFrame:
    """Snap chargers within buffer_meters of corridor_geom and compute distance along corridor."""
    raise NotImplementedError("Skeleton for test")


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
