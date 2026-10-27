"""Download documented population counts, or use a compatible manual CSV."""
import numpy as np
import pandas as pd
import config
from utils import RAW, PROCESSED, SAMPLES, cached_json, norm_key, ensure_dirs
from resolve_districts import resolve_one, geocode


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



def propose_crosswalk(values, boundaries, geocode_fn=None):
    """A spelling or location suggestion never authorises moving population."""
    labels = dict(zip(boundaries.district_key, boundaries.district))
    rows = []
    for name in values.district:
        key, method = resolve_one(name, boundaries, geocode_fn=geocode_fn)
        exact = method == "exact"
        evidence = "Exact normalised name; geography changes still need review." if exact else "Name is not exact; suggestion, not verified."
        if not exact:
            # Fuzzy resolution stops early, so separately record any location evidence.
            try:
                geo_key, geo_method = resolve_one(name, boundaries, kind="rto", geocode_fn=geocode_fn)
                if geo_method == "geocode":
                    evidence += f" Geocode falls in {labels[geo_key]}: suggestion, not verified."
            except RuntimeError as err:
                evidence += f" Geocode unavailable: {err}"
        rows.append(dict(population_district=name, polygon_district=labels.get(key, ""),
                         relation="one_to_one" if exact else "needs_human_check",
                         method=method if method != "unresolved" else "geocode",
                         evidence=evidence if key else evidence + " No polygon resolved.",
                         verified="yes" if exact else "no"))
    return pd.DataFrame(rows)


def attach_crosswalk(values, boundaries, crosswalk):
    """Never split a source row or use a partial many-to-one aggregate."""
    required = {"population_district", "polygon_district", "relation", "method", "evidence", "verified"}
    if not required.issubset(crosswalk):
        raise ValueError("Population crosswalk is missing required columns.")
    if values.district.duplicated().any() or crosswalk.population_district.duplicated().any():
        raise ValueError("Population source/crosswalk has duplicate rows; splitting is forbidden.")
    if set(values.district) != set(crosswalk.population_district):
        raise ValueError("Crosswalk must contain every population source row exactly once.")
    if not crosswalk.relation.isin(["one_to_one", "many_to_one", "needs_human_check"]).all():
        raise ValueError("Unknown population relation.")
    table = values.merge(crosswalk, left_on="district", right_on="population_district", validate="one_to_one")
    table["population"] = pd.to_numeric(table.population, errors="coerce")
    if table.population.dropna().le(0).any() or not np.isfinite(table.population.dropna()).all():
        raise ValueError("Population must be positive and finite, or missing.")
    names = dict(zip(boundaries.district, boundaries.district_key))
    table["district_key"] = table.polygon_district.map(names)
    exact = table.relation.eq("one_to_one")
    valid_exact = table.apply(lambda r: norm_key(r.population_district) == norm_key(r.polygon_district), axis=1)
    if (exact & (~valid_exact | table.method.ne("exact"))).any():
        raise ValueError("one_to_one is allowed only for exact name matches.")
    approved = exact | (table.relation.eq("many_to_one") & table.verified.fillna("").str.lower().eq("yes"))
    accepted = []
    for key, group in table.dropna(subset=["district_key"]).groupby("district_key"):
        # Multiple sources require an explicitly reviewed aggregation for all contributors.
        okay = approved.loc[group.index].all() and group.population.notna().all()
        if len(group) > 1:
            okay = okay and group.relation.eq("many_to_one").all() and group.verified.str.lower().eq("yes").all()
        if okay:
            accepted.append({"district_key": key, "population": group.population.sum()})
    result = boundaries[["district", "district_key"]].merge(
        pd.DataFrame(accepted, columns=["district_key", "population"]), on="district_key", how="left", validate="one_to_one")
    result["population_source"] = f"{config.PUBLIC_POPULATION_SOURCE_URL}; {config.PUBLIC_POPULATION_YEAR} official estimate; crosswalk"
    result["population_year"] = config.PUBLIC_POPULATION_YEAR
    result["population_status"] = np.where(result.population.notna(), "crosswalk accepted", "unverified or missing population")
    print("Population rows with no resolved polygon:", table.loc[table.district_key.isna(), "population_district"].tolist())
    print("Population rows without exact polygon:", table.loc[~exact, "population_district"].tolist())
    print("Polygons without accepted population:", result.loc[result.population.isna(), "district"].tolist())
    print("Population rows to verify by hand:\n" + crosswalk.loc[~exact & ~approved, list(crosswalk.columns)].to_string(index=False))
    return result


def candidate_population(boundaries, values=None, crosswalk_path=None, geocode_fn=None):
    values = pd.read_csv(SAMPLES / config.POPULATION_CANDIDATE_FILE) if values is None else values
    path = SAMPLES / config.POPULATION_CROSSWALK_FILE if crosswalk_path is None else crosswalk_path
    if path.exists():
        crosswalk = pd.read_csv(path).fillna("")
    else:
        crosswalk = propose_crosswalk(values, boundaries, geocode_fn)
        crosswalk.to_csv(path, index=False)
    return attach_crosswalk(values, boundaries, crosswalk)

def main(boundaries):
    ensure_dirs()
    manual = RAW / config.POPULATION_MANUAL_FILE
    if not manual.exists() and config.POPULATION_USE_CANDIDATE_CROSSWALK and (SAMPLES / config.POPULATION_CANDIDATE_FILE).exists():
        result = candidate_population(boundaries)
        result.to_csv(PROCESSED / "district_population.csv", index=False)
        return result
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
