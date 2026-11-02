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


def test_spot_check_template_schema_and_integrity():
    """Verify data/samples/spot_check_TEMPLATE.csv contains 30 valid real chargers."""
    from pathlib import Path
    template_file = Path(__file__).resolve().parents[1] / "data" / "samples" / "spot_check_TEMPLATE.csv"
    assert template_file.exists(), "spot_check_TEMPLATE.csv must exist"
    df = pd.read_csv(template_file)
    assert len(df) == 30, f"Expected 30 records, found {len(df)}"
    required_cols = [
        "spot_id", "name", "latitude", "longitude", "operator",
        "connector_types", "power_kw", "ports", "corridor_or_district",
        "verification_method", "verification_notes", "data_flag"
    ]
    for col in required_cols:
        assert col in df.columns, f"Missing required column: {col}"
    assert df["latitude"].between(8.0, 14.5).all(), "Latitudes must lie within Tamil Nadu bounds"
    assert df["longitude"].between(76.0, 81.0).all(), "Longitudes must lie within Tamil Nadu bounds"
    assert df["ports"].ge(1).all(), "Ports must be at least 1"
    assert df["data_flag"].eq("real").all(), "Spot check data must be marked real"
