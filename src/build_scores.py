"""
STEPS 4 + 5 - Spatial join and gap score.

  * Put every charger into the district polygon that contains it.
  * Count chargers per district.
  * gap_score = EVs in district / public chargers in district  (higher = more underserved)
  * Districts with 0 chargers are marked "no chargers" and ranked as MOST underserved.
"""
import geopandas as gpd
import numpy as np
import pandas as pd

from load_boundaries import load_boundaries, report_name_mismatches
from load_vahan import load_vahan, read_vahan_file
from fetch_chargers import fetch_chargers
from utils import OUTPUTS, PROCESSED, ensure_dirs

SCORES_CSV = OUTPUTS / "district_gap_scores.csv"
SCORED_GEOJSON = PROCESSED / "districts_scored.geojson"
CHARGERS_ASSIGNED = PROCESSED / "chargers_assigned.csv"
CHARGERS_UNASSIGNED = PROCESSED / "chargers_unassigned.csv"
VAHAN_UNMATCHED = PROCESSED / "vahan_unmatched.csv"


def assign_chargers_to_districts(chargers, boundaries):
    """
    Point-in-polygon join: which district polygon does each charger sit in?
    Returns the chargers table with an added 'district' / 'district_key' column
    (empty when the point is outside every Tamil Nadu district).
    """
    points = gpd.GeoDataFrame(
        chargers.copy(),
        geometry=gpd.points_from_xy(chargers["longitude"], chargers["latitude"]),
        crs="EPSG:4326",
    )
    # Both layers must use the same coordinate system before joining.
    assert points.crs == boundaries.crs, "CRS mismatch between chargers and boundaries"

    # 'intersects' also counts points lying exactly on a district border.
    joined = gpd.sjoin(points, boundaries[["district", "district_key", "geometry"]],
                       how="left", predicate="intersects")
    # A point on a shared border could match two districts: keep the first match only.
    joined = joined[~joined.index.duplicated(keep="first")]
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right"], errors="ignore"))


def rank_districts(df):
    """
    Add gap_score, status and rank.
      rank 1 = most underserved.
      Districts with no chargers come first (biggest EV count first), then the rest by gap_score.
    """
    has_chargers = df["charger_count"] > 0
    df["gap_score"] = np.where(has_chargers, df["ev_total"] / df["charger_count"].replace(0, np.nan), np.nan)
    df["status"] = np.where(has_chargers, "ok", "no chargers")

    order = df.assign(_no_chargers=(~has_chargers).astype(int), _score=df["gap_score"].fillna(0))
    order = order.sort_values(["_no_chargers", "_score", "ev_total"], ascending=False)
    df = df.loc[order.index].copy()
    df["rank"] = range(1, len(df) + 1)
    df["gap_score"] = df["gap_score"].round(2)
    return df.reset_index(drop=True)


def main():
    ensure_dirs()
    boundaries = load_boundaries()
    chargers = fetch_chargers()

    # ---- Match district names between the map and the VAHAN file ----
    print("[4/5] Name check (VAHAN file vs boundary file):")
    boundary_names = dict(zip(boundaries["district_key"], boundaries["district"]))
    vahan_raw = read_vahan_file()
    report_name_mismatches(boundaries, vahan_raw["district"].dropna().tolist())
    ev_table, unmatched = load_vahan(boundary_names)
    pd.DataFrame({"vahan_name_without_polygon": unmatched}).to_csv(VAHAN_UNMATCHED, index=False)
    if unmatched:
        print(f"  [WARNING] these VAHAN rows are NOT on the map (no polygon): {unmatched}")

    # ---- Spatial join ----
    assigned = assign_chargers_to_districts(chargers, boundaries)
    n_total = len(chargers)
    n_assigned = int(assigned["district"].notna().sum())
    outside = assigned[assigned["district"].isna()]
    n_outside = len(outside)

    print(f"  Spatial join: {n_assigned} assigned + {n_outside} outside the districts = {n_assigned + n_outside} "
          f"(fetched: {n_total})")
    if n_assigned + n_outside != n_total:
        raise RuntimeError("Charger count mismatch after the spatial join - something was lost or duplicated.")
    print("  Check passed: assigned + unassigned = total fetched.")
    if n_outside:
        print(f"  Chargers OUTSIDE Tamil Nadu districts ({n_outside}) - first 15 shown:")
        print(outside[["source", "name", "operator", "latitude", "longitude"]].head(15).to_string(index=False))
    assigned.to_csv(CHARGERS_ASSIGNED, index=False)
    outside.to_csv(CHARGERS_UNASSIGNED, index=False)

    # ---- Count chargers per district and build the table ----
    counts = assigned.dropna(subset=["district_key"]).groupby("district_key").size().rename("charger_count")
    table = boundaries[["district", "district_key"]].merge(ev_table, on="district_key", how="left")
    table["charger_count"] = table["district_key"].map(counts).fillna(0).astype(int)

    table = rank_districts(table)

    # Optional extra metric: only if the VAHAN file really has a population column.
    columns = ["district", "ev_total", "charger_count", "gap_score", "rank", "data_flag", "status"]
    if "population" in table.columns and table["population"].notna().any():
        table["evs_per_100k"] = (table["ev_total"] / table["population"] * 100000).round(1)
        columns += ["population", "evs_per_100k"]
        print("  Population column found -> also computing EVs per 100,000 people.")

    table[columns].to_csv(SCORES_CSV, index=False)
    print(f"[5/5] Scores saved -> {SCORES_CSV}")

    # Save a map-ready copy (polygons + scores) for the map step.
    scored = boundaries[["district_key", "geometry"]].merge(table[["district_key"] + columns], on="district_key")
    gpd.GeoDataFrame(scored, geometry="geometry", crs=boundaries.crs).to_file(SCORED_GEOJSON, driver="GeoJSON")
    return table


if __name__ == "__main__":
    main()
