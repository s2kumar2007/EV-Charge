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
from typing import Any, Dict, List, Optional, Tuple
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Point


def snap_chargers_to_corridor(
    corridor_geom: LineString,
    chargers_df: pd.DataFrame,
    buffer_meters: float = 5000.0,
    metric_crs: str = "EPSG:32644",
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
    metric_crs: str = "EPSG:32644",
) -> Tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """Calculate spacing between consecutive charging sites along corridor and flag gaps."""
    raise NotImplementedError("Skeleton for test")
