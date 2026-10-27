"""Import collected official table extracts without guessing collapsed PDF cells.

The raw web extraction is cached as JSON so collection works despite a blocked
local downloader. This importer never types district values into logic. It
keeps every original cell and refuses totals when separators are ambiguous.
"""
import json
import re
from datetime import datetime, timezone
import pandas as pd
import config
from utils import RAW, PROCESSED, SAMPLES, OUTPUTS, ensure_dirs, save_json


def source_lines(extracts):
    """Combine overlapping retrieval chunks by their original PDF line number."""
    result = {}
    for extract in extracts:
        for content in extract.get("content", []):
            for line in content.get("text", "").splitlines():
                match = re.match(r"L(\d+)@P([^:]+): (.*)", line)
                if match:
                    number, page, text = match.groups()
                    number = int(number)
                    row = (page, text)
                    if number in result and result[number] != row:
                        raise ValueError(f"Conflicting source extraction at line {number}.")
                    result[number] = row
    return result


def parse_count_cells(text, expected):
    """Accept separated integers, or exactly one digit per required cell only.

    '1 2 34' has three explicit cells. '001' has exactly three single-digit
    cells. '1 234' has several possible splits and is deliberately unresolved.
    """
    tokens = text.split()
    if len(tokens) == expected and all(token.isdigit() for token in tokens):
        return list(map(int, tokens))
    joined = "".join(tokens)
    if joined.isdigit() and len(joined) == expected:
        return list(map(int, joined))
    return None


def parse_ev_table(lines):
    first, last = config.PUBLIC_EV_TABLE_FIRST_LINE, config.PUBLIC_EV_TABLE_LAST_LINE
    missing = sorted(set(range(first, last + 1)) - lines.keys())
    if missing:
        raise ValueError(f"Official EV extract is incomplete: missing source lines {missing}.")
    code_pattern = "|".join(map(re.escape, sorted(config.PUBLIC_EV_CATEGORY_CODES, key=len, reverse=True)))
    category = re.compile(rf"^({code_pattern})(.*)$")
    rows, district, pending = [], None, None
    for number in range(first, last + 1):
        page, original = lines[number]
        # Page extraction sometimes glues two rows or a district name to a row.
        pieces = re.sub(rf"(?<!^)(?=({code_pattern}))", "\n", original).splitlines()
        for text in pieces:
            text = text.strip()
            if not text:
                continue
            match = category.match(text)
            if match:
                if pending is not None:
                    raise ValueError("A PDF category has no count cells before the next category.")
                code, cells = match.groups()
                record = {"district": district, "category": code, "source_page": page,
                          "source_line": number, "raw_cells": cells.strip()}
                if not cells.strip():
                    pending = record
                    continue
            elif text.replace(" ", "").isdigit() and pending is not None:
                record = pending
                record["raw_cells"] = text
                pending = None
            elif re.fullmatch(r"[A-Za-z][A-Za-z ]*", text):
                district = text
                continue
            else:
                raise ValueError(f"Unrecognised official table text at source line {number}: {text}")
            if record["district"] is None:
                raise ValueError("Category appeared before a district heading.")
            values = parse_count_cells(record["raw_cells"], len(config.PUBLIC_EV_YEARS))
            record["extraction_status"] = "verified separators" if values is not None else "ambiguous PDF cells"
            for position, year in enumerate(config.PUBLIC_EV_YEARS):
                record[str(year)] = values[position] if values is not None else None
            rows.append(record)
    if pending is not None:
        raise ValueError("The final table row is incomplete.")
    audit = pd.DataFrame(rows)
    duplicates = audit.duplicated(["district", "category"], keep=False)
    for _, group in audit[duplicates].groupby(["district", "category"]):
        if len(group[[str(y) for y in config.PUBLIC_EV_YEARS]].drop_duplicates()) != 1:
            raise ValueError("Conflicting duplicate district/category cells; review the PDF.")
    unique = audit.drop_duplicates(["district", "category"])
    totals = []
    for district, group in unique.groupby("district", sort=False):
        complete = group.extraction_status.eq("verified separators").all()
        totals.append({"district": district,
                       "ev_total": int(group[str(config.PUBLIC_EV_SELECTED_YEAR)].sum()) if complete else None,
                       "data_flag": "real" if complete else "missing",
                       "extraction_status": "complete" if complete else "ambiguous PDF cells - not ranked",
                       "ev_year": config.PUBLIC_EV_SELECTED_YEAR,
                       "ev_measure": config.PUBLIC_EV_MEASURE_LABEL,
                       "source_url": config.PUBLIC_EV_SOURCE_URL,
                       "source_date": config.PUBLIC_EV_SOURCE_DATE})
    return pd.DataFrame(totals), audit


def parse_population_table(lines):
    rows = []
    for number in range(config.PUBLIC_POPULATION_FIRST_LINE, config.PUBLIC_POPULATION_LAST_LINE + 1):
        if number not in lines:
            raise ValueError(f"Population extraction missing source line {number}.")
        page, text = lines[number]
        match = re.fullmatch(r"\s*\d+\.\s+(.+?)\s+(\d+)\s+\d+\s+\d+\s+[\d.]+\s+[\d.]+", text)
        if not match:
            raise ValueError(f"Population row is ambiguous at line {number}: {text}")
        district, population = match.groups()
        rows.append({"district": district, "population": int(population),
                     "population_year": config.PUBLIC_POPULATION_YEAR,
                     "population_flag": "official estimate, not census enumeration",
                     "source_url": config.PUBLIC_POPULATION_SOURCE_URL, "source_page": page,
                     "boundary_compatibility": "not verified - candidate only"})
    return pd.DataFrame(rows)


def main():
    ensure_dirs()
    def read_extract(name):
        path = RAW / name
        if not path.exists():
            path = SAMPLES / config.PUBLIC_SOURCE_SNAPSHOT_DIR / name
        return json.loads(path.read_text(encoding="utf-8-sig"))
    extracts = [read_extract(name) for name in config.PUBLIC_EV_EXTRACT_FILES]
    totals, audit = parse_ev_table(source_lines(extracts))
    audit.to_csv(PROCESSED / "public_ev_category_extraction_audit.csv", index=False)
    totals.to_csv(SAMPLES / config.VAHAN_SAMPLE_FILE, index=False)
    totals.to_csv(RAW / "official_ev_2025_collected.csv", index=False)
    population_extract = read_extract("population_government_web_extract.json")
    population = parse_population_table(source_lines([population_extract]))
    population.to_csv(RAW / "population_official_estimates_candidate.csv", index=False)
    # Candidate populations must not be silently promoted to compatible inputs.
    population.to_csv(SAMPLES / "population_official_estimates_candidate.csv", index=False)
    summary = {"collected_utc": datetime.now(timezone.utc).isoformat(),
               "ev_source": config.PUBLIC_EV_SOURCE_URL, "ev_year": config.PUBLIC_EV_SELECTED_YEAR,
               "ev_measure": "annual registrations; not active or cumulative fleet",
               "ev_district_rows": len(totals), "ev_complete_districts": int(totals.ev_total.notna().sum()),
               "ev_unresolved_districts": totals.loc[totals.ev_total.isna(), "district"].tolist(),
               "population_source": config.PUBLIC_POPULATION_SOURCE_URL,
               "population_candidate_rows": len(population), "population_year": config.PUBLIC_POPULATION_YEAR,
               "population_used": False, "reason": "Boundary compatibility has not been verified.",
               "collection_method": "official PDF text retrieved through web tool, cached locally; not a live API"}
    save_json(OUTPUTS / "data_collection_manifest.json", summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
