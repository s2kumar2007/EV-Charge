"""Supplied-file processing uses fictional in-memory tables, never internet."""
import pandas as pd
import pytest
import import_supplied_data as supplied


def test_census_keeps_only_district_total_and_preserves_source_values():
    frame = pd.DataFrame({"State": ["01"]*3, "District": ["001"]*3,
        "Level": ["DISTRICT"]*3, "Name": ["Fiction"]*3,
        "TRU": ["Total", "Rural", "Urban"], "TOT_P": ["30", "10", "20"]})
    result = supplied.census_candidates(frame)
    assert result.population.tolist() == [30]
    assert result.boundary_compatible.tolist() == ["no"]
    with pytest.raises(ValueError, match="duplicated"):
        supplied.census_candidates(pd.concat([frame, frame]))


def test_national_name_suggestions_never_accept_geography():
    pop = pd.DataFrame({"district": ["Fiction", "Other"], "state_code": ["01"]*2, "district_code": ["001", "002"]})
    boundary = pd.DataFrame({"district": ["Fiction", "Fiction"], "district_key": ["x", "y"]})
    result = supplied.propose_national_crosswalk(pop, boundary)
    assert result.polygon_ids_suggested.tolist() == ["x|y", ""]
    assert result.verified.eq("no").all() and result.relation.eq("needs_human_check").all()


def test_ev_national_totals_are_audited_but_not_disaggregated():
    result = supplied.inspect_ev_export('Title\nFuel,Two Wheeler,Total\nFake,10,10\nTotal,10,10')
    assert result["fuel_totals"]["Total"] == 10
    assert result["district_rows"] == 0 and not result["usable_for_district_ranking"]
    with pytest.raises(ValueError, match="sum"):
        supplied.inspect_ev_export('Title\nFuel,Two Wheeler,Total\nFake,10,11')


def test_census_printed_country_total_must_reconcile():
    frame = pd.DataFrame({"State": ["00", "01"], "District": ["000", "001"],
        "Level": ["India", "DISTRICT"], "Name": ["Country", "Fiction"],
        "TRU": ["Total", "Total"], "TOT_P": ["99", "30"]})
    with pytest.raises(ValueError, match="printed India total"):
        supplied.census_candidates(frame)
    frame.loc[0, "TOT_P"] = "30"
    assert supplied.census_candidates(frame).population.tolist() == [30]
