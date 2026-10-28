"""Print evidence-backed acceptance status; unavailable evidence stays PARTIAL."""
import argparse
import json
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
import config
from cache_map_assets import inspect_assets
from utils import ROOT, save_json


def evaluate(frames, boundary, hotspot, map_report, comparison=None, scope="state"):
    """Pure evaluation makes failures testable with fake in-memory evidence."""
    checks, tasks = [], []
    pipeline_command = "python run_india.py --offline" if scope == "india" else "python run_all.py --offline"
    def add(name, status, **numbers):
        checks.append(dict(check=name, status=status, **numbers))
    def frame(name):
        return frames.get(name, pd.DataFrame())
    def known(table, column):
        return int(table[column].notna().sum()) if column in table else 0
    scores = frame("scores")
    n = boundary.get("district_count", 0)
    provider = boundary.get("provider", "unknown")
    add("boundaries", "PASS" if n and provider == config.BOUNDARY_PROVIDER and len(scores) == n else "PARTIAL", loaded=n, provider=provider, score_rows=len(scores))
    if n and provider != config.BOUNDARY_PROVIDER:
        tasks.append("Review the boundary provider of these saved outputs; it differs from, or is unverified against, the current BOUNDARY_PROVIDER setting. Regenerate with the selected provider after caching its inputs.")
    if provider == "pinned_repo":
        tasks.append("Review boundary redistribution permission: pinned README says personal usage and names no data licence.")
    raw, dedup = frame("raw"), frame("deduplicated")
    def ports(table):
        return int(table.ports_known.astype(str).str.lower().isin(["true", "1"]).sum()) if "ports_known" in table else None
    add("chargers", "PASS" if "ports_known" in raw and "ports_known" in dedup and len(dedup) <= len(raw) else "PARTIAL",
        raw=len(raw) if "ports_known" in raw else None, deduplicated=len(dedup) if "ports_known" in dedup else None,
        raw_ports_known=ports(raw), deduplicated_ports_known=ports(dedup))
    if len(dedup) > len(raw):
        checks[-1]["status"] = "FAIL"
    complete = known(scores, "ev_total")
    measures = scores.ev_measure.dropna().unique().tolist() if "ev_measure" in scores else []
    add("EV counts", "PASS" if n and complete == n and measures else "PARTIAL", complete=complete, missing=n-complete if n else None, measure=measures,
        basic_ranked=known(scores, "rank"), observation_years=scores.ev_year.dropna().astype(str).unique().tolist() if "ev_year" in scores else [])
    if not n or complete < n:
        if scope == "india":
            tasks.append(f"Supply data/raw/{config.INDIA_EV_FILE} using its template and dataset IDs, uniform registration period/categories, source_url, observation_date and boundary_compatible=true only after reviewing district geography. Do not turn RTO office locations into district catchment counts.")
        else:
            tasks.append("Review the PDF word-coordinate audit and public_ev_pdf_checks.json, then run python src/complete_ev_counts.py followed by python run_all.py --offline. Any STOP must be resolved against the original PDF; preserve the CSV until every existing complete value verifies.")
    population, crosswalk = frame("population"), frame("crosswalk")
    needs = []
    if "relation" in crosswalk:
        accepted = crosswalk.relation.eq("one_to_one") | (crosswalk.relation.eq("many_to_one") & crosswalk.verified.astype(str).str.lower().eq("yes"))
        needs = crosswalk.loc[~accepted, "population_district"].tolist()
    covered = known(population, "population")
    add("population compatibility", "PASS" if n and covered == n and not needs else "PARTIAL", accepted_polygons=covered, missing=n-covered if n else None, rows_to_verify=needs,
        indicator_label=config.POPULATION_INDICATOR_LABEL if scope == "state" else config.POPULATION_GENERIC_INDICATOR_LABEL)
    if needs:
        tasks.append(f"Review data/samples/{config.POPULATION_CROSSWALK_FILE}: " + ", ".join(needs) + ". Non-exact rows require relation=many_to_one, verified=yes and documentary evidence; never split totals.")
    if n and covered < n and not needs:
        tasks.append(f"Supply compatible population with source/year and verified district geography. National inputs use data/raw/{config.INDIA_POPULATION_FILE}; never split older census totals across newer polygons.")
    osm = frame("osm")
    for label, column, prefix in (("roads", "road_km_per_km2", "road"), ("commercial places", "commercial_per_km2", "commercial")):
        count = known(osm, column)
        sources = osm[f"{prefix}_source"].dropna().unique().tolist() if f"{prefix}_source" in osm else []
        dates = osm[f"{prefix}_snapshot_date"].dropna().unique().tolist() if f"{prefix}_snapshot_date" in osm else []
        good_date = dates and config.INDICATOR_UNKNOWN_DATE not in dates
        add(label, "PASS" if n and count == n and sources and good_date else "PARTIAL", districts=count, missing=n-count if n else None, sources=sources, snapshot_dates=dates)
        if not n or count < n:
            tasks.append(f"Cache a complete {label} Overpass answer or run the national PBF extraction, then rerun {pipeline_command}.")
    ranked = known(frame("index"), "rank")
    add("composite index", "PASS" if n and ranked == n else "PARTIAL", ranked=ranked, missing=n-ranked if n else None)
    moran_n = hotspot.get("n", 0)
    gi_n = hotspot.get("gistar_n", 0)
    add("Moran I and Gi*", "PASS" if hotspot.get("I") is not None and gi_n > 0 else "PARTIAL", moran_I=hotspot.get("I"), moran_n=moran_n,
        gistar_n=gi_n, eligible=hotspot.get("n_eligible"), warning="Few districts: indicative, not conclusive" if moran_n < config.HOTSPOT_SMALL_N else hotspot.get("warning"), reason=hotspot.get("reason"))
    if hotspot.get("I") is None:
        if ranked < config.HOTSPOT_MIN_OBSERVATIONS:
            tasks.append(f"Complete verified indicator inputs before rerunning {pipeline_command}; too few ranked districts are available for spatial statistics.")
        else:
            tasks.append(f"Run {pipeline_command} using the project virtual environment with libpysal/esda installed; no statistic is substituted.")
    map_exists = map_report is not None and map_report.get("generated", True)
    offline = bool(map_report and map_report.get("offline_assets"))
    add("map", "PASS" if map_exists and offline else "PARTIAL", generated=map_exists, offline_assets="yes" if offline else "no",
        external_urls=(map_report or {}).get("external_urls", []), missing_local=(map_report or {}).get("missing_local", []), tiles_online=config.MAP_TILES is not None)
    if not offline:
        map_relative = f"outputs/{config.INDIA_OUTPUT_FOLDER}/{config.INDIA_MAP_FILE}" if scope == "india" else f"outputs/{config.MAP_FILENAME}"
        tasks.append(f"With internet, run python src/cache_map_assets.py {map_relative}; keep its assets directory beside the HTML. Set MAP_TILES=None for a polygon map without online tiles.")
    observed_flags = []
    for table in frames.values():
        if "data_flag" in table:
            observed_flags.extend(table.data_flag.dropna().astype(str).tolist())
    synthetic = any("synthetic" in flag.lower() for flag in observed_flags)
    add("synthetic data in use", "FAIL" if synthetic else "PASS" if "data_flag" in scores else "PARTIAL", synthetic="YES" if synthetic else "NO" if "data_flag" in scores else "unknown",
        synthetic_switches_enabled=bool(config.ALLOW_SYNTHETIC or config.USE_SYNTHETIC_TEST_DATA))
    if synthetic:
        tasks.append("Disable synthetic inputs and regenerate all outputs from real source data.")
    if not comparison:
        command = "python src/load_boundaries.py --compare" + (" --national" if scope == "india" else "")
        tasks.append(f"With internet run {command}; review counts/name differences before changing BOUNDARY_PROVIDER. Both ADM1 and ADM2 downloads and attribution are required for geoBoundaries state selection.")
    sample = f"outputs/{config.INDIA_OUTPUT_FOLDER}/validation_sample.csv" if scope == "india" else "outputs/validation_sample.csv"
    tasks.append(f"Review {sample} charger merges and provisional AHP judgments before making accuracy or expert-weight claims.")
    overall = "FAIL" if any(c["status"] == "FAIL" for c in checks) else "PARTIAL" if any(c["status"] == "PARTIAL" for c in checks) or tasks else "PASS"
    return {"status": overall, "checks": checks, "manual_tasks": tasks}


def main(root=ROOT, scope="state"):
    root = Path(root)
    frames = {}
    suffix = Path(config.INDIA_OUTPUT_FOLDER) if scope == "india" else Path()
    for name, (folder, filename) in config.ACCEPTANCE_INPUT_FILES.items():
        if scope == "india" and name == "crosswalk":
            continue
        path = root / folder / suffix / filename
        if path.exists():
            frames[name] = pd.read_csv(path)
    def read_json(path):
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    output = root / "outputs" / suffix
    boundary = read_json(root / "data/processed" / suffix / config.ACCEPTANCE_BOUNDARY_MANIFEST)
    hotspot = read_json(output / config.ACCEPTANCE_HOTSPOT_FILE)
    comparison = read_json(output / config.BOUNDARY_COMPARISON_FILE)
    national = read_json(output / config.GOOGLE_MAPS_MANIFEST_INPUT) if scope == "india" else {}
    if scope == "india":
        if not boundary and national:
            source = national.get("boundary_source", {})
            boundary = {"district_count": national.get("district_count", 0), "provider": source.get("provider", "supplied snapshot; provider not recorded in older manifest")}
        # Earlier national runs recorded source provenance in their run manifest.
        if "osm" in frames and national.get("osm_source"):
            date = national.get("osm_header", {}).get("snapshot_utc") or config.INDICATOR_UNKNOWN_DATE
            for prefix in ("road", "commercial"):
                frames["osm"][f"{prefix}_source"] = "national_cache (saved run manifest)"
                frames["osm"][f"{prefix}_snapshot_date"] = date
    filename = config.INDIA_MAP_FILE if scope == "india" else config.MAP_FILENAME
    path = output / filename
    map_report = inspect_assets(path.read_text(encoding="utf-8"), path.parent) if path.exists() else None
    if map_report is not None:
        map_report["generated"] = path.stat().st_size > 0 and "L.map(" in path.read_text(encoding="utf-8")
    report = evaluate(frames, boundary, hotspot, map_report, comparison, scope)
    report["scope"] = scope
    if scope == "india":
        supplied = read_json(output / config.SUPPLIED_AUDIT_REPORT)
        if supplied:
            report["checks"].append({"check": "supplied national source audit", "status": "PARTIAL",
                "files": supplied.get("files", [])})
            report["manual_tasks"].extend(supplied.get("manual_tasks", []))
        google_path = output / config.GOOGLE_MAPS_INDIA_FILENAME
        receipt = read_json(google_path.with_suffix(".manifest.json"))
        report["checks"].append({"check": "Google Maps national view", "status": "PARTIAL", "generated": google_path.exists() and google_path.stat().st_size > 0,
            "districts": receipt.get("districts"), "mapped_chargers": receipt.get("mapped_chargers"), "api_authorisation": "unverified; requires browser validation"})
        report["manual_tasks"].append("Run python run_map.py in your terminal and keep it open. Verify the local district view, then Maps JavaScript API/billing/referrer authorisation in the browser. The local SVG fallback does not verify Google authorization. The key is kept out of this report.")
        if report["status"] != "FAIL":
            report["status"] = "PARTIAL"
    for check in report["checks"]:
        print(f"{check['status']}: {check['check']}: " + json.dumps({k:v for k,v in check.items() if k not in ('status','check')}, ensure_ascii=False))
    print("\nMANUAL TASKS:")
    for task in report["manual_tasks"]:
        print("- " + task)
    print("\nACCEPTANCE: " + report["status"])
    save_json(output / config.ACCEPTANCE_OUTPUT_FILE, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--scope", choices=["state", "india"], default="state")
    args = parser.parse_args()
    result = main(args.root, args.scope)
    raise SystemExit(1 if result["status"] == "FAIL" else 0)
