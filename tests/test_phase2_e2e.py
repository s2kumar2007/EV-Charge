"""
End-to-end integration test for Phase 2: Bayesian Uncertainty & Planner Assistant.

Executes end-to-end verification across the Bayesian pipeline, FastAPI endpoints,
credible interval reporting, and Planner Assistant Q&A with evidence blocks.
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from api.main import app
from bayes_layer import run_bayesian_pipeline

ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"


@pytest.fixture
def client():
    return TestClient(app)


def test_phase2_bayesian_pipeline_execution(tmp_path):
    """Verify Bayesian uncertainty pipeline generates valid posteriors across all districts."""
    out_file = tmp_path / "test_e2e_posteriors.csv"
    df = run_bayesian_pipeline(
        output_path=out_file,
        save_output=True,
        seed=2026,
    )
    assert out_file.exists()
    assert len(df) >= 30
    assert "req_p50" in df.columns
    assert "model_agreement" in df.columns
    assert "prior_dominated" in df.columns
    assert (df["req_p10"] <= df["req_p50"]).all()
    assert (df["req_p50"] <= df["req_p90"]).all()


def test_phase2_district_api_enriched_payload(client):
    """Verify GET /api/districts/{key} includes Bayesian uncertainty fields in drill-down."""
    resp = client.get("/api/districts/chennai")
    assert resp.status_code == 200
    data = resp.json()
    assert data["district_key"] == "chennai"
    assert "req_p10" in data and "req_p50" in data and "req_p90" in data
    assert "most_likely_gap" in data
    assert "model_agreement" in data


def test_phase2_district_uncertainty_endpoints(client):
    """Verify GET /districts/{id}/uncertainty returns complete Bayesian posterior and drivers."""
    for path in ["/api/districts/chennai/uncertainty", "/districts/chennai/uncertainty"]:
        resp = client.get(path)
        assert resp.status_code == 200
        d = resp.json()
        assert d["district_key"] == "chennai"
        assert d["req_ci_80_width"] >= 0
        assert "provenance_notice" in d
        assert "CEA" in d["provenance_notice"] or "expert" in d["provenance_notice"].lower()


def test_phase2_assistant_grounded_qa_end_to_end(client):
    """Verify POST /assistant executes grounded tool calls and returns required evidence blocks."""
    # 1. Ranking explanation
    q1 = {"question": "Why is Krishnagiri ranked 3rd?"}
    r1 = client.post("/api/assistant", json=q1)
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["status"] == "ok"
    assert "Krishnagiri" in d1["answer"]
    assert "Evidence" in d1["answer"]
    assert len(d1["evidence"]) >= 1

    # 2. Highway corridor gaps & UNVERIFIED warning
    q2 = {"question": "Which highway stretch should we fix first?"}
    r2 = client.post("/api/assistant", json=q2)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["status"] == "ok"
    assert "UNVERIFIED" in d2["answer"]

    # 3. Missing/zero-charger unranked transparency
    q3 = {"question": "Why is Kanyakumari unranked?"}
    r3 = client.post("/assistant", json=q3)
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["status"] == "ok"
    assert "unranked" in d3["answer"].lower()
