"""Recover the existing EV measure from original PDF cells without guessing."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import pandas as pd
import config
from import_public_tables import parse_ev_table, source_lines
from utils import RAW, SAMPLES, PROCESSED, OUTPUTS, norm_key, save_json


def integer_cell(words):
    """Accept one integer or explicit valid thousands groups inside one cell."""
    raw = " ".join(word["text"] for word in sorted(words, key=lambda w: (w["top"], w["x0"]))).strip()
    if re.fullmatch(r"[0-9]+", raw):
        return int(raw)
    compact = re.sub(r"\s*,\s*", ",", raw)
    # Commas are explicit separators; separate bare digits are not joined.
    if "," in compact and (re.fullmatch(r"[0-9]{1,3}(?:,[0-9]{3})+", compact) or
                           re.fullmatch(r"[0-9]{1,2}(?:,[0-9]{2})*,[0-9]{3}", compact)):
        return int(compact.replace(",", ""))
    return None


def cell_from_words(words, bbox, page, column, backend="pdfplumber"):
    """Every included word keeps its original PDF coordinates for review."""
    if bbox is None:
        selected = []
    else:
        x0, top, x1, bottom = bbox
        inset = config.PUBLIC_EV_PDF_CELL_INSET_PT
        selected = [w for w in words if x0-inset <= w["x0"] and w["x1"] <= x1+inset and top-inset <= w["top"] and w["bottom"] <= bottom+inset]
    return {"page": page, "column": column, "bbox": list(bbox) if bbox is not None else None,
            "coordinate_units": "PDF points", "backend": backend,
            "raw": " ".join(w["text"] for w in sorted(selected, key=lambda w: (w["top"], w["x0"]))),
            "words": [{k: w[k] for k in ("text", "x0", "x1", "top", "bottom")} for w in selected],
            "value": integer_cell(selected) if column in config.PUBLIC_EV_YEARS else None}


def pdfplumber_rows(path):
    reader = importlib.import_module("pdfplumber")
    rows, audit = [], []
    columns = ["district", "category", *config.PUBLIC_EV_YEARS]
    with reader.open(path) as document:
        for page_number, page in enumerate(document.pages, start=1):
            if page_number < config.PUBLIC_EV_PDF_FIRST_TABLE_PAGE:
                continue
            words = page.extract_words(**config.PUBLIC_EV_PDF_WORD_SETTINGS)
            for table in page.find_tables(table_settings=config.PUBLIC_EV_PDF_TABLE_SETTINGS):
                for row in table.rows:
                    if len(row.cells) != len(columns):
                        raise ValueError(f"Page {page_number}: expected five table columns; review PDF geometry.")
                    cells = [cell_from_words(words, bbox, page_number, column) for column, bbox in zip(columns, row.cells)]
                    audit.extend(cells)
                    rows.append({"district": cells[0]["raw"], "category": cells[1]["raw"],
                                 "values": {str(year): cells[i+2]["value"] for i, year in enumerate(config.PUBLIC_EV_YEARS)},
                                 "page": page_number, "raw_cells": cells})
    if not rows:
        raise ValueError("pdfplumber found no annexure table cells.")
    return rows, audit, "pdfplumber word coordinates"


def parse_layout(text, expected_names):
    """Fallback accepts only three visibly separated numeric year columns."""
    codes = "|".join(re.escape(c) for c in sorted(config.PUBLIC_EV_CATEGORY_CODES, key=len, reverse=True))
    totals = "|".join(re.escape(t) for t in config.PUBLIC_EV_PDF_TOTAL_TEXT)
    category_pattern = re.compile(rf"(?<![A-Za-z0-9])({codes}|{totals})(?![A-Za-z0-9])", re.I)
    lookup = {norm_key(name): name for name in expected_names}
    rows, audit, current, pending = [], [], "", []
    for page, page_text in enumerate(text.split("\f"), start=1):
        if page < config.PUBLIC_EV_PDF_FIRST_TABLE_PAGE:
            continue
        for line_number, line in enumerate(page_text.splitlines(), start=1):
            match = category_pattern.search(line)
            if not match:
                # Only exact source district labels are used; narrative/header text is ignored.
                stripped = line.strip()
                if norm_key(stripped) in lookup:
                    current = lookup[norm_key(stripped)]
                continue
            prefix = line[:match.start()].strip()
            if prefix:
                pending.append(prefix)
                candidate = " ".join(pending)
                if norm_key(candidate) in lookup:
                    current, pending = lookup[norm_key(candidate)], []
                elif norm_key(prefix) in lookup:
                    current, pending = lookup[norm_key(prefix)], []
                else:
                    raise ValueError(f"Unrecognised district label in layout page {page}, line {line_number}: {candidate}")
            raw = line[match.end():]
            numeric = list(re.finditer(r"[0-9][0-9,]*", raw))
            valid = len(numeric) == len(config.PUBLIC_EV_YEARS)
            if valid:
                gaps = [raw[numeric[i].end():numeric[i+1].start()] for i in range(len(numeric)-1)]
                valid = all(len(gap) >= 2 and gap.isspace() for gap in gaps)
                valid = valid and not raw[:numeric[0].start()].strip() and not raw[numeric[-1].end():].strip()
            values = {}
            cells = [
                {"page": page, "line": line_number, "column": "district", "raw": prefix,
                 "bbox": [0, line_number, match.start(), line_number+1],
                 "coordinate_units": "pdftotext layout character columns/lines, not PDF points", "backend": "pdftotext -layout", "value": None},
                {"page": page, "line": line_number, "column": "category", "raw": match.group(1),
                 "bbox": [match.start(), line_number, match.end(), line_number+1],
                 "coordinate_units": "pdftotext layout character columns/lines, not PDF points", "backend": "pdftotext -layout", "value": None},
            ]
            audit.extend(cells)
            for i, year in enumerate(config.PUBLIC_EV_YEARS):
                token = numeric[i] if valid else None
                value = integer_cell([{"text": token.group(), "top": 0, "x0": 0}]) if token else None
                values[str(year)] = value
                cell = {"page": page, "line": line_number, "column": year,
                        "raw": token.group() if token else raw.strip(),
                        "bbox": [match.end()+token.start(), line_number, match.end()+token.end(), line_number+1] if token else None,
                        "coordinate_units": "pdftotext layout character columns/lines, not PDF points",
                        "backend": "pdftotext -layout", "value": value}
                cells.append(cell)
                audit.append(cell)
            category = match.group(1)
            district = current
            if norm_key(category) in config.PUBLIC_EV_STATE_TOTAL_LABELS:
                district, category = category, ""
            rows.append({"district": district, "category": category, "values": values, "page": page, "raw_cells": cells})
    if not rows:
        raise ValueError("pdftotext layout contains no recognised annexure category rows.")
    return rows, audit, "pdftotext -layout character coordinates"


def extract_rows(path, expected_names):
    errors = []
    try:
        return pdfplumber_rows(path)
    except (ImportError, OSError, ValueError, RuntimeError) as err:
        errors.append(f"pdfplumber: {type(err).__name__}: {err}")
        print("PDF primary reader failed: " + errors[-1])
    for candidate in config.PUBLIC_EV_PDF_READER_CANDIDATES:
        executable = shutil.which(candidate) or (candidate if Path(candidate).is_file() else None)
        if not executable:
            continue
        try:
            result = subprocess.run([executable, "-layout", "-enc", "UTF-8", str(path), "-"], capture_output=True, check=True)
            text = result.stdout.decode("utf-8")
            (RAW / config.PUBLIC_EV_PDF_LAYOUT_FILE).write_text(text, encoding="utf-8")
            return parse_layout(text, expected_names)
        except (OSError, subprocess.SubprocessError, UnicodeError, ValueError) as err:
            errors.append(f"pdftotext -layout: {type(err).__name__}: {err}")
    raise RuntimeError("Original-PDF extraction blocked. " + " | ".join(errors) +
                       " MANUAL: install pdfplumber with python -m pip install pdfplumber, or repair/install a working pdftotext, then run python src/complete_ev_counts.py.")


def reconcile(rows, baseline, expected_categories):
    """The existing measure and source categories define completeness, never guesses."""
    original_names = dict(zip(baseline.district.map(norm_key), baseline.district))
    current = None
    records, totals = [], []
    for row in rows:
        label, category = row["district"].strip(), row["category"].strip()
        label_key, category_key = norm_key(label), norm_key(category)
        state_total = label_key == norm_key(config.STATE_NAME) and category_key in config.PUBLIC_EV_DISTRICT_TOTAL_LABELS
        if state_total and label_key in original_names:
            raise ValueError("A total row could refer to the state or a same-named district; review it manually.")
        if label_key in config.PUBLIC_EV_STATE_TOTAL_LABELS or state_total:
            totals.append({**row, "kind": "state", "district": None})
            continue
        if label_key in original_names:
            current = original_names[label_key]
        if label and label_key not in original_names and label_key not in config.PUBLIC_EV_DISTRICT_TOTAL_LABELS and (category in config.PUBLIC_EV_CATEGORY_CODES or category_key in config.PUBLIC_EV_DISTRICT_TOTAL_LABELS):
            raise ValueError(f"Unrecognised PDF district label: {label}; no row assigned to the previous district.")
        if category_key in config.PUBLIC_EV_DISTRICT_TOTAL_LABELS or label_key in config.PUBLIC_EV_DISTRICT_TOTAL_LABELS:
            totals.append({**row, "kind": "district", "district": current})
            continue
        if category not in config.PUBLIC_EV_CATEGORY_CODES:
            continue  # Header cells remain in the audit, not in the category sum.
        if current is None:
            raise ValueError("A category appeared before a recognised district cell; no totals replaced.")
        records.append({"district": current, "category": category, **row["values"]})
    parsed = pd.DataFrame(records)
    if parsed.empty:
        raise ValueError("No category values extracted; no totals replaced.")
    if parsed.duplicated(["district", "category"]).any():
        raise ValueError("Duplicate district/category cells; review the PDF before replacing totals.")
    candidate = baseline.copy()
    candidate["extraction_status"] = "ambiguous PDF cells - not ranked"
    candidate["ev_total"] = pd.Series(float("nan"), index=candidate.index)
    checks = {"baseline_check": [], "printed_district_totals": [], "printed_state_totals": []}
    year_totals = {}
    for i, original in baseline.iterrows():
        group = parsed[parsed.district.eq(original.district)]
        expected = set(expected_categories.loc[expected_categories.district.eq(original.district), "category"])
        actual = set(group.category)
        if actual - expected:
            raise ValueError(f"Unexpected categories for {original.district}: {sorted(actual-expected)}; measure cannot change.")
        year_totals[original.district] = {}
        for year in config.PUBLIC_EV_YEARS:
            column = str(year)
            complete = actual == expected and bool(expected) and group[column].notna().all()
            year_totals[original.district][column] = int(group[column].sum()) if complete else None
        value = year_totals[original.district][str(config.PUBLIC_EV_SELECTED_YEAR)]
        if pd.notna(original.ev_total):
            check = {"district": original.district, "existing": int(original.ev_total), "extracted": value,
                     "status": "PASS" if value == int(original.ev_total) else "STOP"}
            checks["baseline_check"].append(check)
            print("Baseline EV check: " + json.dumps(check))
        if value is not None:
            candidate.loc[i, "ev_total"] = value
            candidate.loc[i, "extraction_status"] = "complete"
    candidate["data_flag"] = candidate.ev_total.notna().map({True: "real", False: "missing"})
    if any(check["status"] != "PASS" for check in checks["baseline_check"]):
        raise ValueError("STOP: extracted PDF values disagree with, or cannot verify, existing complete district totals. Existing CSV preserved.")
    for total in totals:
        for year in config.PUBLIC_EV_YEARS:
            year = str(year)
            printed = total["values"].get(year)
            if total["kind"] == "district":
                computed = year_totals.get(total["district"], {}).get(year)
                key = "printed_district_totals"
            else:
                values = [value[year] for value in year_totals.values()]
                computed = sum(values) if all(v is not None for v in values) else None
                key = "printed_state_totals"
            check = {"district": total.get("district"), "year": year, "printed": printed, "computed": computed,
                     "status": "PASS" if printed is not None and computed == printed else "PARTIAL" if computed is None or printed is None else "STOP"}
            checks[key].append(check)
            print("Printed-total check: " + json.dumps(check))
            if check["status"] == "STOP":
                raise ValueError("STOP: printed totals disagree with extracted category sums. Existing CSV preserved.")
    for key in ("printed_district_totals", "printed_state_totals"):
        if not checks[key]:
            print(f"{key}: not present in extracted table; no printed total invented.")
    print(f"EV complete: {candidate.ev_total.notna().sum()}/{len(candidate)}; measure={config.PUBLIC_EV_MEASURE_LABEL}; year={config.PUBLIC_EV_SELECTED_YEAR}")
    return candidate, checks


def baseline_categories():
    extracts = []
    for name in config.PUBLIC_EV_EXTRACT_FILES:
        path = SAMPLES / config.PUBLIC_SOURCE_SNAPSHOT_DIR / name
        extracts.append(json.loads(path.read_text(encoding="utf-8-sig")))
    return parse_ev_table(source_lines(extracts))[1]


def main():
    path = RAW / config.PUBLIC_EV_PDF_FILE
    if not path.exists():
        print(f"PARTIAL: missing {path}. Download the original official PDF to this exact path; no EV values changed.")
        return False
    baseline_path = SAMPLES / config.VAHAN_SAMPLE_FILE
    baseline = pd.read_csv(baseline_path)
    if "ev_year" in baseline and not pd.to_numeric(baseline.ev_year, errors="coerce").dropna().eq(config.PUBLIC_EV_SELECTED_YEAR).all():
        raise ValueError("Existing EV year differs from the configured extraction year; the measure cannot change silently.")
    if "ev_measure" in baseline and not baseline.ev_measure.dropna().eq(config.PUBLIC_EV_MEASURE_LABEL).all():
        raise ValueError("Existing EV measure differs from the configured definition; no CSV values replaced.")
    rows, audit, backend = extract_rows(path, baseline.district.tolist())
    folder = SAMPLES / config.PUBLIC_SOURCE_SNAPSHOT_DIR
    # The audit is saved even when reconciliation later stops on a mismatch.
    save_json(folder / config.PUBLIC_EV_PDF_AUDIT_FILE, {"backend": backend, "source_url": config.PUBLIC_EV_SOURCE_URL,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "selected_year": config.PUBLIC_EV_SELECTED_YEAR, "measure": config.PUBLIC_EV_MEASURE_LABEL, "cells": audit})
    candidate, checks = reconcile(rows, baseline, baseline_categories())
    save_json(folder / config.PUBLIC_EV_PDF_CHECKS_FILE, checks)
    pending = baseline_path.with_suffix(".csv.tmp")
    candidate.to_csv(pending, index=False)
    pending.replace(baseline_path)
    print("EV CSV regenerated after baseline and available printed-total checks. Next run python run_all.py --offline and python run_acceptance.py.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        main()
    except (RuntimeError, ValueError, OSError) as err:
        print(str(err))
        raise SystemExit(1)
