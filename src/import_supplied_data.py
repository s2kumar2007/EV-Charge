"""Audit supplied source files and prepare unverified national population candidates."""
import csv
import hashlib
import io
from pathlib import Path
import geopandas as gpd
import pandas as pd
import config
from utils import RAW, PROCESSED, OUTPUTS, norm_key, save_json


def census_candidates(frame):
    columns = config.SUPPLIED_CENSUS_COLUMNS
    if not set(columns.values()).issubset(frame):
        raise ValueError("Census workbook is missing configured source columns.")
    rows = frame.loc[frame[columns["level"]].eq(config.SUPPLIED_CENSUS_DISTRICT_LEVEL) &
                     frame[columns["area_type"]].eq(config.SUPPLIED_CENSUS_TOTAL_LABEL), list(columns.values())].copy()
    rows = rows.rename(columns={source: target for target, source in columns.items()})
    if rows.empty or rows.duplicated(["state_code", "district_code"]).any():
        raise ValueError("Census district totals are empty or duplicated; rural/urban rows are never added twice.")
    rows["population"] = pd.to_numeric(rows.population, errors="raise")
    if rows.population.isna().any() or not rows.population.gt(0).all() or not rows.population.mod(1).eq(0).all():
        raise ValueError("Census population values must be supplied positive integers.")
    country = frame.loc[frame[columns["level"]].eq(config.SUPPLIED_CENSUS_COUNTRY_LEVEL) &
                        frame[columns["area_type"]].eq(config.SUPPLIED_CENSUS_TOTAL_LABEL), columns["population"]]
    if len(country) > 1 or (len(country) == 1 and int(country.iloc[0]) != int(rows.population.sum())):
        raise ValueError("District population sum disagrees with the printed India total.")
    rows["population_year"] = config.SUPPLIED_CENSUS_YEAR
    rows["source_url"] = config.OFFICIAL_CENSUS_DISTRICT_URL
    rows["boundary_compatible"] = "no"
    return rows.drop(columns=["level", "area_type"]).reset_index(drop=True)


def propose_national_crosswalk(population, boundaries):
    lookup = {}
    for row in boundaries.itertuples():
        lookup.setdefault(norm_key(row.district), []).append(str(row.district_key))
    rows = []
    for row in population.itertuples():
        matches = lookup.get(norm_key(row.district), [])
        rows.append({"state_code": row.state_code, "district_code": row.district_code,
            "population_district": row.district, "polygon_ids_suggested": "|".join(matches),
            "relation": "needs_human_check", "verified": "no",
            "evidence": "Name suggestion only; Census year and polygon extent must be reviewed. " +
                        ("Multiple polygon names match." if len(matches)>1 else "No name match." if not matches else "One name match; geography not verified.")})
    return pd.DataFrame(rows)


def inspect_ev_export(text):
    # Some exports contain literal backslash-n separators in their title block.
    lines = text.replace("\\n", "\n").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("Fuel,")), None)
    if start is None:
        raise ValueError("No fuel table header in the supplied EV export.")
    records = list(csv.DictReader(io.StringIO("\n".join(lines[start:]))))
    if not records or "Total" not in records[0]:
        raise ValueError("No supplied EV totals found.")
    totals = {row["Fuel"]: int(row["Total"].replace(",", "")) for row in records}
    for row in records:
        if sum(int(value.replace(",", "")) for key,value in row.items() if key not in ("Fuel", "Total")) != totals[row["Fuel"]]:
            raise ValueError("Supplied EV category sum disagrees with its printed row total.")
    total_label = config.SUPPLIED_EV_TOTAL_LABEL
    if total_label in totals and sum(value for key,value in totals.items() if key != total_label) != totals[total_label]:
        raise ValueError("Supplied EV fuel rows disagree with the printed grand total.")
    return {"title": lines[0], "fuel_totals": totals, "district_rows": 0,
            "usable_for_district_ranking": False,
            "reason": "Combined national fuel totals have no district or RTO rows; registration period and geography cannot be assigned to districts."}


def main():
    folder = RAW / config.SUPPLIED_USER_FOLDER
    report = {"files": [], "manual_tasks": []}
    for filename in (config.SUPPLIED_CENSUS_FILE, config.SUPPLIED_STATE_FILE, config.SUPPLIED_EV_FILE):
        path = folder / filename
        if not path.is_file():
            report["manual_tasks"].append(f"Copy {filename} into {folder}.")
            continue
        record = {"file": filename, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if filename == config.SUPPLIED_CENSUS_FILE:
            frame = pd.read_excel(path, dtype=str)
            population = census_candidates(frame)
            population.to_csv(RAW / config.SUPPLIED_POPULATION_CANDIDATE, index=False)
            boundary_path = PROCESSED / config.INDIA_OUTPUT_FOLDER / config.GOOGLE_MAPS_BOUNDARY_INPUT
            if boundary_path.exists():
                crosswalk = propose_national_crosswalk(population, gpd.read_file(boundary_path))
                crosswalk.to_csv(RAW / config.SUPPLIED_POPULATION_CROSSWALK, index=False)
            record.update(district_totals=len(population), population_year=config.SUPPLIED_CENSUS_YEAR,
                          population_sum=int(population.population.sum()), accepted_polygons=0)
            report["manual_tasks"].append("Review Census 2011 district extents against the chosen polygon release before importing any population; do not split old district populations.")
        elif filename == config.SUPPLIED_EV_FILE:
            record.update(inspect_ev_export(path.read_text(encoding="utf-8-sig")))
            report["manual_tasks"].append("Export district-level EV rows for one explicit registration period and vehicle-category definition, with source metadata. The combined India total cannot be disaggregated.")
        else:
            frame = pd.read_excel(path, header=1, dtype=str)
            record.update(rows=len(frame), purpose="State code directory; contains no district EV or population counts.")
        report["files"].append(record)
    save_json(OUTPUTS / config.INDIA_OUTPUT_FOLDER / config.SUPPLIED_AUDIT_REPORT, report)
    for record in report["files"]:
        print(record)
    for task in report["manual_tasks"]:
        print("MANUAL: " + task)
    return report


if __name__ == "__main__":
    main()
