"""
STEP 3 - EV counts from a VAHAN export.
Input: data/raw/vahan_tn_ev_by_district.csv  (file name set below)
  * It may have a 'district' column (district level) OR an 'rto' column (RTO level, as VAHAN scrapers produce).
  * Names are matched to the district polygons automatically (see resolve_districts.py). No spelling table.
  * RTO rows that belong to the same district are added together.
Districts with no EV count are left EMPTY ("no EV data"). Nothing is invented unless you switch on
ALLOW_SYNTHETIC in config.py, and then every invented value is flagged "synthetic".
"""
import numpy as np
import pandas as pd

import config
from resolve_districts import resolve_names
from utils import PROCESSED, RAW, ensure_dirs

VAHAN_FILE = RAW / "vahan_tn_ev_by_district.csv"
TEMPLATE_FILE = RAW / "vahan_tn_ev_by_district_TEMPLATE.csv"
RESOLUTION_LOG = PROCESSED / "vahan_name_resolution.csv"
TYPE_COLUMNS = ["two_wheeler", "three_wheeler", "four_wheeler", "bus"]


def write_template():
    if TEMPLATE_FILE.exists():
        return
    pd.DataFrame([{"district": "EXAMPLE", "ev_total": 1000, "two_wheeler": 700, "three_wheeler": 100,
                   "four_wheeler": 190, "bus": 10, "population": 1000000}]).to_csv(TEMPLATE_FILE, index=False)
    print(f"  template written -> {TEMPLATE_FILE.name}. Use a 'district' OR an 'rto' column.")


def _numbers(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def read_vahan_file():
    """Return (table, name_column). Empty table if the file does not exist."""
    if not VAHAN_FILE.exists():
        return pd.DataFrame(columns=["district", "ev_total"]), "district"
    df = pd.read_csv(VAHAN_FILE)
    df.columns = [c.strip().lower() for c in df.columns]
    name_col = "district" if "district" in df.columns else "rto" if "rto" in df.columns else None
    if name_col is None:
        raise ValueError(f"{VAHAN_FILE.name} needs a 'district' or an 'rto' column. Found: {list(df.columns)}")
    df = df[~df[name_col].astype(str).str.upper().str.contains("EXAMPLE")].copy()
    for col in ["ev_total", "population"] + TYPE_COLUMNS:
        if col in df.columns:
            df[col] = _numbers(df[col])
    present = [c for c in TYPE_COLUMNS if c in df.columns]
    if present:
        if "ev_total" not in df.columns:
            df["ev_total"] = np.nan
        type_sum = df[present].sum(axis=1, min_count=1)
        fill = df["ev_total"].isna() & type_sum.notna()
        if fill.any():
            print(f"  ev_total was blank for {int(fill.sum())} row(s): using the sum of the vehicle-type columns.")
        df.loc[fill, "ev_total"] = type_sum[fill]
    if "ev_total" not in df.columns:
        raise ValueError(f"{VAHAN_FILE.name} needs an 'ev_total' column (or the vehicle-type columns).")
    return df, name_col


def load_vahan(boundaries, geocode_fn=None):
    """
    Return (table, resolution). The table has ONE row per boundary district:
    district_key, ev_total (empty if unknown), data_flag ('real' / 'synthetic' / 'missing'), and 'population' if given.
    """
    df, name_col = read_vahan_file()
    resolution = resolve_names(df[name_col].dropna().tolist(), boundaries,
                               kind="rto" if name_col == "rto" else "district", geocode_fn=geocode_fn)
    resolution.to_csv(RESOLUTION_LOG, index=False)
    mapping = dict(zip(resolution["name"], resolution["district_key"]))
    df["district_key"] = df[name_col].map(mapping)

    unresolved = sorted(resolution.loc[resolution["district_key"].isna(), "name"].astype(str))
    if unresolved:
        print(f"  [WARNING] these VAHAN names could not be placed on any district (their EVs are NOT counted): {unresolved}")

    used = df.dropna(subset=["district_key", "ev_total"])
    if len(used) and used.groupby("district_key").size().max() > 1:
        print("  note: several VAHAN rows belong to one district; their values were added together.")
    agg = {"ev_total": "sum"}
    if "population" in used.columns:
        agg["population"] = "max"
    real = used.groupby("district_key", as_index=False).agg(agg)
    real["data_flag"] = "real"

    keys = list(boundaries["district_key"])
    table = pd.DataFrame({"district_key": keys}).merge(real, on="district_key", how="left")
    table["data_flag"] = table["data_flag"].fillna("missing")
    missing = table["data_flag"] == "missing"

    if missing.any():
        names = boundaries.set_index("district_key").loc[table.loc[missing, "district_key"], "district"].tolist()
        if config.ALLOW_SYNTHETIC and len(real):
            rng = np.random.default_rng(config.SYNTHETIC_SEED)
            low, high = int(real["ev_total"].min()), int(real["ev_total"].max())
            table.loc[missing, "ev_total"] = rng.integers(low, high + 1, size=int(missing.sum()))
            table.loc[missing, "data_flag"] = "synthetic"
            print(f"  [WARNING] ALLOW_SYNTHETIC is on: {len(names)} district(s) got flagged synthetic values: {names}")
        else:
            print(f"  [WARNING] {len(names)} district(s) have NO EV data and are left empty: {names}")
    return table, resolution


def main():
    ensure_dirs()
    write_template()
    state = "found" if VAHAN_FILE.exists() else "NOT found (all districts will show 'no EV data')"
    print(f"[3/5] VAHAN: {VAHAN_FILE.name} {state}.")


if __name__ == "__main__":
    main()
