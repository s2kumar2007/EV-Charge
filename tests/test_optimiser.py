"""
Tests for site optimization, MILP maximum coverage, and candidate generation.
All tests use tiny synthetic in-memory instances with known closed-form solutions.
"""
import pytest
import numpy as np
import pandas as pd

from site_optimiser import (
    solve_max_coverage_milp,
    generate_candidate_sites,
    solve_corridor_frlm,
    rank_and_export_sites,
)


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(optimiser)")
def test_max_coverage_milp_known_optimal():
    """Verify MILP solver recovers the unique mathematically optimal site on a tiny instance."""
    # 3 demand points: A (weight 100), B (weight 50), C (weight 20)
    demand = [
        {"id": "A", "weight": 100.0, "x": 0.0, "y": 0.0},
        {"id": "B", "weight": 50.0, "x": 10.0, "y": 0.0},
        {"id": "C", "weight": 20.0, "x": 25.0, "y": 0.0},
    ]

    # 3 candidate sites:
    # Site 1 covers {A} (radius 6 km)
    # Site 2 covers {B, C} (distance to B: 5 km, C: 5 km)
    # Site 3 covers {A, B} (distance to A: 5 km, B: 5 km) -> weight 150
    candidates = [
        {"site_id": "SITE-1", "name": "Site 1", "x": 0.0, "y": 0.0},
        {"site_id": "SITE-2", "name": "Site 2", "x": 20.0, "y": 0.0},
        {"site_id": "SITE-3", "name": "Site 3", "x": 5.0, "y": 0.0},
    ]

    # With budget = 1, Site 3 is strictly optimal (covers 150 vs 100 or 70)
    sol1 = solve_max_coverage_milp(demand, candidates, site_budget=1, coverage_radius_km=7.0)
    assert sol1["status"] == "optimal"
    assert sol1["total_covered_weight"] == 150.0
    selected_ids1 = [s["site_id"] for s in sol1["selected_sites"]]
    assert selected_ids1 == ["SITE-3"]

    # With budget = 2, Sites 2 and 3 cover all {A, B, C} (total weight 170.0)
    sol2 = solve_max_coverage_milp(demand, candidates, site_budget=2, coverage_radius_km=7.0)
    assert sol2["status"] == "optimal"
    assert sol2["total_covered_weight"] == 170.0
    selected_ids2 = set(s["site_id"] for s in sol2["selected_sites"])
    assert selected_ids2 == {"SITE-2", "SITE-3"}
