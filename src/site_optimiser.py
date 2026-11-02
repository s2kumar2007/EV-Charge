"""
EV Charging Site Selection and Optimization Module.

Inputs:
  - Corridor gap segments (corridor_gaps.geojson)
  - District gap scores and Moran's Gi* hotspots (hotspots_summary.csv)
  - District requirements deficit (charger_requirements.csv)
  - Optional real grid capacity constraints (where real substation data exists)
Outputs:
  - outputs/recommended_sites.csv: Ranked list of recommended new charging sites
  - outputs/recommended_sites.geojson: Point geometries for map layer
Assumptions:
  - Max-coverage MILP formulation under a site budget constraint.
  - Siting prioritizes flagged corridor gaps (MoP 20 km rule) and high-deficit Gi* clusters.
  - Grid constraints are applied ONLY where real capacity numbers exist; otherwise flagged 'unconstrained'.
"""
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


def solve_max_coverage_milp(
    demand_points: List[Dict[str, Any]],
    candidate_sites: List[Dict[str, Any]],
    site_budget: int,
    coverage_radius_km: float = 15.0,
    grid_capacity_mw: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Solve Maximum Coverage Location Problem (MCLP) using PuLP/CBC MILP solver."""
    raise NotImplementedError("Skeleton for test")


def generate_candidate_sites(
    corridor_gaps_df: Optional[pd.DataFrame] = None,
    hotspots_df: Optional[pd.DataFrame] = None,
    requirements_df: Optional[pd.DataFrame] = None,
    grid_capacity_data: Optional[Dict[str, float]] = None,
) -> List[Dict[str, Any]]:
    """
    Generate candidate siting locations along flagged corridors and high-deficit Gi* hotspots.

    Inputs:
      corridor_gaps_df: Gaps on highway corridors (flagged stretches).
      hotspots_df: Moran's Gi* hotspot classifications per district.
      requirements_df: Sizing deficit ports per district.
      grid_capacity_data: Real substation capacity dict if available.
    Returns:
      List of candidate site dicts with coordinates, type, priority, grid status, and drivers.
    """
    candidates = []

    # 1. Highway Corridor Gaps
    if corridor_gaps_df is not None and not corridor_gaps_df.empty:
        flagged = corridor_gaps_df
        if "flagged" in corridor_gaps_df.columns:
            flagged = corridor_gaps_df[corridor_gaps_df["flagged"] == True]

        for _, row in flagged.iterrows():
            cid = str(row.get("corridor_id", "NH"))
            start_m = float(row.get("start_distance_m", 0.0))
            end_m = float(row.get("end_distance_m", row.get("spacing_km", 0.0) * 1000.0))
            gap_km = float(row.get("spacing_km", (end_m - start_m) / 1000.0))
            midpoint_km = round((start_m + end_m) / 2000.0, 1)

            lon = float(row.get("midpoint_lon", row.get("longitude", 80.0)))
            lat = float(row.get("midpoint_lat", row.get("latitude", 13.0)))

            site_id = f"CAND-CORR-{cid}-{int(midpoint_km)}"
            grid_cap = grid_capacity_data.get(site_id) if grid_capacity_data else None
            grid_str = f"grid capacity {grid_cap:.1f} MW" if grid_cap is not None else "grid unconstrained (no official grid data available)"

            candidates.append({
                "site_id": site_id,
                "name": f"{cid} Km {midpoint_km} Waypoint",
                "corridor_id": cid,
                "site_type": "highway_corridor",
                "latitude": lat,
                "longitude": lon,
                "priority_score": round(gap_km * 2.0, 1),
                "grid_capacity_mw": grid_cap,
                "grid_constrained": grid_cap is not None,
                "drivers": f"Flagged stretch of {gap_km:.1f} km on {cid}; {grid_str}",
                "data_flag": "candidate",
            })

    # 2. Urban Hotspot & High Deficit Districts
    if hotspots_df is not None and not hotspots_df.empty:
        dist_data = hotspots_df.copy()
        if requirements_df is not None and not requirements_df.empty:
            dist_data = dist_data.merge(
                requirements_df[["district_key", "ports_deficit"]],
                on="district_key",
                how="left",
            )

        for _, row in dist_data.iterrows():
            d_name = row.get("district", "Unknown")
            d_key = row.get("district_key", str(d_name).lower().strip())
            gi_type = str(row.get("hotspot_type", "Not Significant"))
            deficit = float(row.get("ports_deficit", 0.0))
            if pd.isna(deficit):
                deficit = 0.0

            is_hot = "Hot" in gi_type
            if is_hot or deficit > 5:
                lat = float(row.get("latitude", 13.0))
                lon = float(row.get("longitude", 80.0))
                site_id = f"CAND-URBAN-{d_key}"
                grid_cap = grid_capacity_data.get(site_id) if grid_capacity_data else None
                grid_str = f"grid capacity {grid_cap:.1f} MW" if grid_cap is not None else "grid unconstrained (no official grid data available)"

                candidates.append({
                    "site_id": site_id,
                    "name": f"{d_name} Urban Hub",
                    "corridor_id": "none",
                    "site_type": "urban_hotspot",
                    "latitude": lat,
                    "longitude": lon,
                    "priority_score": round(deficit + (30.0 if is_hot else 0.0), 1),
                    "grid_capacity_mw": grid_cap,
                    "grid_constrained": grid_cap is not None,
                    "drivers": f"{gi_type} with deficit of {int(deficit)} ports; {grid_str}",
                    "data_flag": "candidate",
                })

    return candidates


def solve_corridor_frlm(
    corridor_gaps_df: pd.DataFrame,
    site_budget: int = 5,
) -> pd.DataFrame:
    """Simplified Flow-Refueling Location Model (FRLM) along priority highway corridors."""
    raise NotImplementedError("Skeleton for test")


def rank_and_export_sites(
    selected_sites: List[Dict[str, Any]],
    save_output: bool = True,
) -> pd.DataFrame:
    """Format, rank, and export recommended sites with drivers and data_flag columns."""
    raise NotImplementedError("Skeleton for test")
