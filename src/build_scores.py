"""Assign chargers once, then score districts with known EV counts."""
import geopandas as gpd
import numpy as np
import pandas as pd
import config
from utils import OUTPUTS, PROCESSED, ensure_dirs

SCORES_CSV = OUTPUTS / "district_gap_scores.csv"
SCORED_GEOJSON = PROCESSED / "districts_scored.geojson"
CHARGERS_ASSIGNED = PROCESSED / "chargers_assigned.csv"
CHARGERS_UNASSIGNED = PROCESSED / "chargers_unassigned.csv"


def assign_chargers_to_districts(chargers, boundaries):
    """Shared-border points go to the first sorted key, never both districts."""
    points = gpd.GeoDataFrame(chargers.copy().reset_index(drop=True),
                             geometry=gpd.points_from_xy(chargers.longitude, chargers.latitude), crs=config.WGS84)
    points = points.to_crs(boundaries.crs)
    points["_record_order"] = np.arange(len(points))
    joined = gpd.sjoin(points, boundaries[["district", "district_key", "geometry"]], how="left", predicate="intersects")
    joined = joined.sort_values(["_record_order", "district_key"], na_position="last", kind="stable")
    joined = joined.drop_duplicates("_record_order").sort_values("_record_order")
    if len(joined) != len(chargers):
        raise RuntimeError("Spatial join lost or duplicated a charger.")
    return pd.DataFrame(joined.drop(columns=["geometry", "index_right", "_record_order"], errors="ignore")).reset_index(drop=True)


def rank_districts(df):
    """Rank 1 is the greatest gap. Missing EV counts never receive a rank."""
    if config.GAP_UNIT not in ("stations", "ports") or config.NO_CHARGER_POLICY not in ("smoothed", "first"):
        raise ValueError("Check GAP_UNIT and NO_CHARGER_POLICY in config.py.")
    df = df.copy()
    unit_col = "port_count" if config.GAP_UNIT == "ports" else "charger_count"
    units = df[unit_col].astype(float)
    ev = df["ev_total"].astype(float)
    if (ev.dropna() < 0).any() or (units < 0).any():
        raise ValueError("Negative EV or charger counts are invalid.")
    has_ev = ev.notna()
    df["gap_unit"] = config.GAP_UNIT
    df["status"] = np.select([~has_ev, units.eq(0)], ["no EV data", "no chargers"], default="ok")
    denominator = units.clip(lower=1) if config.NO_CHARGER_POLICY == "smoothed" else units.replace(0, np.nan)
    df["gap_score"] = ev / denominator
    ranked = df[has_ev].copy()
    ranked["_none"] = ranked[unit_col].eq(0) if config.NO_CHARGER_POLICY == "first" else False
    # A stable alphabetical tie rule makes repeated results explainable.
    order = ranked.sort_values(["_none", "gap_score", "ev_total", "district"],
                               ascending=[False, False, False, True], na_position="first", kind="stable")
    df["rank"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    df.loc[order.index, "rank"] = np.arange(1, len(order) + 1)
    return df.sort_values("rank", na_position="last", kind="stable").reset_index(drop=True)


def count_units(assigned, keys):
    valid = assigned.dropna(subset=["district_key"])
    counts = valid.groupby("district_key").size()
    ports = valid.groupby("district_key")["ports"].sum()
    return keys.map(counts).fillna(0).astype(int), keys.map(ports).fillna(0).astype(int)


def main(chargers=None, boundaries=None, ev_table=None, use_dedup=None):
    from fetch_chargers import fetch_chargers
    from load_boundaries import load_boundaries
    from load_vahan import load_vahan
    ensure_dirs()
    use_dedup = config.DEDUP_ENABLED if use_dedup is None else use_dedup
    boundaries = load_boundaries() if boundaries is None else boundaries
    raw = fetch_chargers(boundaries, force=config.REFRESH_DOWNLOADS) if chargers is None else chargers
    if ev_table is None:
        ev_table, _ = load_vahan(boundaries)
    raw_assigned = assign_chargers_to_districts(raw, boundaries)
    raw_outside = raw_assigned[raw_assigned.district.isna()]
    raw_assigned.to_csv(CHARGERS_ASSIGNED, index=False)
    raw_outside.to_csv(CHARGERS_UNASSIGNED, index=False)
    print(f"Raw chargers: {len(raw)} fetched = {len(raw) - len(raw_outside)} inside + {len(raw_outside)} outside")
    selected = raw_assigned
    if use_dedup:
        from dedupe_chargers import main as dedupe
        merged = dedupe(raw)
        selected = assign_chargers_to_districts(merged, boundaries)
        selected.to_csv(PROCESSED / "chargers_deduplicated_assigned.csv", index=False)
        selected[selected.district.isna()].to_csv(PROCESSED / "chargers_deduplicated_unassigned.csv", index=False)
        print(f"Deduplicated: {len(selected)} = {selected.district.notna().sum()} inside + {selected.district.isna().sum()} outside")
    table = boundaries[["district", "district_key"]].merge(ev_table, on="district_key", how="left", validate="one_to_one")
    table["raw_charger_count"], table["raw_port_count"] = count_units(raw_assigned, table.district_key)
    table["charger_count"], table["port_count"] = count_units(selected, table.district_key)
    table["count_basis"] = "deduplicated" if use_dedup else "raw"
    table = rank_districts(table)
    if "population" in table:
        table["evs_per_100k"] = table.ev_total / table.population.where(table.population > 0) * config.PER_100K
    filename = "district_gap_scores_deduplicated.csv" if use_dedup else SCORES_CSV.name
    columns = ["district", "ev_total", "charger_count", "port_count", "gap_score", "gap_unit", "rank", "data_flag", "status",
               "raw_charger_count", "raw_port_count", "count_basis", "district_key"]
    columns += [c for c in ("population", "evs_per_100k") if c in table]
    table[columns].to_csv(OUTPUTS / filename, index=False)
    geo = boundaries[["district_key", "geometry"]].merge(table, on="district_key", validate="one_to_one")
    target = PROCESSED / "districts_scored_deduplicated.geojson" if use_dedup else SCORED_GEOJSON
    gpd.GeoDataFrame(geo, crs=boundaries.crs).to_file(target, driver="GeoJSON")
    return table


if __name__ == "__main__":
    main()
