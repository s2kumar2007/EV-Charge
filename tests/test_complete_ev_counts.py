"""Original-PDF recovery tests use fake word coordinates and table rows."""
import pandas as pd
import pytest
from types import SimpleNamespace
import config
import complete_ev_counts as recovery


def word(text, x=1, top=1):
    return {"text": text, "x0": x, "x1": x+5, "top": top, "bottom": top+5}


def row(district, category, value):
    return {"district": district, "category": category, "values": {str(y): value for y in config.PUBLIC_EV_YEARS}, "page": 1}


def base():
    baseline = pd.DataFrame({"district": ["Alpha", "Beta"], "ev_total": [7, None], "data_flag": ["real", "missing"],
        "ev_year": [2025,2025], "ev_measure": [config.PUBLIC_EV_MEASURE_LABEL]*2})
    expected = pd.DataFrame({"district": ["Alpha", "Alpha", "Beta", "Beta"], "category": ["2WN", "LMV", "2WN", "LMV"]})
    return baseline, expected


def test_numeric_cell_requires_unambiguous_separators():
    assert recovery.integer_cell([word("1,234")]) == 1234
    assert recovery.integer_cell([word("1,23,456")]) == 123456
    assert recovery.integer_cell([word("1,"), word("234",10)]) == 1234
    assert recovery.integer_cell([word("1"),word("234",10)]) is None
    assert recovery.integer_cell([word("1"),word("2,345",10)]) is None
    assert recovery.integer_cell([]) is None


def test_word_coordinates_respect_cell_borders():
    words = [word("123",2),word("999",30)]
    cell = recovery.cell_from_words(words, (0,0,20,10),1,2025)
    assert cell["raw"] == "123" and cell["value"] == 123
    assert cell["words"][0]["x0"] == 2 and cell["coordinate_units"] == "PDF points"


def test_recovery_keeps_original_totals_and_checks_printed_totals():
    baseline, expected = base()
    rows = [row("Alpha","2WN",3),row("","LMV",4),row("","Total",7),row("Beta","2WN",5),row("","LMV",1),row("Grand Total","",13)]
    result, checks = recovery.reconcile(rows,baseline,expected)
    assert result.ev_total.tolist() == [7,6]
    assert all(check["status"] == "PASS" for values in checks.values() for check in values)
    assert result.ev_measure.eq(config.PUBLIC_EV_MEASURE_LABEL).all()


def test_disagreement_stops_without_mutating_baseline():
    baseline, expected = base()
    before = baseline.copy()
    with pytest.raises(ValueError,match="STOP"):
        recovery.reconcile([row("Alpha","2WN",3),row("","LMV",9)],baseline,expected)
    pd.testing.assert_frame_equal(before,baseline)


def test_missing_cells_and_missing_categories_stay_missing():
    baseline, expected = base()
    rows = [row("Alpha","2WN",3),row("","LMV",4),row("Beta","2WN",None),row("","LMV",1)]
    result,_ = recovery.reconcile(rows,baseline,expected)
    assert pd.isna(result.ev_total.iloc[1]) and result.data_flag.iloc[1] == "missing"
    result,_ = recovery.reconcile(rows[:-1],baseline,expected)
    assert pd.isna(result.ev_total.iloc[1])


def test_bad_printed_total_stops():
    baseline, expected = base()
    rows = [row("Alpha","2WN",3),row("","LMV",4),row("","Total",8)]
    with pytest.raises(ValueError,match="printed totals"):
        recovery.reconcile(rows,baseline,expected)


def test_layout_fallback_has_honest_character_coordinates(monkeypatch):
    monkeypatch.setattr(config,"PUBLIC_EV_PDF_FIRST_TABLE_PAGE",1)
    text = "Alpha   2WN   1   2   3\n        LMV   0   0   4"
    rows, audit, backend = recovery.parse_layout(text,["Alpha"])
    assert rows[0]["values"]["2025"] == 3
    assert "not PDF points" in audit[0]["coordinate_units"]
    assert "pdftotext" in backend
    assert len(audit) == 10 and audit[1]["column"] == "category"
    rows,_,_ = recovery.parse_layout("Alpha   2WN   1 2 3",["Alpha"])
    assert rows[0]["values"]["2025"] is None


def test_pdfplumber_backend_uses_words_and_grid(monkeypatch):
    monkeypatch.setattr(config,"PUBLIC_EV_PDF_FIRST_TABLE_PAGE",1)
    cells=[(0,0,20,10),(20,0,40,10),(40,0,60,10),(60,0,80,10),(80,0,100,10)]
    words=[word("Alpha",1),word("2WN",21),word("1",41),word("2",61),word("3",81)]
    page=SimpleNamespace(extract_words=lambda **kw:words,find_tables=lambda **kw:[SimpleNamespace(rows=[SimpleNamespace(cells=cells)])])
    class Document:
        pages=[page]
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(recovery.importlib,"import_module",lambda name:SimpleNamespace(open=lambda path:Document()))
    rows,audit,backend=recovery.pdfplumber_rows("fake.pdf")
    assert rows[0]["values"]["2025"] == 3 and len(audit) == 5
    assert backend == "pdfplumber word coordinates"


def test_fallback_does_not_skip_printed_totals(monkeypatch):
    monkeypatch.setattr(config,"PUBLIC_EV_PDF_FIRST_TABLE_PAGE",1)
    text="Alpha   2WN   3   3   3\n        LMV   4   4   4\n        Total   7   7   7\nBeta   2WN   5   5   5\n       LMV   1   1   1\nGrand Total   13   13   13"
    rows,_,_=recovery.parse_layout(text,["Alpha","Beta"])
    baseline,expected=base()
    _,checks=recovery.reconcile(rows,baseline,expected)
    assert len(checks["printed_district_totals"]) == 3
    assert len(checks["printed_state_totals"]) == 3


def test_unrecognised_district_never_inherits_previous_district():
    baseline,expected=base()
    rows=[row("Alpha","2WN",3),row("Unknown source district","LMV",4)]
    with pytest.raises(ValueError,match="Unrecognised PDF district"):
        recovery.reconcile(rows,baseline,expected)


def test_failed_reconciliation_retains_existing_and_extracted_audit():
    baseline, expected = base()
    checks = {}
    with pytest.raises(ValueError, match="STOP"):
        recovery.reconcile([row("Alpha", "2WN", 3), row("", "LMV", 9)], baseline, expected, checks)
    check = checks["baseline_check"][0]
    assert check["existing"] == 7 and check["extracted"] == 12 and check["status"] == "STOP"


def test_borderless_page_edge_row_uses_word_positions(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_EV_PDF_FIRST_TABLE_PAGE", 1)
    boxes=[(0,20,20,40),(20,20,40,40),(40,20,60,40),(60,20,80,40),(80,20,100,40)]
    words=[dict(word(text,x),top=25,bottom=35) for text,x in [("Alpha",1),("LMV",21),("1",41),("2",61),("3",81)]]
    words += [dict(word(text,x),top=5,bottom=15) for text,x in [("2WN",21),("4",41),("5",61),("6",81)]]
    page=SimpleNamespace(extract_words=lambda **kw:words,find_tables=lambda **kw:[SimpleNamespace(rows=[SimpleNamespace(cells=boxes)])])
    class Document:
        pages=[page]
        def __enter__(self): return self
        def __exit__(self,*args): pass
    monkeypatch.setattr(recovery.importlib,"import_module",lambda name:SimpleNamespace(open=lambda path:Document()))
    rows,audit,_=recovery.pdfplumber_rows("fake.pdf")
    assert [r["category"] for r in rows] == ["2WN", "LMV"]
    assert rows[0]["values"]["2025"] == 6
    assert rows[0]["district"] == "Alpha" and len(audit) == 10
    assert "merged district label" in audit[0]["row_detection"]
    assert "page-edge" in audit[1]["row_detection"]


def test_extra_category_is_allowed_only_when_pdf_explicitly_zero():
    baseline, expected = base()
    rows=[row("Alpha","2WN",3),row("","LMV",4),row("","OTH",0)]
    result,_=recovery.reconcile(rows,baseline,expected)
    assert result.ev_total.iloc[0] == 7
    rows[-1]=row("","OTH",1)
    with pytest.raises(ValueError,match="Unexpected nonzero"):
        recovery.reconcile(rows,baseline,expected)
    rows[-1]=row("","OTH",None)
    with pytest.raises(ValueError,match="ambiguous"):
        recovery.reconcile(rows,baseline,expected)


def test_page_edge_continuation_keeps_previous_district_blank(monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_EV_PDF_FIRST_TABLE_PAGE", 1)
    first=[None,(20,20,40,40),(40,20,60,40),(60,20,80,40),(80,20,100,40)]
    second=[(0,40,20,60),(20,40,40,60),(40,40,60,60),(60,40,80,60),(80,40,100,60)]
    words=[]
    for top,items in [(5,[("MPV",21),("0",41),("0",61),("0",81)]),
                      (25,[("OTH",21),("0",41),("0",61),("0",81)]),
                      (45,[("Beta",1),("2WIC",21),("0",41),("0",61),("0",81)])]:
        words.extend(dict(word(text,x),top=top,bottom=top+10) for text,x in items)
    page=SimpleNamespace(extract_words=lambda **kw:words,find_tables=lambda **kw:[SimpleNamespace(rows=[SimpleNamespace(cells=first),SimpleNamespace(cells=second)])])
    class Document:
        pages=[page]
        def __enter__(self): return self
        def __exit__(self,*args): pass
    monkeypatch.setattr(recovery.importlib,"import_module",lambda name:SimpleNamespace(open=lambda path:Document()))
    rows,_,_=recovery.pdfplumber_rows("fake.pdf")
    assert [row["district"] for row in rows] == ["", "", "Beta"]
    assert [row["category"] for row in rows] == ["MPV", "OTH", "2WIC"]
