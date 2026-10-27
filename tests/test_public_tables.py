"""Fictional official-table extraction tests, with no real source files."""
import pytest
import config
from import_public_tables import parse_count_cells, parse_ev_table, parse_population_table, source_lines
from utils import norm_key


def test_separators_never_guess():
    assert parse_count_cells("1 2 34",3) == [1,2,34]
    assert parse_count_cells("001",3) == [0,0,1]
    assert parse_count_cells("1 234",3) is None
    assert parse_count_cells("14 18",3) is None


def test_ev_totals_and_ambiguous_cells(monkeypatch):
    lines={0:("0","Alpha"),1:("0","2WN 1 2 3"),2:("0","LMV000"),
           3:("0","Beta"),4:("0","2WN 1 234")}
    monkeypatch.setattr(config,"PUBLIC_EV_TABLE_FIRST_LINE",0)
    monkeypatch.setattr(config,"PUBLIC_EV_TABLE_LAST_LINE",4)
    totals,audit=parse_ev_table(lines)
    assert totals.iloc[0].ev_total == 3
    assert totals.iloc[0].data_flag == "real"
    assert totals.iloc[1].data_flag == "missing"
    assert totals.iloc[1].extraction_status.startswith("ambiguous")
    assert len(audit)==3
    assert "not cumulative fleet" in totals.iloc[0].ev_measure


def test_incomplete_extraction_rejected(monkeypatch):
    monkeypatch.setattr(config,"PUBLIC_EV_TABLE_FIRST_LINE",0)
    monkeypatch.setattr(config,"PUBLIC_EV_TABLE_LAST_LINE",2)
    with pytest.raises(ValueError,match="incomplete"):
        parse_ev_table({0:("0","Alpha")})


def test_population_candidates_not_promoted(monkeypatch):
    monkeypatch.setattr(config,"PUBLIC_POPULATION_FIRST_LINE",0)
    monkeypatch.setattr(config,"PUBLIC_POPULATION_LAST_LINE",0)
    table=parse_population_table({0:("0","1. Alpha 1234 10 8 1.0 2.0")})
    assert table.iloc[0].population == 1234
    assert table.iloc[0].boundary_compatibility.startswith("not verified")
    assert table.iloc[0].population_flag.startswith("official estimate")


def test_generic_articles_and_source_conflicts():
    assert norm_key("The Alpha District") == norm_key("Alpha")
    with pytest.raises(ValueError,match="Conflicting"):
        source_lines([{"content":[{"text":"L1@P0: Alpha"},{"text":"L1@P0: Beta"}]}])
