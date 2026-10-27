"""Offline checks of cache policies, warning paths and generated map layers."""
import io
import json
from pathlib import Path
from unittest.mock import Mock
import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import box
import config
import utils
import build_scores
import fetch_chargers
import gap_index
import hotspots
import load_population
import load_vahan
import make_map


def test_cache_offline_reuse_and_force(monkeypatch, tmp_path):
    path = tmp_path / "cached.json"
    path.write_text('{"elements": []}')
    monkeypatch.setattr(config, "OFFLINE", True)
    assert utils.cached_json(path, "GET", "https://fake.invalid", validator=utils.validate_overpass) == {"elements": []}
    with pytest.raises(RuntimeError, match="Offline"):
        utils.cached_json(path, "GET", "https://fake.invalid", force=True)
    with pytest.raises(ValueError, match="incomplete"):
        utils.validate_overpass({"elements": [], "remark": "timeout"})


def test_retry_and_no_key_logging(monkeypatch, capsys):
    import requests
    monkeypatch.setattr(config, "OFFLINE", False)
    request = Mock(side_effect=requests.ConnectionError("key=private-key"))
    monkeypatch.setattr(requests, "request", request)
    with pytest.raises(RuntimeError, match="after 2 attempts"):
        utils.request_with_retry("GET", "https://fake.invalid", attempts=2, wait=0, params={"key": "private-key"})
    assert request.call_count == 2 and "private-key" not in capsys.readouterr().out


def test_port_bool_and_source_parsers():
    assert fetch_chargers.parse_ports(True) == (1, False)
    osm = fetch_chargers.parse_osm({"elements": [{"type": "way", "id": 1, "center": {"lat": .5, "lon": .5}, "tags": {"capacity": "3"}}]})
    ocm = fetch_chargers.parse_ocm([{"ID": 1, "AddressInfo": {"Latitude": .5, "Longitude": .5}, "NumberOfPoints": "abc"}])
    assert osm[0]["ports"] == 3 and osm[0]["ports_known"]
    assert ocm[0]["ports"] == 1 and not ocm[0]["ports_known"]


def test_synthetic_gate_cannot_be_bypassed_by_sample_setting(monkeypatch):
    monkeypatch.setattr(config, "USE_SYNTHETIC_TEST_DATA", False)
    monkeypatch.setattr(config, "VAHAN_SAMPLE_FILE", config.SYNTHETIC_TEST_FILENAME)
    monkeypatch.setattr(load_vahan, "RAW_VAHAN_FILE", Path("fake_missing.csv"))
    monkeypatch.setattr(Path, "exists", lambda path: path.name != "fake_missing.csv")
    with pytest.raises(ValueError, match="blocked"):
        load_vahan.get_vahan_source()


def test_synthetic_file_forces_flag(monkeypatch):
    monkeypatch.setattr(load_vahan, "get_vahan_source", lambda: (Path("test.csv"), "fake", True))
    fake = pd.DataFrame({"district": ["Alpha"], "ev_total": [3], "data_flag": ["real"]})
    monkeypatch.setattr(pd, "read_csv", lambda path: fake.copy())
    table, _ = load_vahan.read_vahan_file()
    assert table.iloc[0].data_flag == "synthetic"


def test_population_download_not_used_before_review(monkeypatch, tmp_path):
    boundaries = gpd.GeoDataFrame({"district": ["Alpha"], "district_key": ["alpha"]}, geometry=[box(0, 0, 1, 1)], crs=config.WGS84)
    fake = pd.DataFrame({"state_name": [config.STATE_NAME], "district_name": ["Alpha"], "pop_total": [1234]})
    monkeypatch.setattr(load_population, "RAW", tmp_path)
    monkeypatch.setattr(load_population, "PROCESSED", tmp_path)
    monkeypatch.setattr(load_population, "download_population", lambda force: fake)
    monkeypatch.setattr(config, "POPULATION_BOUNDARIES_VERIFIED", False)
    assert load_population.main(boundaries).population.isna().all()


def test_map_and_output_contract(monkeypatch, tmp_path):
    # Every value below is an invented test input, not a submission dataset.
    processed, outputs = tmp_path / "processed", tmp_path / "outputs"
    processed.mkdir(); outputs.mkdir()
    for module in (build_scores, make_map, gap_index, hotspots):
        if hasattr(module, "PROCESSED"):
            monkeypatch.setattr(module, "PROCESSED", processed)
        monkeypatch.setattr(module, "OUTPUTS", outputs)
    monkeypatch.setattr(build_scores, "SCORED_GEOJSON", processed / "districts_scored.geojson")
    monkeypatch.setattr(build_scores, "CHARGERS_ASSIGNED", processed / "chargers_assigned.csv")
    monkeypatch.setattr(build_scores, "CHARGERS_UNASSIGNED", processed / "chargers_unassigned.csv")
    monkeypatch.setattr(make_map, "MAP_HTML", outputs / "map.html")
    monkeypatch.setattr(config, "CACHE_MAP_ASSETS", False)
    b = gpd.GeoDataFrame({"district": ["Alpha", "Beta", "Gamma"], "district_key": ["alpha", "beta", "gamma"]},
                         geometry=[box(x, 0, x + 1, 1) for x in range(3)], crs=config.WGS84)
    chargers = pd.DataFrame({"source": ["OSM"], "source_id": ["node/1"], "name": ["Test <station>"], "operator": ["Test energy"],
                             "latitude": [.5], "longitude": [.5], "ports": [2], "ports_known": [True]})
    ev = pd.DataFrame({"district_key": b.district_key, "ev_total": [30, 80, np.nan], "population": [300, 400, np.nan], "data_flag": ["synthetic", "real", "missing"]})
    ev["source_date"] = "2020-01-01"
    ev["ev_year"] = 2020
    ev["ev_measure"] = "fictional annual registrations for map tests"
    basic = build_scores.main(chargers, b, ev, use_dedup=False)
    population = pd.DataFrame({"district_key": b.district_key, "population": [300, 400, np.nan], "population_source": ["fake"] * 3})
    osm = pd.DataFrame({"district_key": b.district_key, "road_km_per_km2": [1, 3, np.nan], "commercial_per_km2": [2, 8, np.nan]})
    index = gap_index.main(basic, population, osm)
    # Supply fictional classes to test rendering, not the statistic implementation.
    pd.DataFrame({"district": b.district, "district_key": b.district_key, "class_raw": ["hot spot 95%"] * 3,
                  "class_fdr": ["not significant"] * 3, "z_score": [2] * 3, "p_value": [.04] * 3,
                  "p_value_fdr": [.12] * 3, "reason": ["fake test"] * 3}).to_csv(outputs / "district_hotspots.csv", index=False)
    make_map.main()
    document = (outputs / "map.html").read_text()
    assert "Composite index" in document and "Hotspots (Gi*)" in document and "Districts (gap score)" in document
    assert "SYNTHETIC TEST DATA IN USE" in document and "Test &lt;station&gt;" in document
    assert "dashArray" in document and "6,4" in document
    assert (outputs / "district_gap_scores.csv").exists()
    assert index[index.district == "Gamma"]['rank'].isna().all()
