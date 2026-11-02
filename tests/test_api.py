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
        assert resp.json()["district_key"] == "chennai"

    # Non-existent key must return 404
    resp_404 = client.get("/api/districts/non_existent_district_xyz")
    assert resp_404.status_code == 404


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
