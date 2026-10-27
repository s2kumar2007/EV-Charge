"""Provider selection, release downloads and spatial state filtering work offline."""
import json
from types import SimpleNamespace
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box
import config
import boundary_sources as providers
import india_data


def frame(names, geometries):
    return gpd.GeoDataFrame({"shapeName": names, "shapeID": [f"id{i}" for i in range(len(names))]}, geometry=geometries, crs=config.WGS84)


def test_representative_points_select_state(monkeypatch):
    monkeypatch.setattr(config, "STATE_NAME", "Test State")
    districts = providers.clean_boundaries(frame(["Inside", "Outside"], [box(.1,.1,.9,.9), box(2,0,3,1)]), "shapeName", "shapeID")
    states = providers.clean_boundaries(frame(["Test State"], [box(0,0,1,1)]), "shapeName", "shapeID")
    result = providers.select_state(districts, states)
    assert result.district.tolist() == ["Inside"]


def test_same_provider_setting_reaches_national_and_state(monkeypatch):
    calls = []
    monkeypatch.setattr(providers, "download_geoboundaries", lambda level, force=False: calls.append(level) or "national")
    monkeypatch.setattr(providers, "geoboundaries_state", lambda force=False: "state")
    monkeypatch.setattr(config, "BOUNDARY_PROVIDER", "geoboundaries")
    assert providers.load_provider() == "state"
    assert india_data.load_boundaries() == "national" and calls == ["ADM2"]
    monkeypatch.setattr(config, "BOUNDARY_PROVIDER", "pinned_repo")
    monkeypatch.setattr(providers, "pinned_national", lambda force=False: "pinned-national")
    monkeypatch.setattr(providers, "pinned_state", lambda force=False: "pinned-state")
    assert providers.load_provider() == "pinned-state"
    assert india_data.load_boundaries() == "pinned-national"


def test_download_uses_metadata_url_and_saves_attribution(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "RAW", tmp_path)
    metadata = {"gjDownloadURL": "https://fake.invalid/release.geojson", "boundaryLicense": "ODbL 1.0", "boundaryISO": "IND", "boundaryType": "ADM2", "boundaryID": "fictional-release"}
    monkeypatch.setattr(providers, "cached_json", lambda *a, **kw: (kw["validator"](metadata), providers.save_json(a[0], metadata), metadata)[-1])
    payload = frame(["Fictional"], [box(0,0,1,1)]).to_json().encode()
    calls = []
    monkeypatch.setattr(providers, "request_with_retry", lambda method, url: calls.append(url) or SimpleNamespace(content=payload))
    assert len(providers.download_geoboundaries("ADM2")) == 1
    assert calls == [metadata["gjDownloadURL"]]
    assert "ODbL 1.0" in (tmp_path / f"{config.GEOBOUNDARIES_CACHE_PREFIX}_ADM2_attribution.txt").read_text()
    providers.download_geoboundaries("ADM2")
    assert len(calls) == 1
    assert (tmp_path / f"{config.GEOBOUNDARIES_CACHE_PREFIX}_ADM2_metadata.json").exists()


def test_comparison_and_invalid_geometry():
    left = pd.DataFrame({"district": ["A", "B"]})
    right = pd.DataFrame({"district": ["B", "C", "D"]})
    report = providers.compare_providers(left, right)
    assert report["only_pinned_repo"] == ["A"] and report["geoboundaries_count"] == 3
    broken = frame(["A", "B"], [box(0,0,1,1), box(1,0,2,1)])
    broken["shapeID"] = "duplicate"
    with pytest.raises(ValueError, match="unique"):
        providers.clean_boundaries(broken, "shapeName", "shapeID")
