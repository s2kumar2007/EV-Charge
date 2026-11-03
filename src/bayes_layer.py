"""
Bayesian Uncertainty Layer for ChargeGap India.

Provides discrete Bayesian network inference, marginalization over missing evidence,
credible intervals, and driver attribution.

Inputs:
  - config/bn_priors.yaml: Expert prior probability distributions
  - Phase 1 district outputs (gap scores, indicator quantiles, confidence)
Outputs:
  - outputs/bayes_district_posteriors.csv: Posterior requirement/gap class distributions,
    80% credible intervals, and driver attributions
Assumptions:
  - All priors are explicitly documented expert assumptions (CEA/NITI Aayog/MoP/BEE).
  - Missing evidence is marginalized out, never imputed with invented values.
"""
import itertools
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import yaml

# pgmpy version shim
try:
    from pgmpy.models import DiscreteBayesianNetwork as BayesianNetworkModel
except ImportError:
    from pgmpy.models import BayesianNetwork as BayesianNetworkModel

from pgmpy.factors.discrete import TabularCPD
from pgmpy.inference import VariableElimination


def build_bayesian_network(priors_path: Union[str, Path]) -> BayesianNetworkModel:
    """
    Build and validate a discrete Bayesian network from a YAML priors specification.
    
    Reads DAG nodes, states, parents, and conditional probability tables, constructs
    TabularCPDs for all nodes, and validates the model structure via check_model().
    """
    priors_file = Path(priors_path)
    if not priors_file.exists():
        raise FileNotFoundError(f"Prior configuration file not found at: {priors_file}")

    with open(priors_file, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    nodes = cfg.get("nodes", {})
    if not nodes:
        raise ValueError(f"No nodes defined in prior configuration: {priors_file}")

    # Build directed edges
    edges = [(p, n) for n, n_cfg in nodes.items() for p in n_cfg.get("parents", [])]
    model = BayesianNetworkModel(edges)
    model.add_nodes_from(list(nodes.keys()))

    cpds: List[TabularCPD] = []
    for name, n_cfg in nodes.items():
        states = n_cfg["states"]
        parents = n_cfg.get("parents", [])
        cpt = n_cfg["cpt"]
        state_names = {name: states, **{p: nodes[p]["states"] for p in parents}}

        if not parents:
            # Root node prior distribution
            values = [[float(p)] for p in cpt]
            cpd = TabularCPD(
                variable=name,
                variable_card=len(states),
                values=values,
                state_names=state_names,
            )
        else:
            # Conditioned node: construct column matrix from Cartesian product of parent states
            cols: List[List[float]] = []
            for combo in itertools.product(*(nodes[p]["states"] for p in parents)):
                key = ",".join(f"{p}={val}" for p, val in zip(parents, combo))
                if key not in cpt:
                    raise KeyError(f"Missing parent condition '{key}' in CPT for node '{name}'")
                cols.append([float(x) for x in cpt[key]])

            # Transpose to shape (len(states), num_parent_combinations)
            values = [[cols[c][s] for c in range(len(cols))] for s in range(len(states))]
            evidence_card = [len(nodes[p]["states"]) for p in parents]
            cpd = TabularCPD(
                variable=name,
                variable_card=len(states),
                values=values,
                evidence=parents,
                evidence_card=evidence_card,
                state_names=state_names,
            )
        cpds.append(cpd)

    model.add_cpds(*cpds)
    if not model.check_model():
        raise ValueError("Bayesian network model check failed; verify CPD dimensions and probabilities.")

    return model


def infer_district_posteriors(
    model: BayesianNetworkModel,
    evidence: Optional[Dict[str, str]] = None,
    target_nodes: Optional[List[str]] = None,
) -> Dict[str, Dict[str, float]]:
    """
    Perform exact inference using Variable Elimination given observed district evidence.
    
    Missing evidence is automatically marginalized over, widening the posterior rather
    than imputing unobserved states.
    """
    if evidence is None:
        evidence = {}
    if target_nodes is None:
        target_nodes = ["Requirement_class", "Gap_class"]

    # Filter evidence to valid model nodes and observed non-null states
    model_nodes = set(model.nodes())
    valid_evidence = {k: v for k, v in evidence.items() if k in model_nodes and v is not None}

    infer = VariableElimination(model)
    results: Dict[str, Dict[str, float]] = {}

    for target in target_nodes:
        if target in valid_evidence:
            # If target node itself is observed, posterior is degenerate (1.0 on observed state)
            obs_state = valid_evidence[target]
            cpd = model.get_cpds(target)
            results[target] = {s: (1.0 if s == obs_state else 0.0) for s in cpd.state_names[target]}
        else:
            q = infer.query([target], evidence=valid_evidence, show_progress=False)
            results[target] = {state: float(val) for state, val in zip(q.state_names[target], q.values)}

    return results


def compute_indicator_quantiles(df: pd.DataFrame) -> Dict[str, Tuple[float, float]]:
    """
    Compute state-level tertile cutoffs (33.3% and 66.7%) for continuous district indicators.
    
    Indicators:
      - commercial_per_km2 (urbanisation)
      - road_km_per_km2 (traffic)
      - evs_per_100k or ev_total (ev_growth)
    """
    cache: Dict[str, Tuple[float, float]] = {}

    if "commercial_per_km2" in df.columns and not df["commercial_per_km2"].dropna().empty:
        s = df["commercial_per_km2"].dropna()
        cache["urbanisation"] = (float(s.quantile(0.333)), float(s.quantile(0.667)))
    else:
        cache["urbanisation"] = (1.0, 5.0)

    if "road_km_per_km2" in df.columns and not df["road_km_per_km2"].dropna().empty:
        s = df["road_km_per_km2"].dropna()
        cache["traffic"] = (float(s.quantile(0.333)), float(s.quantile(0.667)))
    else:
        cache["traffic"] = (0.5, 1.5)

    ev_col = "evs_per_100k" if "evs_per_100k" in df.columns else "ev_total"
    if ev_col in df.columns and not df[ev_col].dropna().empty:
        # Exclude synthetic rows if present
        clean_s = df[df.get("data_flag", "") != "synthetic"][ev_col].dropna() if "data_flag" in df.columns else df[ev_col].dropna()
        if not clean_s.empty:
            cache["ev"] = (float(clean_s.quantile(0.333)), float(clean_s.quantile(0.667)))
        else:
            cache["ev"] = (500.0, 2000.0)
    else:
        cache["ev"] = (500.0, 2000.0)

    return cache


def discretise_district_row(
    district_row: Union[pd.Series, Dict[str, Any]],
    quantiles_cache: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """
    Map continuous Phase 1 district metrics to discrete Bayesian network node states.
    
    Nodes populated:
      - Urbanisation: 'low', 'med', 'high' (from commercial_per_km2)
      - EV_growth: 'low', 'med', 'high' (from ev_total or evs_per_100k; omitted if missing or synthetic)
      - Traffic_exposure: 'low', 'med', 'high' (from road_km_per_km2)
      - OSM_completeness: 'poor', 'fair', 'good' (from confidence)
      - Grid_headroom: 'low', 'med', 'high', or 'unknown' (explicit unobserved telemetry state)
    
    Missing evidence is omitted, allowing the exact inference engine to marginalize over it.
    """
    if quantiles_cache is None:
        quantiles_cache = {
            "urbanisation": (1.0, 5.0),
            "traffic": (0.5, 1.5),
            "ev": (500.0, 2000.0),
        }

    evidence: Dict[str, str] = {}

    # 1. Urbanisation
    comm = district_row.get("commercial_per_km2")
    if comm is not None and not pd.isna(comm):
        q_low, q_high = quantiles_cache.get("urbanisation", (1.0, 5.0))
        if float(comm) <= q_low:
            evidence["Urbanisation"] = "low"
        elif float(comm) <= q_high:
            evidence["Urbanisation"] = "med"
        else:
            evidence["Urbanisation"] = "high"

    # 2. EV_growth
    # Strictly respect data honesty: synthetic or missing EV counts must NEVER be treated as real evidence
    data_flag = str(district_row.get("data_flag", "")).lower()
    status = str(district_row.get("status", "")).lower()
    ev_val = district_row.get("evs_per_100k")
    if ev_val is None or pd.isna(ev_val):
        ev_val = district_row.get("ev_total")

    if data_flag != "synthetic" and status != "no_data" and ev_val is not None and not pd.isna(ev_val):
        q_low, q_high = quantiles_cache.get("ev", (500.0, 2000.0))
        if float(ev_val) <= q_low:
            evidence["EV_growth"] = "low"
        elif float(ev_val) <= q_high:
            evidence["EV_growth"] = "med"
        else:
            evidence["EV_growth"] = "high"

    # 3. Traffic_exposure
    road = district_row.get("road_km_per_km2")
    if road is not None and not pd.isna(road):
        q_low, q_high = quantiles_cache.get("traffic", (0.5, 1.5))
        if float(road) <= q_low:
            evidence["Traffic_exposure"] = "low"
        elif float(road) <= q_high:
            evidence["Traffic_exposure"] = "med"
        else:
            evidence["Traffic_exposure"] = "high"

    # 4. OSM_completeness
    conf = district_row.get("confidence")
    if conf is not None and not pd.isna(conf):
        conf_f = float(conf)
        if conf_f < 0.50:
            evidence["OSM_completeness"] = "poor"
        elif conf_f < 0.75:
            evidence["OSM_completeness"] = "fair"
        else:
            evidence["OSM_completeness"] = "good"

    # 5. Grid_headroom
    grid = district_row.get("grid_headroom")
    if grid in ("low", "med", "high"):
        evidence["Grid_headroom"] = grid
    else:
        evidence["Grid_headroom"] = "unknown"

    return evidence


def compute_credible_interval(
    requirement_posterior: Dict[str, float],
    credibility: float = 0.80,
) -> Tuple[int, int, int]:
    """
    Convert discrete requirement class posterior to P10, P50, and P90 port counts
    using piecewise-linear CDF interpolation over physical requirement tiers.
    
    Tiers (ports):
      - tier_1_low: [0, 50)
      - tier_2_med: [50, 200)
      - tier_3_high: [200, 500)
      - tier_4_severe: [500, 1200]
    """
    bounds = [0.0, 50.0, 200.0, 500.0, 1200.0]
    ordered_states = ["tier_1_low", "tier_2_med", "tier_3_high", "tier_4_severe"]

    raw_probs = [float(requirement_posterior.get(s, 0.0)) for s in ordered_states]
    total_p = sum(raw_probs)
    if total_p <= 0:
        probs = [0.25, 0.25, 0.25, 0.25]
    else:
        probs = [p / total_p for p in raw_probs]

    # Construct cumulative distribution function
    cdf = [0.0]
    for p in probs:
        cdf.append(cdf[-1] + p)
    cdf[-1] = 1.0  # Numerical safeguard

    alpha = (1.0 - credibility) / 2.0
    quantiles = [alpha, 0.50, 1.0 - alpha]
    results: List[int] = []

    for q in quantiles:
        val = bounds[0]
        for i in range(len(probs)):
            if q <= cdf[i + 1] or i == len(probs) - 1:
                span = cdf[i + 1] - cdf[i]
                if span > 1e-12:
                    frac = (q - cdf[i]) / span
                    val = bounds[i] + frac * (bounds[i + 1] - bounds[i])
                else:
                    val = bounds[i]
                break
        results.append(int(round(val)))

    p10, p50, p90 = results[0], results[1], results[2]
    # Enforce strict monotonicity
    p10 = max(0, p10)
    p50 = max(p10, p50)
    p90 = max(p50, p90)

    return p10, p50, p90


def infer_district_full(
    model: BayesianNetworkModel,
    district_row: Union[pd.Series, Dict[str, Any]],
    quantiles_cache: Optional[Dict[str, Any]] = None,
    credibility: float = 0.80,
) -> Dict[str, Any]:
    """
    Run complete Bayesian inference for a single district.
    
    Returns:
      - evidence: Discretised evidence dict
      - posteriors: Full posterior distributions for Requirement_class and Gap_class
      - requirement_posterior: Posterior dict for Requirement_class
      - gap_posterior: Posterior dict for Gap_class
      - p10, p50, p90: Credible interval bounds for required ports
      - ci_width: Absolute 80% credible interval width (p90 - p10)
      - most_likely_gap: State with highest probability in Gap_class
    """
    evidence = discretise_district_row(district_row, quantiles_cache=quantiles_cache)
    posteriors = infer_district_posteriors(
        model, evidence=evidence, target_nodes=["Requirement_class", "Gap_class"]
    )
    req_post = posteriors["Requirement_class"]
    gap_post = posteriors["Gap_class"]

    p10, p50, p90 = compute_credible_interval(req_post, credibility=credibility)
    most_likely_gap = max(gap_post.items(), key=lambda kv: kv[1])[0]

    return {
        "evidence": evidence,
        "posteriors": posteriors,
        "requirement_posterior": req_post,
        "gap_posterior": gap_post,
        "p10": p10,
        "p50": p50,
        "p90": p90,
        "ci_width": p90 - p10,
        "most_likely_gap": most_likely_gap,
    }


def attribute_top_drivers(
    model: BayesianNetworkModel,
    evidence: Dict[str, str],
    target_node: str = "Requirement_class",
    top_k: int = 3,
) -> List[Tuple[str, float]]:
    """
    Attribute which observed or missing evidence nodes most significantly shift the target posterior.
    
    Method:
      1. Baseline posterior P0 under current evidence.
      2. For each observed node k in evidence:
         Calculate Total Variation Distance (TVD) when k is omitted (leave-one-out impact):
         TVD(P0, P_{-k}) = 0.5 * sum_s |P0(s) - P_{-k}(s)|.
      3. For candidate unobserved nodes (e.g. EV_growth when absent):
         Calculate maximum counterfactual shift across possible states:
         max_{s} TVD(P0, P_{+k=s}).
         Labeled as 'missing_{k}' to flag key drivers of uncertainty.
      4. Return ranked list of (node_identifier, shift_magnitude).
    """
    base_res = infer_district_posteriors(model, evidence=evidence, target_nodes=[target_node])
    p0 = base_res[target_node]

    impacts: List[Tuple[str, float]] = []

    # 1. Leave-one-out impact for observed nodes
    for k in list(evidence.keys()):
        if evidence[k] is None:
            continue
        e_reduced = {i: v for i, v in evidence.items() if i != k}
        reduced_res = infer_district_posteriors(model, evidence=e_reduced, target_nodes=[target_node])
        p_reduced = reduced_res[target_node]
        shift = 0.5 * sum(abs(p0[s] - p_reduced.get(s, 0.0)) for s in p0)
        impacts.append((k, round(float(shift), 4)))

    # 2. Counterfactual impact for unobserved nodes
    candidate_unobserved = ["EV_growth", "Urbanisation", "Traffic_exposure", "OSM_completeness"]
    for u in candidate_unobserved:
        if u not in evidence or evidence[u] is None:
            cpd = model.get_cpds(u)
            if cpd is None:
                continue
            max_shift = 0.0
            for state in cpd.state_names[u]:
                e_plus = dict(evidence)
                e_plus[u] = state
                plus_res = infer_district_posteriors(model, evidence=e_plus, target_nodes=[target_node])
                p_plus = plus_res[target_node]
                shift = 0.5 * sum(abs(p0[s] - p_plus.get(s, 0.0)) for s in p0)
                if shift > max_shift:
                    max_shift = shift
            if max_shift > 0.04:
                impacts.append((f"missing_{u}", round(float(max_shift), 4)))

    impacts.sort(key=lambda x: x[1], reverse=True)
    return impacts[:top_k]


def format_driver_summary(
    drivers: List[Tuple[str, float]],
    evidence: Optional[Dict[str, str]] = None,
) -> str:
    """Format top drivers into a human-readable explanation string for outputs and UI."""
    if not drivers:
        return "Baseline prior distribution (no significant evidence shifts)"

    parts: List[str] = []
    for name, shift in drivers:
        if name.startswith("missing_"):
            node = name.replace("missing_", "")
            parts.append(f"missing {node} (uncertainty +{shift:.2f})")
        else:
            state = evidence.get(name) if evidence else ""
            if state:
                parts.append(f"{name}={state} (impact {shift:.2f})")
            else:
                parts.append(f"{name} (impact {shift:.2f})")

    return "Driven by " + "; ".join(parts)
