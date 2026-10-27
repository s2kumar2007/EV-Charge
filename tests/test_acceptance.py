"""Acceptance statuses use fictional in-memory evidence only."""
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_acceptance as acceptance
import config


def test_missing_evidence_is_partial_and_never_zero_claim():
    report = acceptance.evaluate({}, {}, {}, None)
    assert report["status"] == "PARTIAL"
    chargers = next(c for c in report["checks"] if c["check"] == "chargers")
    assert chargers["raw"] is None
    assert next(c for c in report["checks"] if c["check"] == "synthetic data in use")["synthetic"] == "unknown"


def test_synthetic_input_fails():
    frames = {"scores": pd.DataFrame({"data_flag": ["synthetic"], "ev_total": [1], "ev_measure": ["fictional annual"], "rank": [1]})}
    report = acceptance.evaluate(frames, {"provider": config.BOUNDARY_PROVIDER, "district_count": 1}, {}, None)
    assert report["status"] == "FAIL"
    assert next(c for c in report["checks"] if c["check"] == "synthetic data in use")["synthetic"] == "YES"


def test_numbers_dates_and_missing_map_assets_are_reported():
    frames = {"scores": pd.DataFrame({"data_flag": ["real"], "ev_total": [1], "rank": [1], "ev_measure": ["fictional annual"]}),
              "raw": pd.DataFrame({"ports_known": [True, False]}), "deduplicated": pd.DataFrame({"ports_known": [True]}),
              "osm": pd.DataFrame({"road_km_per_km2": [1], "road_source": ["national_cache"], "road_snapshot_date": ["fake-date"]})}
    report = acceptance.evaluate(frames, {"provider": config.BOUNDARY_PROVIDER, "district_count": 1}, {"I": None, "n": 0, "gistar_n": 0}, {"offline_assets": False, "external_urls": ["https://fake.invalid/a.js"]})
    roads = next(c for c in report["checks"] if c["check"] == "roads")
    assert roads["status"] == "PASS" and roads["snapshot_dates"] == ["fake-date"]
    chargers = next(c for c in report["checks"] if c["check"] == "chargers")
    assert chargers["raw"] == 2 and chargers["deduplicated_ports_known"] == 1
    assert report["status"] == "PARTIAL"


def test_india_missing_ev_asks_for_national_input_not_state_pdf():
    frames={"scores":pd.DataFrame({"ev_total":[None],"data_flag":["missing"]})}
    report=acceptance.evaluate(frames,{"district_count":1,"provider":config.BOUNDARY_PROVIDER},{},None,scope="india")
    tasks=" ".join(report["manual_tasks"])
    assert config.INDIA_EV_FILE in tasks and config.PUBLIC_EV_PDF_FILE not in tasks
    assert config.INDIA_POPULATION_FILE in tasks


def test_national_report_keeps_browser_key_out(tmp_path, capsys):
    import json
    output=tmp_path / "outputs" / config.INDIA_OUTPUT_FOLDER
    output.mkdir(parents=True)
    pd.DataFrame({"district_key":["fake-id"],"ev_total":[None],"data_flag":["missing"],"rank":[None]}).to_csv(output/"district_gap_scores.csv",index=False)
    (output/config.GOOGLE_MAPS_MANIFEST_INPUT).write_text(json.dumps({"district_count":1,"boundary_source":{"provider":config.BOUNDARY_PROVIDER}}))
    native=output/config.GOOGLE_MAPS_INDIA_FILENAME
    native.write_text('<script src="https://fake.invalid/?key=fake-private-key"></script>')
    native.with_suffix('.manifest.json').write_text(json.dumps({"districts":1,"mapped_chargers":0}))
    (output/config.SUPPLIED_AUDIT_REPORT).write_text(json.dumps({"files":[{"file":"fake.xlsx","district_totals":2}],"manual_tasks":["Review fake geography"]}))
    report=acceptance.main(tmp_path,scope="india")
    assert any(c["check"] == "supplied national source audit" for c in report["checks"])
    assert "Review fake geography" in report["manual_tasks"]
    assert report["scope"] == "india" and report["status"] == "PARTIAL"
    assert "fake-private-key" not in json.dumps(report)
    assert "fake-private-key" not in capsys.readouterr().out
    assert (output/config.ACCEPTANCE_OUTPUT_FILE).exists()
