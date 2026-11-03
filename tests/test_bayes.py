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


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(bayes)")
def test_build_bayesian_network():
    """Verify build_bayesian_network loads network from priors and passes pgmpy check_model."""
    from bayes_layer import build_bayesian_network
    model = build_bayesian_network(PRIORS_FILE)
    assert model.check_model(), "pgmpy model check failed"
    nodes = set(model.nodes())
    assert "Demand_ports" in nodes
    assert "Requirement_class" in nodes
    assert "Gap_class" in nodes


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(bayes)")
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


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(bayes)")
def test_missing_evidence_widens_posterior():
    """Verify marginalizing over missing evidence increases entropy / widens credible interval."""
    from bayes_layer import build_bayesian_network, infer_district_posteriors
    model = build_bayesian_network(PRIORS_FILE)

    # Full evidence on core drivers
    full_evidence = {
        "Urbanisation": "high",
        "EV_growth": "high",
        "Traffic_exposure": "high",
        "OSM_completeness": "good",
        "Grid_headroom": "high"
    }
    full_res = infer_district_posteriors(model, evidence=full_evidence)

    # Missing EV_growth (unobserved district)
    partial_evidence = {
        "Urbanisation": "high",
        "Traffic_exposure": "high",
        "OSM_completeness": "good",
        "Grid_headroom": "high"
    }
    partial_res = infer_district_posteriors(model, evidence=partial_evidence)

    # Shannon entropy of Requirement_class distribution
    def entropy(dist):
        return -sum(p * math.log(p + 1e-12) for p in dist.values() if p > 0)

    h_full = entropy(full_res["Requirement_class"])
    h_partial = entropy(partial_res["Requirement_class"])
    assert h_partial > h_full, f"Missing evidence should increase entropy: {h_partial} vs {h_full}"
