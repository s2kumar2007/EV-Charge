"""Print explicit count reconciliation, exclusions and method checks."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import pandas as pd
import config
from utils import OUTPUTS, PROCESSED


def main(include_slice1=True):
    df = pd.read_csv(OUTPUTS / "district_gap_scores.csv")
    df["rank"] = df["rank"].astype("Int64")
    raw = pd.read_csv(PROCESSED / "chargers_raw.csv")
    assigned = pd.read_csv(PROCESSED / "chargers_assigned.csv")
    inside = int(assigned.district.notna().sum())
    outside = int(assigned.district.isna().sum())
    if inside + outside != len(raw) or int(df.raw_charger_count.sum()) != inside:
        raise RuntimeError("Raw charger reconciliation failed: fetched != inside + outside.")
    print(f"District count: {len(df)}; total KNOWN EVs: {df.ev_total.sum(min_count=1)}")
    print(f"Chargers fetched {len(raw)} = {inside} inside + {outside} outside; OK")
    print(f"Known ports: {raw.ports_known.astype(str).str.lower().isin(['true', '1']).sum()}/{len(raw)} records")
    columns = ["district", "ev_total", "charger_count", "port_count", "gap_score", "rank", "data_flag"]
    print("Most underserved:")
    print(df[df['rank'].notna()].sort_values("rank")[columns].head(config.REPORT_TOP_N).to_string(index=False))
    print("Best served (must have EVs and chargers):")
    print(df[df.ev_total.notna() & df.charger_count.gt(0)].sort_values("gap_score")[columns].head(config.REPORT_TOP_N).to_string(index=False))
    for label, mask in [("no chargers", df.charger_count.eq(0)), ("no EV data", df.ev_total.isna()),
                        ("synthetic", df.data_flag.astype(str).str.contains("synthetic", case=False))]:
        print(f"{label}: {df.loc[mask, 'district'].tolist()}")
    resolution = pd.read_csv(PROCESSED / "vahan_name_resolution.csv")
    print("VAHAN fuzzy/geocode matches (review by hand):")
    print(resolution[resolution.method.isin(["fuzzy", "geocode"])].to_string(index=False))
    print("Unresolved VAHAN names:", resolution.loc[resolution.district_key.isna(), "name"].tolist())
    if not include_slice1:
        return
    path = PROCESSED / "chargers_deduplicated.csv"
    if path.exists() and config.DEDUP_ENABLED:
        merged = pd.read_csv(path)
        print(f"Duplicates removed: {len(raw) - len(merged)}")
        print("Confidence distribution:", merged.confidence.describe().to_dict())
        print(pd.read_csv(OUTPUTS / "dedup_radius_sensitivity.csv").to_string(index=False))
    index = pd.read_csv(OUTPUTS / "district_gap_index.csv")
    print("Top composite districts and rank range:")
    print(index[index['rank'].notna()].sort_values("rank")[["district", "rank", "min_rank", "max_rank", "top_k_share"]].head(config.REPORT_TOP_N).to_string(index=False))
    print("Excluded districts:")
    print(index[index['rank'].isna()][["district", "index_status", "missing_indicators"]].to_string(index=False))
    print("Weight comparison:", json.loads((OUTPUTS / "gap_index_methods.json").read_text()))
    print("Moran's I and p-value:", json.loads((OUTPUTS / "hotspot_statistics.json").read_text()))


if __name__ == "__main__":
    main()
