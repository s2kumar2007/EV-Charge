"""
Offline unit tests for Bayesian Uncertainty Layer (src/bayes_layer.py).
Verifies prior YAML validity, model check, evidence directionality, and missing evidence uncertainty widening.
"""
import math
import sys
from pathlib import Path
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
PRIORS_FILE = ROOT / "config" / "bn_priors.yaml"


def test_bn_priors_yaml_validity():
    """Verify bn_priors.yaml exists, has required nodes, and all CPD columns sum to 1."""
    assert PRIORS_FILE.exists(), "config/bn_priors.yaml must exist"
    with open(PRIORS_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    nodes = data.get("nodes", {})
    expected_nodes = [
        "Urbanisation", "EV_growth", "Traffic_exposure", "OSM_completeness",
        "Grid_headroom", "Charging_behaviour", "True_charger_supply",
        "Demand_ports", "Requirement_class", "Gap_class"
    ]
    for n in expected_nodes:
        assert n in nodes, f"Missing node in YAML: {n}"
        node_cfg = nodes[n]
        assert "states" in node_cfg
        assert "parents" in node_cfg
        assert "rationale" in node_cfg
        assert "source" in node_cfg
        cpt = node_cfg["cpt"]
        if not node_cfg["parents"]:
            assert isinstance(cpt, list)
            assert math.isclose(sum(cpt), 1.0, abs_tol=1e-4)
        else:
            assert isinstance(cpt, dict)
            for cond, probs in cpt.items():
                assert math.isclose(sum(probs), 1.0, abs_tol=1e-4), f"{n} {cond} sum={sum(probs)}"


def test_build_bayesian_network():
    """Verify build_bayesian_network loads network from priors and passes pgmpy check_model."""
    from bayes_layer import build_bayesian_network
    model = build_bayesian_network(PRIORS_FILE)
    assert model.check_model(), "pgmpy model check failed"
    nodes = set(model.nodes())
    assert "Demand_ports" in nodes
    assert "Requirement_class" in nodes
    assert "Gap_class" in nodes


def test_evidence_directionality():
    """Verify evidence shifts the posterior in the expected causal direction."""
    from bayes_layer import build_bayesian_network, infer_district_posteriors
    model = build_bayesian_network(PRIORS_FILE)

    # Baseline prior (no evidence)
    prior_res = infer_district_posteriors(model, evidence={})
    p_severe_prior = prior_res["Requirement_class"]["tier_4_severe"]

    # High growth & high traffic & public charging -> should increase severe requirement
    high_evidence = {
        "EV_growth": "high",
        "Charging_behaviour": "public_dominant",
        "Traffic_exposure": "high",
        "True_charger_supply": "low"
    }
    high_res = infer_district_posteriors(model, evidence=high_evidence)
    p_severe_high = high_res["Requirement_class"]["tier_4_severe"]
    assert p_severe_high > p_severe_prior, f"Expected {p_severe_high} > {p_severe_prior}"

    # Low growth & home dominant & high supply -> should decrease severe requirement
    low_evidence = {
        "EV_growth": "low",
        "Charging_behaviour": "home_dominant",
        "Traffic_exposure": "low",
        "True_charger_supply": "high"
    }
    low_res = infer_district_posteriors(model, evidence=low_evidence)
    p_severe_low = low_res["Requirement_class"]["tier_4_severe"]
    assert p_severe_low < p_severe_prior, f"Expected {p_severe_low} < {p_severe_prior}"


def test_missing_evidence_widens_posterior():
    """Verify marginalizing over missing evidence increases entropy / widens uncertainty."""
    from bayes_layer import build_bayesian_network, infer_district_posteriors
    model = build_bayesian_network(PRIORS_FILE)

    # Known low demand district with observed low growth
    full_evidence = {
        "Urbanisation": "low",
        "EV_growth": "low",
        "Traffic_exposure": "low",
        "OSM_completeness": "good",
    }
    full_res = infer_district_posteriors(model, evidence=full_evidence)

    # Same district when EV_growth is unobserved (missing VAHAN count)
    partial_evidence = {
        "Urbanisation": "low",
        "Traffic_exposure": "low",
        "OSM_completeness": "good",
    }
    partial_res = infer_district_posteriors(model, evidence=partial_evidence)

    # Shannon entropy of Requirement_class distribution
    def entropy(dist):
        return -sum(p * math.log(p + 1e-12) for p in dist.values() if p > 0)

    h_full = entropy(full_res["Requirement_class"])
    h_partial = entropy(partial_res["Requirement_class"])
    assert h_partial > h_full, f"Missing evidence should increase entropy: {h_partial:.3f} vs {h_full:.3f}"


def test_discretise_district_row_complete():
    """Verify discretiser maps continuous indicators to valid discrete node states."""
    import pandas as pd
    from bayes_layer import discretise_district_row

    cache = {
        "urbanisation": (1.0, 5.0),
        "traffic": (0.5, 1.5),
        "ev": (500, 2000),
    }

    # High urban, high traffic, high EV, high confidence
    row_high = pd.Series({
        "district_key": "chennai",
        "commercial_per_km2": 10.0,
        "road_km_per_km2": 2.5,
        "ev_total": 5000,
        "confidence": 0.85,
        "status": "ok",
        "data_flag": "real",
    })
    ev_high = discretise_district_row(row_high, quantiles_cache=cache)
    assert ev_high["Urbanisation"] == "high"
    assert ev_high["Traffic_exposure"] == "high"
    assert ev_high["EV_growth"] == "high"
    assert ev_high["OSM_completeness"] == "good"
    assert ev_high["Grid_headroom"] == "unknown"


def test_discretise_district_row_missing_and_synthetic():
    """Verify missing EV data or synthetic flag results in unobserved EV_growth (marginalized)."""
    import pandas as pd
    from bayes_layer import discretise_district_row

    cache = {
        "urbanisation": (1.0, 5.0),
        "traffic": (0.5, 1.5),
        "ev": (500, 2000),
    }

    # Missing EV data
    row_no_ev = pd.Series({
        "district_key": "rural_dist",
        "commercial_per_km2": 0.2,
        "road_km_per_km2": 0.3,
        "ev_total": float("nan"),
        "confidence": 0.40,
        "status": "no_data",
        "data_flag": "real",
    })
    ev_no_ev = discretise_district_row(row_no_ev, quantiles_cache=cache)
    assert "EV_growth" not in ev_no_ev or ev_no_ev["EV_growth"] is None
    assert ev_no_ev["Urbanisation"] == "low"
    assert ev_no_ev["Traffic_exposure"] == "low"
    assert ev_no_ev["OSM_completeness"] == "poor"

    # Synthetic EV row should NOT be treated as observed real EV growth
    row_synth = pd.Series({
        "district_key": "synth_dist",
        "commercial_per_km2": 2.0,
        "road_km_per_km2": 1.0,
        "ev_total": 1200,
        "confidence": 0.60,
        "status": "ok",
        "data_flag": "synthetic",
    })
    ev_synth = discretise_district_row(row_synth, quantiles_cache=cache)
    assert "EV_growth" not in ev_synth or ev_synth["EV_growth"] is None
    assert ev_synth["OSM_completeness"] == "fair"


def test_compute_credible_interval():
    """Verify conversion of requirement class probabilities to P10, P50, P90 port counts."""
    from bayes_layer import compute_credible_interval

    # Low requirement case
    dist_low = {"tier_1_low": 1.0, "tier_2_med": 0.0, "tier_3_high": 0.0, "tier_4_severe": 0.0}
    p10, p50, p90 = compute_credible_interval(dist_low, credibility=0.80)
    assert 0 <= p10 <= p50 <= p90 <= 50
    assert p50 == 25

    # Severe requirement case
    dist_severe = {"tier_1_low": 0.0, "tier_2_med": 0.0, "tier_3_high": 0.0, "tier_4_severe": 1.0}
    p10_s, p50_s, p90_s = compute_credible_interval(dist_severe, credibility=0.80)
    assert 500 <= p10_s <= p50_s <= p90_s <= 1200

    # Diffuse / uncertain distribution has wider interval than sharp distribution
    dist_diffuse = {"tier_1_low": 0.25, "tier_2_med": 0.25, "tier_3_high": 0.25, "tier_4_severe": 0.25}
    p10_d, p50_d, p90_d = compute_credible_interval(dist_diffuse, credibility=0.80)
    ci_diffuse = p90_d - p10_d
    ci_low = p90 - p10
    assert ci_diffuse > ci_low


def test_infer_district_full():
    """Verify end-to-end per-district inference produces requirement ranges and gap posterior."""
    import pandas as pd
    from bayes_layer import build_bayesian_network, infer_district_full

    model = build_bayesian_network(PRIORS_FILE)
    row = pd.Series({
        "district_key": "chennai",
        "commercial_per_km2": 15.0,
        "road_km_per_km2": 3.0,
        "ev_total": 8000,
        "confidence": 0.85,
        "status": "ok",
        "data_flag": "real",
    })
    res = infer_district_full(model, row)
    assert "p10" in res and "p50" in res and "p90" in res
    assert "ci_width" in res
    assert "gap_posterior" in res
    assert "Requirement_class" in res["posteriors"]
    assert res["p10"] <= res["p50"] <= res["p90"]


