"""
Tests for FastAPI application endpoints using TestClient.
Uses in-memory mocks / fixtures to test offline behavior.
"""
import pytest
from fastapi.testclient import TestClient

from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_index_endpoint(client):
    """Verify GET / returns the static Leaflet dashboard index page."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert "ChargeGap India" in resp.text
    assert "id=\"map\"" in resp.text


def test_get_districts_endpoint(client):
    """Verify GET /api/districts returns list with standard schema columns."""
    resp = client.get("/api/districts")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    if data:
        row = data[0]
        assert "district_key" in row
        assert "data_flag" in row


def test_get_district_by_key_endpoint(client):
    """Verify GET /api/districts/{key} returns single district or 404."""
    resp = client.get("/api/districts/chennai")
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        data = resp.json()
        assert data["district_key"] == "chennai"
        # Verify enrichment fields from requirements and hotspots if available
        if "ports_deficit" in data and data["ports_deficit"] is not None:
            assert isinstance(data["ports_deficit"], (int, float))
        if "confidence" in data and data["confidence"] is not None:
            assert 0.0 <= float(data["confidence"]) <= 1.0

    # Non-existent key must return 404
    resp_404 = client.get("/api/districts/non_existent_district_xyz")
    assert resp_404.status_code == 404


def test_districts_handles_indicative_and_missing_data_state(client):
    """Verify API gracefully structures records even when values are None/indicative."""
    resp = client.get("/api/districts")
    assert resp.status_code == 200
    districts = resp.json()
    for d in districts:
        assert "district" in d
        assert "data_flag" in d
        if d.get("rank") is None:
            assert d.get("ev_total") is None


def test_get_corridors_endpoint(client):
    """Verify GET /api/corridors returns list of highway corridor stretches."""
    resp = client.get("/api/corridors")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_get_sites_endpoint(client):
    """Verify GET /api/sites returns recommended priority charging sites."""
    resp = client.get("/api/sites")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_post_whatif_recomputes_ranges(client):
    """Verify POST /api/whatif recomputes deficit ranges under custom parameters."""
    payload = {
        "adoption_growth_pct": 30.0,
        "target_ratio": 25.0,
        "undercount_factor": 1.3,
    }
    resp = client.post("/api/whatif", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "districts" in data
    assert "parameters" in data
    assert "summary" in data
    assert "total_p50_port_deficit" in data["summary"]
    assert "total_simulated_evs" in data["summary"]
