"""Sanity checks. Run after run_all.py:  python checks.py"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SCORES = ROOT / "outputs" / "district_gap_scores.csv"
CHARGERS_RAW = ROOT / "data" / "processed" / "chargers_raw.csv"
UNASSIGNED = ROOT / "data" / "processed" / "chargers_unassigned.csv"
RESOLUTION = ROOT / "data" / "processed" / "vahan_name_resolution.csv"


def main():
    if not SCORES.exists():
        print("outputs/district_gap_scores.csv not found - run  python run_all.py  first.")
        sys.exit(1)
    df = pd.read_csv(SCORES)
    print("=== ChargeGap Slice 0 sanity checks ===")
    print(f"Districts in results:          {len(df)}")
    print(f"Total EVs (sum of districts):  {int(df['ev_total'].sum()):,}")
    print(f"Chargers counted in districts: {int(df['charger_count'].sum())}")
    if CHARGERS_RAW.exists():
        fetched = len(pd.read_csv(CHARGERS_RAW))
        outside = len(pd.read_csv(UNASSIGNED)) if UNASSIGNED.exists() else 0
        ok = "OK" if fetched == int(df["charger_count"].sum()) + outside else "MISMATCH!"
        print(f"Chargers fetched: {fetched} = in districts + {outside} outside  -> {ok}")

    cols = ["rank", "district", "ev_total", "charger_count", "gap_score", "data_flag"]
    ranked = df[df["rank"].notna()]
    print("\nTop 5 MOST underserved (rank 1 = worst):")
    print(ranked.sort_values("rank").head(5)[cols].to_string(index=False) if len(ranked) else "  (nothing ranked: no EV data)")
    served = df[(df["charger_count"] > 0) & df["gap_score"].notna()].sort_values("gap_score")
    print("\nBest served 5 (lowest gap_score, districts that have chargers):")
    print(served.head(5)[cols].to_string(index=False) if len(served) else "  (no district has both chargers and EV data)")

    print("\n--- Missing / flagged data ---")
    for label, mask in [("NO chargers", df["charger_count"] == 0), ("NO EV data", df["data_flag"] == "missing"),
                        ("SYNTHETIC EV counts", df["data_flag"] == "synthetic")]:
        names = df.loc[mask, "district"].tolist()
        print(f"Districts with {label}: {len(names)}" + (f" -> {names}" if names else ""))
    if RESOLUTION.exists():
        res = pd.read_csv(RESOLUTION)
        bad = res[res["district_key"].isna()]["name"].tolist()
        fuzzy = res[res["method"].isin(["fuzzy", "geocode"])]
        print(f"VAHAN names NOT placed on the map: {bad or 'none'}")
        print(f"VAHAN names matched by fuzzy/geocode (check these by eye): {len(fuzzy)}")
        if len(fuzzy):
            print(fuzzy.to_string(index=False))


if __name__ == "__main__":
    main()
