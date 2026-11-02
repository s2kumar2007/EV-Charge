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
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import pulp
import geopandas as gpd
from shapely.geometry import Point

import config
from utils import OUTPUTS, ensure_dirs


def _calc_distance_km(p1: Dict[str, Any], p2: Dict[str, Any]) -> float:
    """Compute distance between two points in km, supporting Cartesian (x, y) or Geographic (lat, lon)."""
    if "x" in p1 and "x" in p2:
        dx = float(p1["x"]) - float(p2["x"])
        dy = float(p1.get("y", 0.0)) - float(p2.get("y", 0.0))
        return math.hypot(dx, dy)

    # Geographic coordinates (Haversine formula)
    lat1 = math.radians(float(p1.get("latitude", p1.get("lat", 0.0))))
    lon1 = math.radians(float(p1.get("longitude", p1.get("lon", 0.0))))
    lat2 = math.radians(float(p2.get("latitude", p2.get("lat", 0.0))))
    lon2 = math.radians(float(p2.get("longitude", p2.get("lon", 0.0))))

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2.0) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return 6371.0 * c


def solve_max_coverage_milp(
    demand_points: List[Dict[str, Any]],
    candidate_sites: List[Dict[str, Any]],
    site_budget: int,
    coverage_radius_km: float = 15.0,
    grid_capacity_mw: Optional[Dict[str, float]] = None,
    power_demand_per_site_mw: float = 1.0,
) -> Dict[str, Any]:
    """
    Solve Maximum Coverage Location Problem (MCLP) using PuLP/CBC MILP solver.

    Inputs:
      demand_points: List of dicts with 'id', 'weight' (or 'ev_total' / 'deficit'), and coords.
      candidate_sites: List of dicts with 'site_id', 'name', and coords.
      site_budget: Maximum number of candidate sites to select.
      coverage_radius_km: Service coverage radius in km.
      grid_capacity_mw: Optional real substation capacity constraints per site_id.
    Returns:
      dict with status, total_covered_weight, selected_sites, covered_demand_ids, drivers.
    """
    if not demand_points or not candidate_sites or site_budget <= 0:
        return {
            "status": "trivial",
            "total_covered_weight": 0.0,
            "selected_sites": [],
            "covered_demand_ids": [],
            "uncovered_demand_ids": [d.get("id", str(i)) for i, d in enumerate(demand_points)],
            "drivers": "Empty instance or zero site budget",
            "data_flag": "insufficient_data",
        }

    # 1. Determine coverage matrix N_i = list of candidate indices covering demand i
    coverage_map = {i: [] for i in range(len(demand_points))}
    for i_idx, d_pt in enumerate(demand_points):
        for j_idx, c_site in enumerate(candidate_sites):
            dist = _calc_distance_km(d_pt, c_site)
            if dist <= coverage_radius_km:
                coverage_map[i_idx].append(j_idx)

    # 2. Build MILP Model
    prob = pulp.LpProblem("EV_Max_Coverage", pulp.LpMaximize)

    # Decision variables
    y = {j: pulp.LpVariable(f"y_{j}", cat=pulp.LpBinary) for j in range(len(candidate_sites))}
    x = {i: pulp.LpVariable(f"x_{i}", cat=pulp.LpBinary) for i in range(len(demand_points))}

    # Objective: Maximize sum_{i} weight_i * x_i
    weights = [float(d.get("weight", d.get("ev_total", d.get("ports_deficit", 1.0)))) for d in demand_points]
    prob += pulp.lpSum([weights[i] * x[i] for i in range(len(demand_points))])

    # Constraint 1: x_i <= sum_{j in N_i} y_j
    for i in range(len(demand_points)):
        covering_candidates = coverage_map[i]
        if covering_candidates:
            prob += x[i] <= pulp.lpSum([y[j] for j in covering_candidates])
        else:
            prob += x[i] == 0

    # Constraint 2: Site budget constraint sum_{j} y_j <= site_budget
    prob += pulp.lpSum([y[j] for j in range(len(candidate_sites))]) <= site_budget

    # Constraint 3: Real grid capacity constraint (ONLY where real grid data exists)
    if grid_capacity_mw:
        for j, c_site in enumerate(candidate_sites):
            s_id = c_site.get("site_id", "")
            if s_id in grid_capacity_mw:
                real_cap = float(grid_capacity_mw[s_id])
                if power_demand_per_site_mw > real_cap:
                    # Site power exceeds real substation capacity: cannot select
                    prob += y[j] == 0

    # Solve with CBC
    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    status_str = pulp.LpStatus[prob.status].lower()

    selected_sites = []
    for j in range(len(candidate_sites)):
        if pulp.value(y[j]) is not None and pulp.value(y[j]) > 0.5:
            cand_copy = dict(candidate_sites[j])
            cand_copy["selected"] = True
            selected_sites.append(cand_copy)

    covered_ids = []
    uncovered_ids = []
    total_cov_weight = 0.0
    for i, d_pt in enumerate(demand_points):
        d_id = str(d_pt.get("id", d_pt.get("district_key", f"D{i}")))
        if pulp.value(x[i]) is not None and pulp.value(x[i]) > 0.5:
            covered_ids.append(d_id)
            total_cov_weight += weights[i]
        else:
            uncovered_ids.append(d_id)

    grid_info = "grid capacity constrained" if grid_capacity_mw else "grid capacity unconstrained (no official grid data available)"
    drivers = (
        f"MCLP MILP: {len(selected_sites)} sites selected under budget {site_budget}; "
        f"covered {len(covered_ids)}/{len(demand_points)} demand points ({total_cov_weight:.1f} weight); {grid_info}"
    )

    return {
        "status": status_str,
        "total_covered_weight": round(total_cov_weight, 2),
        "selected_sites": selected_sites,
        "covered_demand_ids": covered_ids,
        "uncovered_demand_ids": uncovered_ids,
        "drivers": drivers,
        "data_flag": "optimal" if status_str == "optimal" else "feasible",
    }


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
    road_class_weights: Optional[Dict[str, float]] = None,
    max_spacing_km: float = 20.0,
) -> pd.DataFrame:
    """
    Simplified Flow-Refueling Location Model (FRLM) along priority highway corridors.

    Inputs:
      corridor_gaps_df: DataFrame of corridor stretches (flagged or unflagged).
      site_budget: Maximum number of new charging sites to recommend.
      road_class_weights: Flow weight multiplier per road hierarchy (NH vs SH vs Expressway).
      max_spacing_km: Maximum allowable distance between consecutive charging sites (default 20 km).
    Returns:
      pd.DataFrame of recommended charging site locations along corridors.
    """
    if corridor_gaps_df.empty or site_budget <= 0:
        return pd.DataFrame()

    weights = road_class_weights or {"EXPRESSWAY": 2.0, "NH": 1.5, "SH": 1.0, "OTHER": 0.8}

    gaps = corridor_gaps_df.copy()
    if "flagged" in gaps.columns:
        gaps = gaps[gaps["flagged"] == True]

    if gaps.empty:
        return pd.DataFrame()

    records = []
    for _, row in gaps.iterrows():
        cid = str(row.get("corridor_id", "NH"))
        if "exp" in cid.lower():
            r_class = "EXPRESSWAY"
        elif "nh" in cid.lower():
            r_class = "NH"
        elif "sh" in cid.lower():
            r_class = "SH"
        else:
            r_class = "OTHER"

        w = weights.get(r_class, 1.0)
        gap_km = float(row.get("spacing_km", 0.0))
        start_m = float(row.get("start_distance_m", 0.0))
        end_m = float(row.get("end_distance_m", start_m + gap_km * 1000.0))
        flow_score = gap_km * w

        records.append({
            "row": row,
            "corridor_id": cid,
            "corridor_name": row.get("corridor_name", cid),
            "road_class": r_class,
            "weight": w,
            "gap_km": gap_km,
            "start_m": start_m,
            "end_m": end_m,
            "flow_score": flow_score,
            "start_lon": float(row.get("start_lon", row.get("longitude", 80.0))),
            "start_lat": float(row.get("start_lat", row.get("latitude", 13.0))),
            "end_lon": float(row.get("end_lon", row.get("longitude", 80.0))),
            "end_lat": float(row.get("end_lat", row.get("latitude", 13.0))),
        })

    # Sort corridors by flow refueling priority descending
    records.sort(key=lambda x: x["flow_score"], reverse=True)

    recommended = []
    sites_allocated = 0

    for item in records:
        if sites_allocated >= site_budget:
            break

        gap_km = item["gap_km"]
        stations_needed = max(1, int(math.ceil(gap_km / max_spacing_km)) - 1)
        stations_to_add = min(stations_needed, site_budget - sites_allocated)

        for s in range(1, stations_to_add + 1):
            fraction = s / (stations_to_add + 1)
            dist_along = item["start_m"] + fraction * (item["end_m"] - item["start_m"])
            mid_km = round(dist_along / 1000.0, 1)

            site_lon = item["start_lon"] + fraction * (item["end_lon"] - item["start_lon"])
            site_lat = item["start_lat"] + fraction * (item["end_lat"] - item["start_lat"])

            site_id = f"REC-CORR-{item['corridor_id']}-{int(mid_km)}"
            recommended.append({
                "site_id": site_id,
                "name": f"{item['corridor_name']} Waypoint (Km {mid_km})",
                "corridor_id": item["corridor_id"],
                "road_class": item["road_class"],
                "distance_along_km": mid_km,
                "latitude": round(site_lat, 6),
                "longitude": round(site_lon, 6),
                "ports_recommended": 4 if item["road_class"] in ["EXPRESSWAY", "NH"] else 2,
                "priority_score": round(item["flow_score"] / stations_needed, 2),
                "confidence": 0.85,
                "drivers": (
                    f"FRLM corridor siting ({item['road_class']} weight {item['weight']:.1f}): "
                    f"divides {gap_km:.1f} km gap into <= {max_spacing_km:.0f} km compliant segments"
                ),
                "data_flag": "recommended",
            })
            sites_allocated += 1

    return pd.DataFrame(recommended)


def rank_and_export_sites(
    selected_sites: List[Dict[str, Any]],
    save_output: bool = True,
) -> Tuple[pd.DataFrame, gpd.GeoDataFrame]:
    """
    Format, rank, and export recommended sites with drivers and data_flag columns.

    Inputs:
      selected_sites: List of selected candidate site dicts.
      save_output: If True, writes outputs/recommended_sites.csv and outputs/recommended_sites.geojson.
    Returns:
      (DataFrame, GeoDataFrame)
    """
    if not selected_sites:
        empty_df = pd.DataFrame(columns=[
            "rank", "site_id", "name", "site_type", "corridor_id", "latitude", "longitude",
            "ports_recommended", "priority_score", "confidence", "drivers", "data_flag",
        ])
        empty_gdf = gpd.GeoDataFrame(empty_df, geometry=[], crs="EPSG:4326")
        return empty_df, empty_gdf

    df = pd.DataFrame(selected_sites)
    # Sort by priority_score descending
    if "priority_score" in df.columns:
        df = df.sort_values(by="priority_score", ascending=False).reset_index(drop=True)

    # 1-based integer rank
    df["rank"] = np.arange(1, len(df) + 1, dtype="int64")

    # Standard columns
    cols_order = [
        "rank", "site_id", "name", "site_type", "corridor_id", "latitude", "longitude",
        "ports_recommended", "priority_score", "confidence", "drivers", "data_flag",
    ]
    for c in cols_order:
        if c not in df.columns:
            if c == "ports_recommended":
                df[c] = 4
            elif c == "confidence":
                df[c] = 0.85
            elif c == "data_flag":
                df[c] = "recommended"
            elif c == "corridor_id":
                df[c] = "none"
            else:
                df[c] = ""

    df = df[cols_order]

    # Convert to GeoDataFrame
    geometry = [Point(xy) for xy in zip(df["longitude"], df["latitude"])]
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs="EPSG:4326")

    if save_output:
        ensure_dirs()
        csv_path = OUTPUTS / getattr(config, "OPTIMISER_OUTPUT_CSV", "recommended_sites.csv")
        geojson_path = OUTPUTS / getattr(config, "OPTIMISER_OUTPUT_GEOJSON", "recommended_sites.geojson")

        df.to_csv(csv_path, index=False)
        gdf.to_file(geojson_path, driver="GeoJSON")
        print(f"Saved {len(df)} recommended sites to {csv_path} and {geojson_path}")

    return df, gdf


def main():
    """Run end-to-end site optimization pipeline."""
    print("[1/3] Loading corridor gaps, hotspot clusters, and requirements deficits...")
    ensure_dirs()
    total_budget = getattr(config, "OPTIMISER_BUDGET_SITES", 15)
    corridor_budget = total_budget // 2
    urban_budget = total_budget - corridor_budget

    corridor_file = OUTPUTS / "corridor_gaps.csv"
    hotspots_file = OUTPUTS / "hotspots_summary.csv"
    req_file = OUTPUTS / "charger_requirements.csv"

    selected_sites = []

    # 1. Highway Corridors FRLM
    if corridor_file.exists():
        c_df = pd.read_csv(corridor_file)
        frlm_df = solve_corridor_frlm(c_df, site_budget=corridor_budget)
        if not frlm_df.empty:
            selected_sites.extend(frlm_df.to_dict("records"))
            print(f"  Allocated {len(frlm_df)} corridor charging sites along flagged highways.")

    # 2. Urban Hotspot & Deficit Max-Coverage MILP
    if hotspots_file.exists() or req_file.exists():
        h_df = pd.read_csv(hotspots_file) if hotspots_file.exists() else pd.DataFrame()
        r_df = pd.read_csv(req_file) if req_file.exists() else pd.DataFrame()

        # Build demand points from requirements or hotspots
        demand_points = []
        source_df = r_df if not r_df.empty else h_df
        for _, r in source_df.iterrows():
            d_flag = str(r.get("data_flag", "real")).lower()
            if d_flag == "real":
                deficit = float(r.get("ports_deficit", r.get("ports_deficit_p50", 10.0)))
                if pd.notna(deficit) and deficit > 0:
                    demand_points.append({
                        "id": str(r.get("district_key", r.get("district", "dist"))),
                        "weight": deficit,
                        "latitude": float(r.get("latitude", 13.0)),
                        "longitude": float(r.get("longitude", 80.0)),
                    })

        candidates = generate_candidate_sites(None, h_df, r_df)
        urban_cands = [c for c in candidates if c["site_type"] == "urban_hotspot"]
        if urban_cands and demand_points:
            milp_res = solve_max_coverage_milp(
                demand_points,
                urban_cands,
                site_budget=urban_budget,
                coverage_radius_km=getattr(config, "OPTIMISER_COVERAGE_RADIUS_KM", 15.0),
            )
            for s in milp_res["selected_sites"]:
                s["ports_recommended"] = 6
                selected_sites.append(s)
            print(f"  Allocated {len(milp_res['selected_sites'])} urban charging sites via MCLP MILP.")

    print("[2/3] Ranking and exporting recommended charging sites...")
    df, gdf = rank_and_export_sites(selected_sites, save_output=True)
    return df


if __name__ == "__main__":
    main()
