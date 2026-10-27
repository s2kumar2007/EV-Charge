"""Offline Slice 1 tests: invented records, polygons and indicators only."""
import sys
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd
import geopandas as gpd
import pytest
from shapely.geometry import box
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config
import dedupe_chargers as dedupe
import fetch_indicators
import gap_index
import hotspots
import load_population
import validate_chargers
from build_scores import assign_chargers_to_districts


def raw_points():
    # These are invented metric test positions, then converted to WGS84.
    points = gpd.GeoDataFrame({"source": ["OSM", "OCM", "OSM"], "source_id": ["node/1", "1", "node/2"],
                              "name": ["Test station"] * 3, "operator": ["Test energy"] * 3,
                              "ports": [2, 4, 1], "ports_known": [True, True, False]},
                             geometry=gpd.points_from_xy([500000, 500010, 501000], [1000000] * 3), crs="EPSG:32631").to_crs(config.WGS84)
    points["latitude"], points["longitude"] = points.geometry.y, points.geometry.x
    return pd.DataFrame(points.drop(columns="geometry"))


def fake_boundaries():
    return gpd.GeoDataFrame({"district": ["Alpha", "Beta"], "district_key": ["alpha", "beta"]},
                            geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=config.WGS84)


def index_inputs():
    return pd.DataFrame({"district": ["A", "B", "C", "D"], "district_key": ["a", "b", "c", "d"],
                         "data_flag": ["real", "synthetic", "real", "missing"],
                         "ev_pressure": [5, 8, 2, np.nan], "evs_per_100k": [1, 2, 4, 2],
                         "road_km_per_km2": [2, 3, 5, 2], "commercial_per_km2": [9, 3, 1, 4]})


def test_distance_and_max_ports():
    result, audit = dedupe.deduplicate(raw_points(), radius=40)
    assert len(result) == 2
    merged = result[result.n_source_records == 2].iloc[0]
    assert merged.ports == 4 and merged.ports_known
    assert set(__import__('json').loads(merged.sources)) == {"OSM", "OCM"}
    assert len(audit) == 3 and audit.groupby("cluster_id").size().max() == 2


def test_confidence_independent_sources():
    inputs = raw_points().iloc[:2].copy()
    independent = dedupe.deduplicate(inputs)[0].iloc[0].confidence
    inputs["source"] = "OSM"
    inputs["source_id"] = ["node/a", "node/b"]
    same_source = dedupe.deduplicate(inputs)[0].iloc[0].confidence
    assert 0 <= same_source < independent <= 1


def test_distinct_operators_stay_separate():
    inputs = raw_points().iloc[:2].copy()
    inputs["operator"] = ["Operator A", "Different company"]
    assert len(dedupe.deduplicate(inputs)[0]) == 2


def test_unnamed_and_empty():
    inputs = raw_points().iloc[:2].copy()
    inputs["name"], inputs["operator"], inputs["ports_known"] = "", "", False
    result, _ = dedupe.deduplicate(inputs, radius=100)
    assert len(result) == 1 and result.iloc[0].ports == 1 and not result.iloc[0].ports_known
    result, audit = dedupe.deduplicate(inputs.iloc[:0])
    assert result.empty and audit.empty and "confidence" in result


def test_no_long_chain_merging():
    inputs = raw_points().copy()
    inputs.loc[2, "longitude"] = inputs.loc[0, "longitude"] + 2 * (inputs.loc[1, "longitude"] - inputs.loc[0, "longitude"])
    result, _ = dedupe.deduplicate(inputs, radius=15)
    assert len(result) == 2


def test_entropy_constant_zero():
    weights = gap_index.entropy_weights(pd.DataFrame({"varying": [0, 1, 2], "constant": [1, 1, 1]}))
    assert np.isclose(weights.sum(), 1) and weights[1] == 0
    with pytest.raises(ValueError, match="constant"):
        gap_index.entropy_weights(np.ones((3, 4)))


def test_reproducible_ranks_and_missing():
    first, metadata = gap_index.compute_index(index_inputs())
    second, _ = gap_index.compute_index(index_inputs())
    pd.testing.assert_frame_equal(first, second)
    assert first.loc[3, ["rank", "composite_score", "min_rank", "max_rank"]].isna().all()
    assert first.loc[1, "synthetic"]
    assert "ev_pressure" in first.loc[3, "missing_indicators"]
    assert sum(metadata["entropy_weights"].values()) == pytest.approx(1)
    ranked = first[first['rank'].notna()]
    assert ((ranked.min_rank >= 1) & (ranked.max_rank <= len(ranked))).all()
    assert ranked.top_k_share.between(0, 1).all()


def test_constant_index_is_unranked():
    inputs = index_inputs()
    inputs[config.INDICATORS] = 1
    result, metadata = gap_index.compute_index(inputs)
    assert result['rank'].isna().all() and metadata['entropy_weights'] is None


def test_ahp_matrix_validation(monkeypatch):
    weights, ratio = gap_index.ahp_weights()
    assert np.allclose(weights, np.ones(4) / 4) and ratio == pytest.approx(0)
    matrix = np.ones((4, 4)); matrix[0, 1] = 2
    monkeypatch.setattr(config, "AHP_MATRIX", matrix)
    with pytest.raises(ValueError, match="reciprocal"):
        gap_index.ahp_weights()


def test_robust_scaling(monkeypatch):
    monkeypatch.setattr(config, "SCALING_METHOD", "robust")
    scaled = gap_index.scale_indicators(index_inputs().loc[:2, config.INDICATORS])
    assert scaled.min().min() >= 0 and scaled.max().max() <= 1


def test_spatial_border_and_outside():
    inputs = pd.DataFrame({"latitude": [.5, .5, .5], "longitude": [.5, 1., 3.]})
    assigned = assign_chargers_to_districts(inputs, fake_boundaries())
    assert len(assigned) == 3
    assert assigned.district.notna().sum() == 2
    assert assigned.iloc[1].district_key == "alpha"


def test_osm_indicators_clip_and_failure():
    b = fake_boundaries()
    roads = {"elements": [{"id": 1, "geometry": [{"lon": .5, "lat": .5}, {"lon": 1.5, "lat": .5}]}]}
    pois = {"elements": [{"id": 1, "lon": .5, "lat": .5}, {"id": 1, "lon": .5, "lat": .5}]}
    result = fetch_indicators.derive_indicators(b, roads, pois)
    assert result.road_km_per_km2.gt(0).all()
    assert result.loc[0, "commercial_per_km2"] > 0 and result.loc[1, "commercial_per_km2"] == 0
    missing = fetch_indicators.derive_indicators(b, None, None)
    assert missing[config.INDICATORS[2:]].isna().all().all()
    assert "out geom" in fetch_indicators.query_for(b.total_bounds, "roads")


def test_population_exact_only_and_duplicate():
    values = pd.DataFrame({"district": ["Alpha"], "population": [1234]})
    result = load_population.match_population(values, fake_boundaries())
    assert result.loc[0, "population"] == 1234 and pd.isna(result.loc[1, "population"])
    with pytest.raises(ValueError, match="duplicate"):
        load_population.match_population(pd.concat([values, values]), fake_boundaries())


def test_population_pagination(monkeypatch):
    def fake_cache(path, method, url, params, force):
        offset = params["offset"]
        return {"num_rows_total": 2, "rows": [{"row": {"district_name": str(offset)}}]}
    monkeypatch.setattr(load_population, "cached_json", fake_cache)
    values = load_population.download_population()
    assert len(values) == 2 and values.iloc[1].district_name == "1"


def test_human_validation():
    table = pd.DataFrame({"n_source_records": [2, 2, 1, 3], "checked_ok": ["yes", "no", "yes", ""]})
    result = validate_chargers.validation_precision(table)
    assert result["precision"] == .5 and result["reviewed_merges"] == 2 and result["unreviewed_merges"] == 1
    assert validate_chargers.validation_precision(table.iloc[:0])["precision"] is None


def test_fdr_and_labels():
    adjusted = hotspots.fdr_bh([.01, .04, .03, np.nan])
    assert np.allclose(adjusted[:3], [.03, .04, .04]) and np.isnan(adjusted[3])
    assert hotspots.classify(2, .001).startswith("hot spot")
    assert hotspots.classify(-2, .001).startswith("cold spot")
    assert hotspots.classify(np.nan, .001) == "not tested"


def test_missing_hotspots_do_not_invent_statistics():
    b = fake_boundaries()
    result, metadata = hotspots.analyse_hotspots(b, pd.DataFrame({"district_key": b.district_key, "composite_score": [np.nan, np.nan]}))
    assert result.p_value.isna().all() and metadata["I"] is None
    assert (result['class'] == 'not tested').all()


def test_gistar_high_cluster_grid():
    pytest.importorskip("libpysal", reason="PySAL unavailable: dependency install blocked by DNS")
    pytest.importorskip("esda", reason="PySAL unavailable: dependency install blocked by DNS")
    # Four high cells in one corner of an invented 3x3 district grid.
    cells = [(x, y) for y in range(3) for x in range(3)]
    b = gpd.GeoDataFrame({"district": [f"Cell {x} {y}" for x, y in cells],
                          "district_key": [f"cell{x}{y}" for x, y in cells]},
                         geometry=[box(x, y, x + 1, y + 1) for x, y in cells], crs=config.WGS84)
    values = pd.DataFrame({"district_key": b.district_key,
                           "composite_score": [100 if x < 2 and y < 2 else 1 for x, y in cells]})
    result, _ = hotspots.analyse_hotspots(b, values, permutations=999, seed=123)
    assert result.loc[result.district_key == "cell00", "class_raw"].iloc[0].startswith("hot spot")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-rs"]))


def test_missing_pysal_leaves_actual_usage_zero(monkeypatch):
    monkeypatch.setitem(sys.modules, "libpysal", None)
    b = gpd.GeoDataFrame({"district": ["A", "B", "C"], "district_key": ["a", "b", "c"]},
        geometry=[box(x, 0, x+1, 1) for x in range(3)], crs=config.WGS84)
    result, metadata = hotspots.analyse_hotspots(b, pd.DataFrame({"district_key": b.district_key, "composite_score": [1, 2, 3]}))
    assert metadata["n"] == 0 and metadata["n_eligible"] == 3 and metadata["gistar_n"] == 0
    assert metadata["I"] is None and result.p_value.isna().all()
    assert result.reason.eq("PySAL dependencies unavailable").all()
