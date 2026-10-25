"""
STEPS 4 + 5 - Spatial join and gap score.
  * Put every charger into the district polygon that contains it; count chargers per district.
  * gap_score = EVs in district / public chargers in district  (higher = more underserved)
  * status: ok / no chargers / no EV data.  Districts with no EV data are not ranked.
  * The treatment of districts with 0 chargers is set by NO_CHARGER_POLICY in config.py.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

import config
from fetch_chargers import fetch_chargers
from load_boundaries import load_boundaries
from load_vahan import load_vahan
from utils import OUTPUTS, PROCESSED, ensure_dirs

SCORES_CSV = OUTPUTS / "district_gap_scores.csv"
SCORED_GEOJSON = PROCESSED / "districts_scored.geojson"
CHARGERS_ASSIGNED = PROCESSED / "chargers_assigned.csv"
CHARGERS_UNASSIGNED = PROCESSED / "chargers_unassigned.csv"


def assign_chargers_to_districts(chargers, boundaries):
    """Point-in-polygon join. Chargers outside every district get an empty 'district'."""
    points = gpd.GeoDataFrame(chargers.copy(),
                              geometry=gpd.points_from_xy(chargers["longitude"], chargers["latitude"]),
                              crs="EPSG:4326")
    assert points.crs == boundaries.crs, "CRS mismatch between chargers and boundaries"
    joined = gpd.sjoin(points, boundaries[["district", "district_key", "geometry"]],
                       how="left", predicate="intersects")
    joined = joined[~joined.index.duplicated(keep="first")]   # a point on a shared border: keep one match
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))


def rank_districts(df):
    """Add gap_score, status and rank (rank 1 = most underserved). Districts without EV data get no rank."""
    df = df.copy()
    ev = df["ev_total"].astype(float)
    has_ev, has_ch = ev.notna(), df["charger_count"] > 0
    df["status"] = np.select([~has_ev, ~has_ch], ["no EV data", "no chargers"], default="ok")
    df["gap_score"] = np.where(has_ev & has_ch, ev / df["charger_count"].replace(0, np.nan), np.nan)

    ranked = df[has_ev].copy()
    ranked_ev = ranked["ev_total"].astype(float)
    if config.NO_CHARGER_POLICY == "smoothed":
        ranked["gap_score"] = ranked_ev / ranked["charger_count"].clip(lower=1)
        order = ranked.assign(_ev=ranked_ev).sort_values(["gap_score", "_ev"], ascending=False)
    else:  # "first"
        order = ranked.assign(_none=(ranked["charger_count"] == 0).astype(int),
                              _score=ranked["gap_score"].fillna(0), _ev=ranked_ev
                              ).sort_values(["_none", "_score", "_ev"], ascending=False)
    df.loc[order.index, "rank"] = np.arange(1, len(order) + 1)
    if config.NO_CHARGER_POLICY == "smoothed":
        df.loc[ranked.index, "gap_score"] = ranked["gap_score"]
    df["gap_score"] = df["gap_score"].round(2)
    return df.sort_values("rank", na_position="last").reset_index(drop=True)


def main():
    ensure_dirs()
    boundaries = load_boundaries()
    chargers = fetch_chargers(boundaries)

    print("[4/5] Name check (VAHAN names vs boundary districts):")
    ev_table, _ = load_vahan(boundaries)

    assigned = assign_chargers_to_districts(chargers, boundaries)
    n_total, n_in = len(chargers), int(assigned["district"].notna().sum())
    outside = assigned[assigned["district"].isna()]
    print(f"  Spatial join: {n_in} inside districts + {len(outside)} outside = {n_in + len(outside)} (fetched: {n_total})")
    if n_in + len(outside) != n_total:
        raise RuntimeError("Charger count mismatch after the spatial join - something was lost or duplicated.")
    print("  Check passed: inside + outside = total fetched.")
    assigned.to_csv(CHARGERS_ASSIGNED, index=False)
    outside.to_csv(CHARGERS_UNASSIGNED, index=False)

    counts = assigned.dropna(subset=["district_key"]).groupby("district_key").size().rename("charger_count")
    table = boundaries[["district", "district_key"]].merge(ev_table, on="district_key", how="left")
    table["charger_count"] = table["district_key"].map(counts).fillna(0).astype(int)
    table = rank_districts(table)

    columns = ["district", "ev_total", "charger_count", "gap_score", "rank", "data_flag", "status"]
    if "population" in table.columns and table["population"].notna().any():
        table["evs_per_100k"] = (table["ev_total"].astype(float) / table["population"] * 100000).round(1)
        columns += ["population", "evs_per_100k"]
        print("  Population column found -> also computing EVs per 100,000 people.")
    table[columns].to_csv(SCORES_CSV, index=False)
    print(f"[5/5] Scores saved -> {SCORES_CSV}")

    scored = boundaries[["district_key", "geometry"]].merge(table[["district_key"] + columns], on="district_key")
    for col in ("ev_total", "rank"):
        scored[col] = scored[col].astype(float)           # empty values become null in the map file
    gpd.GeoDataFrame(scored, geometry="geometry", crs=boundaries.crs).to_file(SCORED_GEOJSON, driver="GeoJSON")
    return table


if __name__ == "__main__":
    main()
