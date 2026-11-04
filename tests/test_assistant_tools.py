"""
Unit tests for Planner Assistant read-only tool layer (src/assistant/tools.py).
Tests use fictional temporary fixtures to verify tool behavior, unknown districts,
ambiguity resolution, and data honesty / UNVERIFIED propagation.
"""
import pytest
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def fictional_outputs(tmp_path):
    """Create isolated fictional output CSV files for testing tool retrieval."""
    out_dir = tmp_path / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. district_gap_index.csv
    gap_df = pd.DataFrame([
        {
            "district": "Chennai",
            "district_key": "chennai",
            "rank": 6,
            "gap_score": 75.4,
            "ev_total": 45000,
            "charger_count": 50,
            "port_count": 120,
            "commercial_per_km2": 15.2,
            "road_km_per_km2": 3.4,
            "status": "ok",
            "data_flag": "real",
            "drivers": "High commercial density and high EV registration volume",
        },
        {
            "district": "Krishnagiri",
            "district_key": "krishnagiri",
            "rank": 3,
            "gap_score": 88.1,
            "ev_total": 8500,
            "charger_count": 8,
            "port_count": 14,
            "commercial_per_km2": 2.1,
            "road_km_per_km2": 1.2,
            "status": "ok",
            "data_flag": "real",
            "drivers": "Severe deficit along NH-48 transit corridor",
        },
        {
            "district": "Ariyalur",
            "district_key": "ariyalur",
            "rank": None,
            "gap_score": None,
            "ev_total": None,
            "charger_count": 1,
            "port_count": 1,
            "commercial_per_km2": 0.5,
            "road_km_per_km2": 0.8,
            "status": "no_data",
            "data_flag": "insufficient_data",
            "drivers": "No EV data available; unranked",
        },
        {
            "district": "Synthetic_District",
            "district_key": "synth_dist",
            "rank": None,
            "gap_score": 95.0,
            "ev_total": 9999,
            "charger_count": 0,
            "port_count": 0,
            "commercial_per_km2": 1.0,
            "road_km_per_km2": 1.0,
            "status": "ok",
            "data_flag": "synthetic",
            "drivers": "Synthetic test row",
        },
    ])
    gap_df.to_csv(out_dir / "district_gap_index.csv", index=False)

    # 2. corridor_gaps.csv
    corridor_df = pd.DataFrame([
        {
            "corridor_id": "NH-48",
            "corridor_name": "Chennai-Bengaluru",
            "segment_id": "NH48_seg_2",
            "gap_km": 42.5,
            "max_allowed_km": 25.0,
            "status": "NON_COMPLIANT",
            "data_flag": "real",
            "guideline_status": "UNVERIFIED MoP 2024 indicative figure",
        }
    ])
    corridor_df.to_csv(out_dir / "corridor_gaps.csv", index=False)

    # 3. recommended_sites.csv
    sites_df = pd.DataFrame([
        {
            "rank": 1,
            "name": "Ranipet Toll Plaza",
            "district": "Ranipet",
            "district_key": "ranipet",
            "site_type": "corridor_nh48",
            "ports_recommended": 8,
            "drivers": "FRLM flow coverage on 42km unserved stretch",
            "data_flag": "recommended",
        }
    ])
    sites_df.to_csv(out_dir / "recommended_sites.csv", index=False)

    # 4. bayes_district_posteriors.csv
    bayes_df = pd.DataFrame([
        {
            "district_key": "krishnagiri",
            "district": "Krishnagiri",
            "req_p10": 45,
            "req_p50": 85,
            "req_p90": 130,
            "req_ci_80_width": 85,
            "prob_adequate": 0.05,
            "prob_moderate": 0.25,
            "prob_severe": 0.70,
            "most_likely_gap": "severe",
            "top_driver_1": "Traffic_exposure",
            "top_driver_2": "EV_growth",
            "drivers": "Driven by Traffic_exposure=high; EV_growth=high",
            "prior_dominated": False,
            "p50_shift_ratio": 0.08,
            "model_agreement": "high_agreement",
            "agreement_note": "Bayesian credible median aligns with Monte Carlo deficit estimate",
            "data_flag": "real",
        }
    ])
    bayes_df.to_csv(out_dir / "bayes_district_posteriors.csv", index=False)

    return out_dir


def test_get_district_valid(fictional_outputs):
    """Verify get_district retrieves correct data and metadata for valid district."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    res = tools.get_district("Krishnagiri")
    assert res["status"] == "ok"
    assert res["district_key"] == "krishnagiri"
    assert res["rank"] == 3
    assert res["data_flag"] == "real"
    assert res["evidence"]["source_file"] == "district_gap_index.csv"


def test_get_district_missing_ev(fictional_outputs):
    """Verify districts with missing EV counts report unranked status and insufficient data flag."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    res = tools.get_district("Ariyalur")
    assert res["status"] == "ok"
    assert res["data_flag"] == "insufficient_data"
    assert res["rank"] is None
    assert "no EV data" in res["note"] or "unranked" in res["note"]


def test_get_district_unknown(fictional_outputs):
    """Verify unknown district queries return not_found status with helpful suggestion."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    res = tools.get_district("Atlantis_Zone")
    assert res["status"] == "not_found"
    assert "unknown" in res["message"].lower() or "not found" in res["message"].lower()


def test_district_fuzzy_matching(fictional_outputs):
    """Verify resolver maps typos and common aliases to official district keys."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    # Minor typo 'chenai' -> 'chennai'
    res = tools.get_district("chenai")
    assert res["status"] == "ok"
    assert res["district_key"] == "chennai"


def test_rank_districts_excludes_synthetic(fictional_outputs):
    """Verify rank_districts returns top districts and excludes synthetic records."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    ranked = tools.rank_districts(top_n=5)
    assert len(ranked["districts"]) >= 1
    # Check that synthetic row is NEVER in official rankings
    keys = [d["district_key"] for d in ranked["districts"]]
    assert "synth_dist" not in keys
    assert ranked["evidence"]["data_flag"] == "real"


def test_explain_rank(fictional_outputs):
    """Verify explain_rank provides drivers, rank, score, and methodology."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    res = tools.explain_rank("Krishnagiri")
    assert res["status"] == "ok"
    assert res["rank"] == 3
    assert "drivers" in res
    assert "evidence" in res


def test_get_corridor_gaps_propagates_unverified(fictional_outputs):
    """Verify corridor gaps tool propagates UNVERIFIED guideline warnings."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    gaps = tools.get_corridor_gaps()
    assert len(gaps["gaps"]) == 1
    assert "UNVERIFIED" in gaps["gaps"][0]["guideline_status"]
    assert "warnings" in gaps
    assert any("UNVERIFIED" in w for w in gaps["warnings"])


def test_get_recommended_sites(fictional_outputs):
    """Verify get_recommended_sites returns candidate siting results."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    sites = tools.get_recommended_sites(top_n=3)
    assert len(sites["sites"]) == 1
    assert sites["sites"][0]["name"] == "Ranipet Toll Plaza"
    assert sites["sites"][0]["ports_recommended"] == 8


def test_get_uncertainty(fictional_outputs):
    """Verify get_uncertainty retrieves Bayesian 80% credible interval and drivers."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    unc = tools.get_uncertainty("Krishnagiri")
    assert unc["status"] == "ok"
    assert unc["req_p10"] == 45
    assert unc["req_p50"] == 85
    assert unc["req_p90"] == 130
    assert unc["prior_dominated"] is False
    assert "provenance_notice" in unc


def test_get_data_quality(fictional_outputs):
    """Verify get_data_quality reports confidence, missing flags, and data provenance."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    qual = tools.get_data_quality("Chennai")
    assert qual["status"] == "ok"
    assert qual["data_flag"] == "real"
    assert "confidence" in qual
    assert "provenance" in qual


def test_list_limitations(fictional_outputs):
    """Verify list_limitations enumerates honest jury-facing project caveats."""
    from assistant.tools import AssistantTools
    tools = AssistantTools(outputs_dir=fictional_outputs)
    lims = tools.list_limitations()
    assert len(lims["limitations"]) >= 3
    assert any("unranked" in lim.lower() for lim in lims["limitations"])
    assert any("unverified" in lim.lower() for lim in lims["limitations"])
