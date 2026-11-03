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


def discretise_district_row(
    district_row: pd.Series,
    quantiles_cache: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """Map continuous Phase 1 district metrics to discrete Bayesian network node states."""
    raise NotImplementedError("Implementation pending in feat(bayes)")


def compute_credible_interval(
    requirement_posterior: Dict[str, float],
    credibility: float = 0.80,
) -> Tuple[int, int, int]:
    """Convert discrete requirement class posterior to P10, P50, and P90 port range."""
    raise NotImplementedError("Implementation pending in feat(bayes)")


def attribute_top_drivers(
    model: BayesianNetworkModel,
    evidence: Dict[str, str],
    target_node: str = "Requirement_class",
) -> List[Tuple[str, float]]:
    """Attribute which observed or missing evidence nodes most significantly shift the posterior."""
    raise NotImplementedError("Implementation pending in feat(bayes)")
