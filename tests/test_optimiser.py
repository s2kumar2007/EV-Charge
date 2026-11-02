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


def test_generate_candidate_sites_extracts_corridor_and_hotspots():
    """Verify candidate generation extracts highway gap waypoints and urban hotspots with grid unconstrained."""
    corridor_gaps = pd.DataFrame([
        {"corridor_id": "NH-48", "start_distance_m": 0, "end_distance_m": 45000, "spacing_km": 45.0, "flagged": True, "longitude": 79.5, "latitude": 12.8}
    ])
    hotspots = pd.DataFrame([
        {"district": "Vellore", "district_key": "vellore", "hotspot_type": "Hot Spot", "latitude": 12.9, "longitude": 79.1}
    ])
    requirements = pd.DataFrame([
        {"district_key": "vellore", "ports_deficit": 12}
    ])

    cands = generate_candidate_sites(corridor_gaps, hotspots, requirements)
    assert len(cands) == 2

    corr_cand = next(c for c in cands if c["site_type"] == "highway_corridor")
    assert corr_cand["corridor_id"] == "NH-48"
    assert "grid unconstrained" in corr_cand["drivers"].lower()
    assert corr_cand["data_flag"] == "candidate"

    urban_cand = next(c for c in cands if c["site_type"] == "urban_hotspot")
    assert "vellore" in urban_cand["site_id"].lower()
    assert urban_cand["data_flag"] == "candidate"


def test_max_coverage_respects_real_grid_constraint():
    """Verify MILP omits candidate when real substation grid capacity is insufficient."""
    demand = [
        {"id": "A", "weight": 100.0, "x": 0.0, "y": 0.0},
        {"id": "B", "weight": 50.0, "x": 10.0, "y": 0.0},
    ]
    candidates = [
        {"site_id": "SITE-1", "name": "Site 1", "x": 0.0, "y": 0.0},
        {"site_id": "SITE-3", "name": "Site 3", "x": 5.0, "y": 0.0},
    ]
    # Site 3 requires 1.0 MW, but real grid capacity is only 0.2 MW
    grid_caps = {"SITE-3": 0.2}
    sol = solve_max_coverage_milp(demand, candidates, site_budget=1, coverage_radius_km=7.0, grid_capacity_mw=grid_caps, power_demand_per_site_mw=1.0)
    assert sol["status"] == "optimal"
    # Site 3 blocked due to real grid constraint; Site 1 must be picked instead
    assert [s["site_id"] for s in sol["selected_sites"]] == ["SITE-1"]


def test_solve_corridor_frlm_allocates_sites_by_flow():
    """Verify corridor FRLM prioritizes high-flow highways (NH over SH) and divides gaps."""
    corridor_gaps = pd.DataFrame([
        {
            "corridor_id": "NH-48",
            "corridor_name": "Chennai-Bengaluru",
            "spacing_km": 60.0,
            "start_distance_m": 0,
            "end_distance_m": 60000,
            "flagged": True,
            "start_lon": 80.0,
            "start_lat": 13.0,
            "end_lon": 79.5,
            "end_lat": 12.9,
        },
        {
            "corridor_id": "SH-10",
            "corridor_name": "State Highway 10",
            "spacing_km": 30.0,
            "start_distance_m": 0,
            "end_distance_m": 30000,
            "flagged": True,
            "start_lon": 79.0,
            "start_lat": 12.5,
            "end_lon": 79.2,
            "end_lat": 12.6,
        },
    ])

    rec = solve_corridor_frlm(corridor_gaps, site_budget=2, max_spacing_km=20.0)
    assert len(rec) == 2
    # NH-48 has higher flow score (60 * 1.5 = 90 vs 30 * 1.0 = 30)
    assert (rec["corridor_id"] == "NH-48").all()
    assert (rec["ports_recommended"] == 4).all()
    assert rec["data_flag"].iloc[0] == "recommended"
