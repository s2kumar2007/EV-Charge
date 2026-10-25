"""
Offline tests for ranking, port parsing, and gap score units (no internet needed).
Run:  python tests/test_scores.py
Uses small in-memory datasets to verify:
  (a) rank is an integer and empty when no EV data
  (b) ports default to 1 when the tag is missing or invalid ("abc", "0", "-2")
  (c) GAP_UNIT = "ports" changes the score as expected
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import build_scores     # noqa: E402
import config           # noqa: E402
from fetch_chargers import parse_ports  # noqa: E402


def test_integer_rank():
    """Test (a): rank is an integer and empty for districts without EV data."""
    # Fake in-memory district data with EV counts and chargers
    fake_df = pd.DataFrame([
        {"district": "DistA", "ev_total": 500, "charger_count": 5, "port_count": 10},
        {"district": "DistB", "ev_total": 200, "charger_count": 1, "port_count": 2},
        {"district": "DistC", "ev_total": np.nan, "charger_count": 3, "port_count": 6},  # no EV data
    ])
    ranked = build_scores.rank_districts(fake_df)

    # Check rank dtype is nullable integer Int64
    assert str(ranked["rank"].dtype) == "Int64", f"Expected Int64 dtype, got {ranked['rank'].dtype}"

    # Districts with EV data must have integer ranks
    a_rank = ranked.loc[ranked["district"] == "DistA", "rank"].iloc[0]
    b_rank = ranked.loc[ranked["district"] == "DistB", "rank"].iloc[0]
    c_rank = ranked.loc[ranked["district"] == "DistC", "rank"].iloc[0]

    assert pd.notna(a_rank) and int(a_rank) == a_rank, f"DistA rank invalid: {a_rank}"
    assert pd.notna(b_rank) and int(b_rank) == b_rank, f"DistB rank invalid: {b_rank}"
    assert pd.isna(c_rank), f"DistC (no EV data) should have empty rank, got {c_rank}"

    # Verify CSV representation prints integer (e.g. '1', not '1.0') and empty for missing
    csv_text = ranked.to_csv(index=False)
    lines = csv_text.strip().splitlines()
    header = lines[0].split(",")
    rank_idx = header.index("rank")
    row_ranks = [line.split(",")[rank_idx] for line in lines[1:]]

    for r in row_ranks:
        assert "." not in r, f"Rank printed with decimal in CSV: {r}"
    assert "" in row_ranks, "Missing rank should print as empty string in CSV"
    print("PASS  (a) rank is an integer and empty when no EV data")


def test_ports_default():
    """Test (b): ports default to 1 when the tag is missing or invalid."""
    # Invalid or missing tags should return 1 port and ports_known = False
    invalid_cases = [None, "", "   ", "abc", "0", "-2", 0, -2, np.nan]
    for val in invalid_cases:
        ports, known = parse_ports(val)
        assert ports == 1, f"Expected 1 for {val!r}, got {ports}"
        assert known is False, f"Expected known=False for {val!r}, got {known}"

    # Valid positive integers should return the integer and ports_known = True
    valid_cases = [("1", 1), ("2", 2), ("10", 10), (4, 4), (6.0, 6)]
    for val, expected in valid_cases:
        ports, known = parse_ports(val)
        assert ports == expected, f"Expected {expected} for {val!r}, got {ports}"
        assert known is True, f"Expected known=True for {val!r}, got {known}"
    print("PASS  (b) ports default to 1 when the tag is missing or invalid ('abc', '0', '-2')")


def test_gap_unit_setting():
    """Test (c): GAP_UNIT = 'ports' changes the score as expected."""
    # Dist1: 100 EVs, 1 station with 10 ports -> score = 100/1 = 100 (stations), 100/10 = 10 (ports)
    # Dist2: 100 EVs, 2 stations with 2 ports -> score = 100/2 = 50 (stations), 100/2 = 50 (ports)
    fake_df = pd.DataFrame([
        {"district": "Dist1", "ev_total": 100, "charger_count": 1, "port_count": 10},
        {"district": "Dist2", "ev_total": 100, "charger_count": 2, "port_count": 2},
    ])

    # 1. With GAP_UNIT = "stations"
    config.GAP_UNIT = "stations"
    ranked_stations = build_scores.rank_districts(fake_df)
    s1 = ranked_stations.loc[ranked_stations["district"] == "Dist1", "gap_score"].iloc[0]
    s2 = ranked_stations.loc[ranked_stations["district"] == "Dist2", "gap_score"].iloc[0]
    assert s1 == 100.0, f"Expected score 100.0 for Dist1 with stations, got {s1}"
    assert s2 == 50.0, f"Expected score 50.0 for Dist2 with stations, got {s2}"
    assert ranked_stations.iloc[0]["district"] == "Dist1", "Dist1 should be rank 1 under stations"

    # 2. With GAP_UNIT = "ports"
    config.GAP_UNIT = "ports"
    ranked_ports = build_scores.rank_districts(fake_df)
    p1 = ranked_ports.loc[ranked_ports["district"] == "Dist1", "gap_score"].iloc[0]
    p2 = ranked_ports.loc[ranked_ports["district"] == "Dist2", "gap_score"].iloc[0]
    assert p1 == 10.0, f"Expected score 10.0 for Dist1 with ports, got {p1}"
    assert p2 == 50.0, f"Expected score 50.0 for Dist2 with ports, got {p2}"
    assert ranked_ports.iloc[0]["district"] == "Dist2", "Dist2 should be rank 1 under ports"

    # Restore default
    config.GAP_UNIT = "stations"
    print("PASS  (c) GAP_UNIT = 'ports' changes the score as expected")


if __name__ == "__main__":
    failed = 0
    for test in [test_integer_rank, test_ports_default, test_gap_unit_setting]:
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
