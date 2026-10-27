"""Download documented population counts, or use a compatible manual CSV."""
import numpy as np
import pandas as pd
import config
from utils import RAW, PROCESSED, cached_json, norm_key, ensure_dirs


def download_population(force=False):
    """The free API exposes the cited Parquet dataset as paginated JSON."""
    import hashlib
    identity = (config.POPULATION_URL, config.POPULATION_DATASET, config.POPULATION_API_CONFIG, config.POPULATION_API_SPLIT)
    fingerprint = hashlib.sha256(str(identity).encode()).hexdigest()
    rows, offset = [], 0
    while True:
        params = {"dataset": config.POPULATION_DATASET, "config": config.POPULATION_API_CONFIG,
                  "split": config.POPULATION_API_SPLIT, "offset": offset, "length": config.POPULATION_PAGE_SIZE}
        snapshot = cached_json(RAW / f"population_{config.POPULATION_YEAR}_{fingerprint}_{offset}.json", "GET",
                               config.POPULATION_URL, params=params, force=force)
        if "rows" not in snapshot or "num_rows_total" not in snapshot or snapshot.get("partial"):
            raise ValueError("Population API did not return a complete page.")
        page = [record["row"] for record in snapshot["rows"]]
        rows.extend(page)
        offset += len(page)
        if offset >= snapshot["num_rows_total"]:
            break
        if not page:
            raise ValueError("Population download ended before all rows were fetched.")
    return pd.DataFrame(rows)


def match_population(table, boundaries):
    """Population totals require exact names; do not move historic totals by geocoding."""
    if not {"district", "population"}.issubset(table):
        raise ValueError("population.csv needs district,population headers.")
    table = table.copy()
    table["district_key"] = table.district.map(norm_key)
    table["population"] = pd.to_numeric(table.population, errors="coerce")
    if table.district_key.duplicated().any():
        raise ValueError("Population contains duplicate district keys; do not sum ambiguous census totals.")
    if ((table.population <= 0) | ~np.isfinite(table.population)).any():
        raise ValueError("Population must contain positive finite totals.")
    result = boundaries[["district", "district_key"]].merge(table[["district_key", "population"]], on="district_key", how="left")
    print("Population unmatched:", result.loc[result.population.isna(), "district"].tolist())
    return result


def main(boundaries):
    ensure_dirs()
    manual = RAW / config.POPULATION_MANUAL_FILE
    source = "missing"
    if manual.exists():
        values = pd.read_csv(manual)
        source = f"manual compatible population: {manual.name} (user must document source/year/licence)"
    else:
        print(f"Population candidate: {config.POPULATION_SOURCE_URL}; {config.POPULATION_LICENCE}")
        try:
            national = download_population(config.REFRESH_DOWNLOADS)
            state = national[national[config.POPULATION_STATE_COLUMN].map(norm_key) == norm_key(config.STATE_NAME)]
            values = state.rename(columns={config.POPULATION_DISTRICT_COLUMN: "district", config.POPULATION_COUNT_COLUMN: "population"})
            if not config.POPULATION_BOUNDARIES_VERIFIED:
                print("[WARNING] Census 2011 downloaded but NOT USED: verify boundary compatibility in config.py, or provide data/raw/population.csv.")
                values = pd.DataFrame(columns=["district", "population"])
            else:
                source = f"{config.POPULATION_CITATION}; year {config.POPULATION_YEAR}"
        except (RuntimeError, ValueError, KeyError) as err:
            print(f"[WARNING] Population unavailable: {err}. Provide data/raw/{config.POPULATION_MANUAL_FILE} (district,population). No values invented.")
            values = pd.DataFrame(columns=["district", "population"])
    result = match_population(values, boundaries)
    result["population_source"] = source
    result.to_csv(PROCESSED / "district_population.csv", index=False)
    return result
