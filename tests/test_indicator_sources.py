"""Offline source priority, clipping, missing coverage and date checks."""
import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import box
import config
import fetch_indicators as indicators


def boundaries():
    return gpd.GeoDataFrame({"district": ["West", "East", "Empty"], "district_key": ["west", "east", "empty"]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)], crs=config.WGS84)


def extract():
    return {"roads": {"elements": [{"id": 1, "geometry": [{"lon": -.5, "lat": .5}, {"lon": 1.5, "lat": .5}]}]},
            "pois": {"elements": [{"id": 2, "lon": .5, "lat": .5}, {"id": 3, "lon": -1, "lat": .5}]}}


def test_road_split_and_missing_coverage():
    b = boundaries()
    clipped = indicators.clip_national(extract(), b, "roads")
    assert clipped["elements"][0]["geometry"][0]["lon"] == 0
    clipped["coverage_keys"] = ["west", "east"]
    result = indicators.derive_indicators(b, clipped, None)
    assert result.road_km.iloc[0] > 0
    assert result.road_km.iloc[1] == pytest.approx(result.road_km.iloc[0] / 2, rel=.002)
    assert np.isnan(result.road_km.iloc[2])
    assert result.commercial_per_km2.isna().all()
    assert len(indicators.clip_national(extract(), b, "pois")["elements"]) == 1


def test_source_order_and_snapshot(monkeypatch):
    b = boundaries()
    monkeypatch.setattr(config, "OFFLINE", True)
    monkeypatch.setattr(indicators, "state_cache", lambda b, k: ({"elements": []}, "state-date", "state.json") if k == "roads" else None)
    calls = []
    def national():
        calls.append(1)
        return extract(), "national-date", "fake.gz"
    monkeypatch.setattr(indicators, "national_extract", national)
    downloads, provenance = indicators.choose_sources(b)
    assert provenance["roads"]["source"] == "state_cache"
    assert provenance["roads"]["snapshot_date"] == "state-date"
    assert provenance["pois"]["source"] == "national_cache"
    assert provenance["pois"]["snapshot_date"] == "national-date"
    assert len(calls) == 1


def test_absent_sources_never_become_zero(monkeypatch):
    monkeypatch.setattr(config, "OFFLINE", True)
    monkeypatch.setattr(indicators, "state_cache", lambda *a: None)
    monkeypatch.setattr(indicators, "national_extract", lambda: None)
    downloads, provenance = indicators.choose_sources(boundaries())
    result = indicators.derive_indicators(boundaries(), **{ "roads": downloads["roads"], "pois": downloads["pois"] })
    assert result[["road_km_per_km2", "commercial_per_km2"]].isna().all().all()
    assert provenance["roads"]["source"] == "missing"


def test_partial_answer_rejected():
    with pytest.raises(ValueError, match="incomplete"):
        indicators.derive_indicators(boundaries(), {"elements": [], "remark": "timeout"}, None)


def test_identified_cache_works_without_original_pbf(tmp_path, monkeypatch):
    import gzip, json
    monkeypatch.setattr(indicators, "ROOT", tmp_path)
    monkeypatch.setattr(indicators, "RAW", tmp_path)
    value = extract()
    value["source"] = {"file": "fictional.pbf", "sha256": "fakehash", "bytes": 10}
    cache = tmp_path / f"india_pbf_fakehash_v{config.INDIA_READER_VERSION}.json.gz"
    with gzip.open(cache, "wt") as stream:
        json.dump(value, stream)
    loaded, date, name = indicators.national_extract()
    assert loaded == value and date == "unknown" and name == cache.name
    value["source"]["sha256"] = "disagrees"
    with gzip.open(cache, "wt") as stream:
        json.dump(value, stream)
    with pytest.raises(ValueError, match="provenance"):
        indicators.national_extract()
