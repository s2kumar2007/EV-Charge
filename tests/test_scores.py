"""
Offline tests for ranking, port parsing, gap score units, and synthetic data flags (no internet needed).
Run:  python tests/test_scores.py
Uses small in-memory datasets to verify:
  (a) rank is an integer and empty when no EV data
  (b) ports default to 1 when the tag is missing or invalid ("abc", "0", "-2")
  (c) GAP_UNIT = "ports" changes the score as expected
  (d) a row with data_flag "synthetic" gives data_flag "synthetic" in the output table
  (e) rows without a data_flag column give "real"
  (f) a district with one real and one synthetic row becomes "synthetic"
  (g) with USE_SYNTHETIC_TEST_DATA = False and no real file, the synthetic test file is NOT loaded
"""
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import build_scores     # noqa: E402
import config           # noqa: E402
from fetch_chargers import parse_ports  # noqa: E402
import load_vahan       # noqa: E402


def test_integer_rank():
    """Test: rank is an integer and empty for districts without EV data."""
    fake_df = pd.DataFrame([
        {"district": "DistA", "ev_total": 500, "charger_count": 5, "port_count": 10},
        {"district": "DistB", "ev_total": 200, "charger_count": 1, "port_count": 2},
        {"district": "DistC", "ev_total": np.nan, "charger_count": 3, "port_count": 6},  # no EV data
    ])
    ranked = build_scores.rank_districts(fake_df)

    assert str(ranked["rank"].dtype) == "Int64", f"Expected Int64 dtype, got {ranked['rank'].dtype}"

    a_rank = ranked.loc[ranked["district"] == "DistA", "rank"].iloc[0]
    b_rank = ranked.loc[ranked["district"] == "DistB", "rank"].iloc[0]
    c_rank = ranked.loc[ranked["district"] == "DistC", "rank"].iloc[0]

    assert pd.notna(a_rank) and int(a_rank) == a_rank, f"DistA rank invalid: {a_rank}"
    assert pd.notna(b_rank) and int(b_rank) == b_rank, f"DistB rank invalid: {b_rank}"
    assert pd.isna(c_rank), f"DistC (no EV data) should have empty rank, got {c_rank}"

    csv_text = ranked.to_csv(index=False)
    lines = csv_text.strip().splitlines()
    header = lines[0].split(",")
    rank_idx = header.index("rank")
    row_ranks = [line.split(",")[rank_idx] for line in lines[1:]]

    for r in row_ranks:
        assert "." not in r, f"Rank printed with decimal in CSV: {r}"
    assert "" in row_ranks, "Missing rank should print as empty string in CSV"
    print("PASS  rank is an integer and empty when no EV data")


def test_ports_default():
    """Test: ports default to 1 when the tag is missing or invalid."""
    invalid_cases = [None, "", "   ", "abc", "0", "-2", 0, -2, np.nan]
    for val in invalid_cases:
        ports, known = parse_ports(val)
        assert ports == 1, f"Expected 1 for {val!r}, got {ports}"
        assert known is False, f"Expected known=False for {val!r}, got {known}"

    valid_cases = [("1", 1), ("2", 2), ("10", 10), (4, 4), (6.0, 6)]
    for val, expected in valid_cases:
        ports, known = parse_ports(val)
        assert ports == expected, f"Expected {expected} for {val!r}, got {ports}"
        assert known is True, f"Expected known=True for {val!r}, got {known}"
    print("PASS  ports default to 1 when the tag is missing or invalid ('abc', '0', '-2')")


def test_gap_unit_setting():
    """Test: GAP_UNIT = 'ports' changes the score as expected."""
    fake_df = pd.DataFrame([
        {"district": "Dist1", "ev_total": 100, "charger_count": 1, "port_count": 10},
        {"district": "Dist2", "ev_total": 100, "charger_count": 2, "port_count": 2},
    ])

    config.GAP_UNIT = "stations"
    ranked_stations = build_scores.rank_districts(fake_df)
    s1 = ranked_stations.loc[ranked_stations["district"] == "Dist1", "gap_score"].iloc[0]
    s2 = ranked_stations.loc[ranked_stations["district"] == "Dist2", "gap_score"].iloc[0]
    assert s1 == 100.0, f"Expected score 100.0 for Dist1 with stations, got {s1}"
    assert s2 == 50.0, f"Expected score 50.0 for Dist2 with stations, got {s2}"
    assert ranked_stations.iloc[0]["district"] == "Dist1", "Dist1 should be rank 1 under stations"

    config.GAP_UNIT = "ports"
    ranked_ports = build_scores.rank_districts(fake_df)
    p1 = ranked_ports.loc[ranked_ports["district"] == "Dist1", "gap_score"].iloc[0]
    p2 = ranked_ports.loc[ranked_ports["district"] == "Dist2", "gap_score"].iloc[0]
    assert p1 == 10.0, f"Expected score 10.0 for Dist1 with ports, got {p1}"
    assert p2 == 50.0, f"Expected score 50.0 for Dist2 with ports, got {p2}"
    assert ranked_ports.iloc[0]["district"] == "Dist2", "Dist2 should be rank 1 under ports"

    config.GAP_UNIT = "stations"
    print("PASS  GAP_UNIT = 'ports' changes the score as expected")


def test_data_flag_synthetic():
    """Test (a): a row with data_flag 'synthetic' gives data_flag 'synthetic' in the output table."""
    fake_boundaries = pd.DataFrame([{"district": "Test", "district_key": "test", "geometry": None}])
    fake_df = pd.DataFrame([{"district": "Test", "ev_total": 100, "data_flag": "synthetic"}])

    orig_reader = load_vahan.read_vahan_file
    try:
        load_vahan.read_vahan_file = lambda: (fake_df, "district")
        table, _ = load_vahan.load_vahan(fake_boundaries)
        flag = table.loc[table["district_key"] == "test", "data_flag"].iloc[0]
        assert flag == "synthetic", f"Expected 'synthetic', got {flag!r}"
        print("PASS  (a) a row with data_flag 'synthetic' gives data_flag 'synthetic'")
    finally:
        load_vahan.read_vahan_file = orig_reader


def test_data_flag_missing_column():
    """Test (b): rows without a data_flag column give 'real'."""
    fake_boundaries = pd.DataFrame([{"district": "Test", "district_key": "test", "geometry": None}])
    fake_df = pd.DataFrame([{"district": "Test", "ev_total": 100}])  # no data_flag column

    orig_reader = load_vahan.read_vahan_file
    try:
        load_vahan.read_vahan_file = lambda: (fake_df, "district")
        table, _ = load_vahan.load_vahan(fake_boundaries)
        flag = table.loc[table["district_key"] == "test", "data_flag"].iloc[0]
        assert flag == "real", f"Expected 'real', got {flag!r}"
        print("PASS  (b) rows without a data_flag column give 'real'")
    finally:
        load_vahan.read_vahan_file = orig_reader


def test_data_flag_mixed_rows():
    """Test (c): a district with one real and one synthetic row becomes 'synthetic'."""
    fake_boundaries = pd.DataFrame([{"district": "Test", "district_key": "test", "geometry": None}])
    fake_df = pd.DataFrame([
        {"district": "Test", "ev_total": 50, "data_flag": "real"},
        {"district": "Test", "ev_total": 50, "data_flag": "synthetic"},
    ])

    orig_reader = load_vahan.read_vahan_file
    try:
        load_vahan.read_vahan_file = lambda: (fake_df, "district")
        table, _ = load_vahan.load_vahan(fake_boundaries)
        flag = table.loc[table["district_key"] == "test", "data_flag"].iloc[0]
        assert flag == "synthetic", f"Expected 'synthetic', got {flag!r}"
        print("PASS  (c) a district with one real and one synthetic row becomes 'synthetic'")
    finally:
        load_vahan.read_vahan_file = orig_reader


def test_synthetic_test_data_gating():
    """Test (d): with USE_SYNTHETIC_TEST_DATA = False and no real file, the synthetic test file is NOT loaded."""
    # File existence is invented too; the test never depends on a real sample.
    exists_patch = patch.object(Path, "exists", lambda path: path.name == load_vahan.SYNTHETIC_TEST_FILE.name)
    exists_patch.start()
    orig_setting = getattr(config, "USE_SYNTHETIC_TEST_DATA", False)
    orig_raw_file = load_vahan.RAW_VAHAN_FILE
    orig_sample = getattr(config, "VAHAN_SAMPLE_FILE", "")
    try:
        config.USE_SYNTHETIC_TEST_DATA = False
        load_vahan.RAW_VAHAN_FILE = Path("non_existent_raw_file_for_test.csv")
        config.VAHAN_SAMPLE_FILE = "non_existent_sample_file_for_test.csv"

        source_path, _, is_syn = load_vahan.get_vahan_source()
        assert source_path is None, f"Expected None when USE_SYNTHETIC_TEST_DATA is False, got {source_path}"
        assert is_syn is False

        # When set to True, the synthetic test file should be loaded
        config.USE_SYNTHETIC_TEST_DATA = True
        source_path, _, is_syn = load_vahan.get_vahan_source()
        assert source_path is not None and "SYNTHETIC_TEST" in source_path.name
        assert is_syn is True
        print("PASS  (d) with USE_SYNTHETIC_TEST_DATA = False and no real file, the synthetic test file is NOT loaded")
    finally:
        exists_patch.stop()
        config.USE_SYNTHETIC_TEST_DATA = orig_setting
        config.VAHAN_SAMPLE_FILE = orig_sample
        load_vahan.RAW_VAHAN_FILE = orig_raw_file


if __name__ == "__main__":
    tests = [
        test_integer_rank,
        test_ports_default,
        test_gap_unit_setting,
        test_data_flag_synthetic,
        test_data_flag_missing_column,
        test_data_flag_mixed_rows,
        test_synthetic_test_data_gating,
    ]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as err:
            print(f"FAIL  {test.__name__}: {err}")
            failed += 1
        except Exception as err:
            print(f"ERROR {test.__name__}: {err}")
            failed += 1

    print("\nAll passed." if not failed else f"\n{failed} FAILED.")
    sys.exit(1 if failed else 0)
