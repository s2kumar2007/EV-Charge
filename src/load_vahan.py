"""
STEP 3 - EV counts per district (from a VAHAN export you make by hand).

VAHAN has no clean API, so we read data/raw/vahan_tn_ev_by_district.csv.
If the file (or a district's value) is missing, we fill in a SYNTHETIC
placeholder and label it data_flag = "synthetic". We never invent numbers silently.
"""
import numpy as np
import pandas as pd

from utils import RAW, ensure_dirs, norm_key

VAHAN_FILE = RAW / "vahan_tn_ev_by_district.csv"
TEMPLATE_FILE = RAW / "vahan_tn_ev_by_district_TEMPLATE.csv"
TYPE_COLUMNS = ["two_wheeler", "three_wheeler", "four_wheeler", "bus"]


def write_template():
    """Write an empty example file showing the expected columns (never overwrites)."""
    if TEMPLATE_FILE.exists():
        return
    template = pd.DataFrame([{
        "district": "EXAMPLE", "ev_total": 1000,
        "two_wheeler": 700, "three_wheeler": 100, "four_wheeler": 190, "bus": 10,
        "population": 1000000,
    }])
    template.to_csv(TEMPLATE_FILE, index=False)
    print(f"  template written -> {TEMPLATE_FILE.name} (copy it to {VAHAN_FILE.name} and fill in real data)")


def _clean_numbers(series):
    """Turn '12,345' / blanks / text into numbers (bad values become empty)."""
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def read_vahan_file():
    """Read the manual VAHAN CSV. Returns an empty table if the file does not exist."""
    if not VAHAN_FILE.exists():
        return pd.DataFrame(columns=["district", "ev_total"])

    df = pd.read_csv(VAHAN_FILE)
    df.columns = [c.strip().lower() for c in df.columns]
    if "district" not in df.columns:
        raise ValueError(f"{VAHAN_FILE.name} must have a 'district' column. Found: {list(df.columns)}")

    # Drop the template's example row if someone copied the template as-is.
    df = df[~df["district"].astype(str).str.upper().str.contains("EXAMPLE")].copy()

    for col in ["ev_total", "population"] + TYPE_COLUMNS:
        if col in df.columns:
            df[col] = _clean_numbers(df[col])

    # If ev_total is blank but the vehicle-type columns are filled, add them up.
    present_types = [c for c in TYPE_COLUMNS if c in df.columns]
    if present_types:
        if "ev_total" not in df.columns:
            df["ev_total"] = np.nan
        type_sum = df[present_types].sum(axis=1, min_count=1)
        filled = df["ev_total"].isna() & type_sum.notna()
        if filled.any():
            print(f"  ev_total was blank for {int(filled.sum())} row(s): using the sum of the vehicle-type columns.")
        df.loc[filled, "ev_total"] = type_sum[filled]

    if "ev_total" not in df.columns:
        raise ValueError(f"{VAHAN_FILE.name} needs an 'ev_total' column (or the vehicle-type columns).")
    return df


def load_vahan(boundary_names):
    """
    boundary_names: dict {district_key: district_name} of the map polygons.
    Returns (table, vahan_names_without_polygon). The table has one row for EVERY
    polygon: district_key, ev_total, data_flag ('real'/'synthetic'), and 'population' if given.
    """
    df = read_vahan_file()
    df["district_key"] = df["district"].map(norm_key)
    df = df[df["district_key"] != ""]

    # If a district appears twice (e.g. two spellings), add the values together and warn.
    if df["district_key"].duplicated().any():
        print("  [warning] some districts appear more than once in the VAHAN file; values were added together.")
    agg = {"ev_total": "sum"}
    if "population" in df.columns:
        agg["population"] = "max"
    real = df.dropna(subset=["ev_total"]).groupby("district_key", as_index=False).agg(agg)
    real["data_flag"] = "real"

    unmatched = sorted({n for n, k in zip(df["district"], df["district_key"]) if k not in boundary_names})

    # Districts on the map with no real value -> clearly flagged synthetic placeholder.
    missing_keys = [k for k in boundary_names if k not in set(real["district_key"])]
    rng = np.random.default_rng(2026)  # fixed seed: same placeholder numbers every run
    synthetic = pd.DataFrame({
        "district_key": missing_keys,
        "ev_total": rng.integers(500, 20000, size=len(missing_keys)),
        "data_flag": "synthetic",
    })
    if missing_keys:
        print(f"  [WARNING] {len(missing_keys)} district(s) have no real EV count -> SYNTHETIC placeholders used "
              f"(flagged 'synthetic'): {[boundary_names[k] for k in missing_keys]}")

    out = pd.concat([real, synthetic], ignore_index=True)
    out = out[out["district_key"].isin(boundary_names)]
    out["ev_total"] = out["ev_total"].round().astype(int)
    return out, unmatched


def main():
    ensure_dirs()
    write_template()
    if VAHAN_FILE.exists():
        print(f"[3/5] VAHAN: found {VAHAN_FILE.name} (matching happens in the next step).")
    else:
        print(f"[3/5] VAHAN: {VAHAN_FILE.name} NOT found -> all EV numbers will be SYNTHETIC and flagged.")


if __name__ == "__main__":
    main()
