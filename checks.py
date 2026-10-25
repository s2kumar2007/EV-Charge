"""
Sanity checks. Run after run_all.py:  python checks.py
Prints a quick summary so you can spot problems before showing the map.
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SCORES = ROOT / "outputs" / "district_gap_scores.csv"
CHARGERS_RAW = ROOT / "data" / "processed" / "chargers_raw.csv"
UNASSIGNED = ROOT / "data" / "processed" / "chargers_unassigned.csv"
UNMATCHED = ROOT / "data" / "processed" / "vahan_unmatched.csv"


def main():
    if not SCORES.exists():
        print("outputs/district_gap_scores.csv not found - run  python run_all.py  first.")
        sys.exit(1)

    df = pd.read_csv(SCORES)
    print("=== ChargeGap Slice 0 sanity checks ===")
    print(f"Districts in results:       {len(df)}")
    print(f"Total EVs (sum of districts): {int(df['ev_total'].sum()):,}")
    print(f"Chargers counted in districts: {int(df['charger_count'].sum())}")
    if CHARGERS_RAW.exists():
        fetched = len(pd.read_csv(CHARGERS_RAW))
        outside = len(pd.read_csv(UNASSIGNED)) if UNASSIGNED.exists() else 0
        ok = "OK" if fetched == int(df["charger_count"].sum()) + outside else "MISMATCH!"
        print(f"Chargers fetched: {fetched} = in districts + {outside} outside  -> {ok}")

    cols = ["rank", "district", "ev_total", "charger_count", "gap_score", "data_flag"]
    print("\nTop 5 MOST underserved (rank 1 = worst):")
    print(df.sort_values("rank").head(5)[cols].to_string(index=False))
    print("\nBottom 5 (best served = lowest gap_score, among districts that have chargers):")
    served = df[df["charger_count"] > 0].sort_values("gap_score")
    print(served.head(5)[cols].to_string(index=False) if len(served) else "  (no district has any charger)")

    print("\n--- Missing / flagged data ---")
    n_none = int((df["charger_count"] == 0).sum())
    print(f"Districts with NO chargers: {n_none}" + (f" -> {df.loc[df.charger_count == 0, 'district'].tolist()}" if n_none else ""))
    synthetic = df.loc[df["data_flag"] == "synthetic", "district"].tolist()
    print(f"Districts using SYNTHETIC EV counts: {len(synthetic)}" + (f" -> {synthetic}" if synthetic else ""))
    print(f"Districts with missing ev_total: {int(df['ev_total'].isna().sum())}")
    if UNMATCHED.exists():
        unmatched = pd.read_csv(UNMATCHED).iloc[:, 0].dropna().tolist()
        print(f"VAHAN rows not on the map (no polygon): {unmatched or 'none'}")


if __name__ == "__main__":
    main()
