"""Offline crosswalk tests use only fictional names and in-memory polygons."""
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box
import config
import load_population as pop


def boundaries():
    return gpd.GeoDataFrame({"district": ["Alphaville", "Betatown"], "district_key": ["alphaville", "betatown"]},
                            geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=config.WGS84)


def test_proposals_do_not_promote_fuzzy_or_geocode():
    values = pd.DataFrame({"district": ["Alphaville", "Betatow", "Elsewhere"], "population": [10, 20, 30]})
    crosswalk = pop.propose_crosswalk(values, boundaries(), lambda q: [.5, 1.5])
    assert crosswalk.relation.tolist() == ["one_to_one", "needs_human_check", "needs_human_check"]
    assert "suggestion, not verified" in crosswalk.iloc[1].evidence
    result = pop.attach_crosswalk(values, boundaries(), crosswalk)
    assert result.population.iloc[0] == 10 and pd.isna(result.population.iloc[1])


def test_verified_many_to_one_sums_without_partial_totals():
    values = pd.DataFrame({"district": ["Old East", "Old West"], "population": [10, 20]})
    crosswalk = pd.DataFrame({"population_district": values.district, "polygon_district": ["Alphaville"]*2,
        "relation": ["many_to_one"]*2, "method": ["geocode"]*2, "evidence": ["reviewed source"]*2, "verified": ["yes"]*2})
    assert pop.attach_crosswalk(values, boundaries(), crosswalk).population.iloc[0] == 30
    crosswalk.loc[1, "verified"] = "no"
    assert pop.attach_crosswalk(values, boundaries(), crosswalk).population.isna().all()
    crosswalk.loc[1, "verified"] = "yes"
    values.loc[1, "population"] = None
    assert pop.attach_crosswalk(values, boundaries(), crosswalk).population.isna().all()


def test_no_split_or_false_exact():
    values = pd.DataFrame({"district": ["Alphaville"], "population": [10]})
    crosswalk = pop.propose_crosswalk(values, boundaries(), lambda q: None)
    with pytest.raises(ValueError, match="duplicate"):
        pop.attach_crosswalk(values, boundaries(), pd.concat([crosswalk, crosswalk]))
    crosswalk.loc[0, "polygon_district"] = "Betatown"
    with pytest.raises(ValueError, match="exact"):
        pop.attach_crosswalk(values, boundaries(), crosswalk)


def test_crosswalk_preserves_human_decisions(tmp_path):
    values = pd.DataFrame({"district": ["Other"], "population": [10]})
    path = tmp_path / "crosswalk.csv"
    crosswalk = pop.propose_crosswalk(values, boundaries(), lambda q: None)
    crosswalk.loc[0, ["relation", "verified", "polygon_district"]] = ["many_to_one", "yes", "Alphaville"]
    crosswalk.to_csv(path, index=False)
    result = pop.candidate_population(boundaries(), values, path, lambda q: pytest.fail("must reuse review"))
    assert result.population.iloc[0] == 10
