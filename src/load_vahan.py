"""
STEP 2 - EV counts from a VAHAN export.
Input: data/raw/vahan_tn_ev_by_district.csv (or data/samples/ fallback)
  * It may have a 'district' column (district level) OR an 'rto' column (RTO level, as VAHAN scrapers produce).
  * Names are matched to the district polygons automatically (see resolve_districts.py). No spelling table.
  * RTO rows that belong to the same district are added together.
Districts with no EV count are left EMPTY ("no EV data"). Nothing is invented unless you switch on
ALLOW_SYNTHETIC in config.py, and then every invented value is flagged "synthetic".
"""
from pathlib import Path

import numpy as np
import pandas as pd

import config
from resolve_districts import resolve_names
from utils import PROCESSED, RAW, ROOT, SAMPLES, ensure_dirs

RAW_VAHAN_FILE = RAW / config.VAHAN_FILE
TEMPLATE_FILE = RAW / config.VAHAN_TEMPLATE
SYNTHETIC_TEST_FILE = SAMPLES / config.SYNTHETIC_TEST_FILENAME
RESOLUTION_LOG = PROCESSED / "vahan_name_resolution.csv"
TYPE_COLUMNS = config.VEHICLE_COLUMNS


def get_vahan_source():
    """
    Find which VAHAN file to read:
    1. data/raw/vahan_tn_ev_by_district.csv (real file)
    2. data/samples/vahan_tn_ev_by_district.csv (committed real file)
    3. data/samples/vahan_tn_ev_by_district_SYNTHETIC_TEST.csv (ONLY if USE_SYNTHETIC_TEST_DATA is True)
    Returns (path_to_file or None, display_string or None, is_synthetic_test: bool).
    """
    if RAW_VAHAN_FILE.exists():
        return RAW_VAHAN_FILE, f"data/raw/{RAW_VAHAN_FILE.name}", False

    sample_setting = getattr(config, "VAHAN_SAMPLE_FILE", "vahan_tn_ev_by_district.csv")
    sample_candidate = Path(sample_setting)
    if sample_candidate.is_absolute():
        sample_path = sample_candidate
    elif (ROOT / sample_candidate).exists():
        sample_path = ROOT / sample_candidate
    else:
        sample_path = SAMPLES / sample_candidate.name

    if sample_path.name == config.SYNTHETIC_TEST_FILENAME:
        if not config.USE_SYNTHETIC_TEST_DATA:
            raise ValueError("Synthetic test file is blocked by USE_SYNTHETIC_TEST_DATA=False.")
        return sample_path, str(sample_path), True

    if sample_path.exists():
        return sample_path, f"data/samples/{sample_path.name}", False

    if getattr(config, "USE_SYNTHETIC_TEST_DATA", False) and SYNTHETIC_TEST_FILE.exists():
        return SYNTHETIC_TEST_FILE, f"data/samples/{SYNTHETIC_TEST_FILE.name}", True

    return None, None, False


def write_template():
    ensure_dirs()
    pd.DataFrame(columns=config.TEMPLATE_COLUMNS).to_csv(TEMPLATE_FILE, index=False)


def _numbers(series):
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")


def read_vahan_file():
    """Return (table, name_column). Empty table if the file does not exist."""
    source_path, display_name, is_synthetic_test = get_vahan_source()
    if source_path is None:
        return pd.DataFrame(columns=["district", "ev_total"]), "district"
    print(f"  using VAHAN file: {display_name}")
    if is_synthetic_test:
        print("  [WARNING] SYNTHETIC TEST DATA IN USE - do not use these results in the submission.")
    df = pd.read_csv(source_path)
    df.columns = [c.strip().lower() for c in df.columns]
    name_col = "district" if "district" in df.columns else "rto" if "rto" in df.columns else None
    if name_col is None:
        raise ValueError(f"{source_path.name} needs a 'district' or an 'rto' column. Found: {list(df.columns)}")
    df = df.dropna(subset=[name_col]).copy()
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
        raise ValueError(f"{source_path.name} needs an 'ev_total' column (or the vehicle-type columns).")
    if is_synthetic_test:
        df["data_flag"] = "synthetic"
    for column in ["ev_total", "population"]:
        if column in df:
            numbers = df[column].dropna()
            if (numbers < 0).any() or not np.isfinite(numbers).all():
                raise ValueError(f"Invalid or negative {column} in VAHAN input; fix the export.")
    return df, name_col


def load_vahan(boundaries, geocode_fn=None):
    """
    Return (table, resolution). The table has ONE row per boundary district:
    district_key, ev_total (empty if unknown), data_flag ('real' / 'synthetic' / 'missing'), and 'population' if given.
    """
    ensure_dirs()
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
    # Carry the observation year/meaning onto the map; registrations in one
    # year must never be presented as today's cumulative vehicle fleet.
    for column in ("ev_year", "ev_measure", "source_url", "source_date"):
        if column in used:
            agg[column] = lambda values: "|".join(sorted(set(values.dropna().astype(str))))
    if "population" in used.columns:
        agg["population"] = "max"
    if "data_flag" in used.columns:
        def combine_flags(series):
            flags = series.dropna().astype(str).str.strip()
            if flags.str.contains("synthetic", case=False).any():
                return "synthetic"
            return "|".join(sorted(set(flags[flags.ne("")]))) or "real"
        agg["data_flag"] = combine_flags
    real = used.groupby("district_key", as_index=False).agg(agg)
    if "data_flag" not in real.columns:
        real["data_flag"] = "real"

    keys = list(boundaries["district_key"])
    table = pd.DataFrame({"district_key": keys}).merge(real, on="district_key", how="left")
    table["data_flag"] = table["data_flag"].fillna("missing")
    missing = table["data_flag"] == "missing"

    if missing.any():
        names = boundaries.set_index("district_key").loc[table.loc[missing, "district_key"], "district"].tolist()
        observed = real[real["data_flag"] != "synthetic"]
        if config.ALLOW_SYNTHETIC and len(observed):
            rng = np.random.default_rng(config.SYNTHETIC_SEED)
            low, high = int(observed["ev_total"].min()), int(observed["ev_total"].max())
            table.loc[missing, "ev_total"] = rng.integers(low, high + 1, size=int(missing.sum()))
            table.loc[missing, "data_flag"] = "synthetic"
            print(f"  [WARNING] ALLOW_SYNTHETIC is on: {len(names)} district(s) got flagged synthetic values: {names}")
        else:
            print(f"  [WARNING] {len(names)} district(s) have NO EV data and are left empty: {names}")
    return table, resolution


def main():
    ensure_dirs()
    write_template()
    source_path, display_name, is_synthetic_test = get_vahan_source()
    if source_path is not None:
        print(f"VAHAN: found ({display_name}).")
        if is_synthetic_test:
            print("  [WARNING] SYNTHETIC TEST DATA IN USE - do not use these results in the submission.")
    else:
        print(f"VAHAN: {RAW_VAHAN_FILE.name} NOT found in data/raw/ or data/samples/ (all districts will show 'no EV data').")


if __name__ == "__main__":
    main()
