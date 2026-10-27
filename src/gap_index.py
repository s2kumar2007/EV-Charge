"""Comparable demand indicators, data-derived entropy weights and rank stability."""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import config
from utils import OUTPUTS, save_json, ensure_dirs


def scale_indicators(values):
    """All directions are positive: larger values mean stronger demand pressure."""
    values = values.astype(float).copy()
    if config.SCALING_METHOD == "robust":
        lower, upper = values.quantile(config.ROBUST_QUANTILES).to_numpy()
        values = values.clip(lower=lower, upper=upper, axis="columns")
    elif config.SCALING_METHOD != "minmax":
        raise ValueError("SCALING_METHOD must be minmax or robust.")
    span = values.max() - values.min()
    return (values - values.min()).divide(span.where(span > config.NUMERIC_TOLERANCE)).fillna(0)


def entropy_weights(scaled):
    """Zero variation means zero information, hence zero entropy weight."""
    x = np.asarray(scaled, dtype=float)
    if x.ndim != 2 or len(x) < 2 or not np.isfinite(x).all() or (x < 0).any():
        raise ValueError("Entropy needs at least two complete, nonnegative rows.")
    sums = x.sum(axis=0)
    p = np.divide(x, sums, out=np.zeros_like(x), where=sums > 0)
    logp = np.zeros_like(p)
    np.log(p, out=logp, where=p > 0)
    entropy = -(p * logp).sum(axis=0) / np.log(len(x))
    diversity = np.maximum(1 - entropy, 0)
    diversity[np.ptp(x, axis=0) <= config.NUMERIC_TOLERANCE] = 0
    if diversity.sum() <= config.NUMERIC_TOLERANCE:
        raise ValueError("All indicators are constant: entropy ranking is undefined.")
    return diversity / diversity.sum()


def ahp_weights():
    """Read expert judgments from config; equal defaults are explicitly provisional."""
    matrix = np.asarray(config.AHP_MATRIX, dtype=float)
    n = len(config.INDICATORS)
    if matrix.shape != (n, n) or not np.isfinite(matrix).all() or (matrix <= 0).any():
        raise ValueError("AHP matrix must be a positive square matrix matching INDICATORS.")
    if not np.allclose(matrix * matrix.T, 1) or not np.allclose(np.diag(matrix), 1):
        raise ValueError("AHP comparisons must be reciprocal with diagonal entries of one.")
    eigenvalues, eigenvectors = np.linalg.eig(matrix)
    i = np.argmax(eigenvalues.real)
    weights = np.abs(eigenvectors[:, i].real)
    weights /= weights.sum()
    ratio = max((eigenvalues[i].real - n) / (n - 1), 0) / config.AHP_RANDOM_INDEX
    if ratio > config.AHP_MAX_CONSISTENCY_RATIO:
        raise ValueError(f"AHP judgments are inconsistent: consistency ratio {ratio:.4f}.")
    return weights, float(ratio)


def ordinal_ranks(scores, labels):
    """Scores descend; district keys break exact ties consistently."""
    order = np.lexsort((np.asarray(labels, dtype=str), -np.asarray(scores)))
    ranks = np.empty(len(scores), dtype=int)
    ranks[order] = np.arange(1, len(scores) + 1)
    return ranks


def rank_sensitivity(scaled, base_weights, labels):
    """Dirichlet draws keep zero-information indicators at zero weight."""
    active = base_weights > config.NUMERIC_TOLERANCE
    rng = np.random.default_rng(config.WEIGHT_SEED)
    draws = np.zeros((config.WEIGHT_RUNS, len(base_weights)))
    draws[:, active] = rng.dirichlet(base_weights[active] * config.DIRICHLET_CONCENTRATION, config.WEIGHT_RUNS)
    scores = np.asarray(scaled) @ draws.T
    ranks = np.column_stack([ordinal_ranks(scores[:, run], labels) for run in range(config.WEIGHT_RUNS)])
    return pd.DataFrame({"min_rank": ranks.min(axis=1), "max_rank": ranks.max(axis=1),
                         "median_rank": np.median(ranks, axis=1),
                         "top_k_share": (ranks <= config.TOP_K).mean(axis=1)})


def compute_index(table):
    """Only complete districts participate in fitting scales or any rankings."""
    result = table.copy().reset_index(drop=True)
    indicators = config.INDICATORS
    values = result[indicators].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    result[indicators] = values
    result["missing_indicators"] = values.isna().apply(lambda row: "|".join(row.index[row]), axis=1)
    complete = result.missing_indicators.eq("")
    for column in ("composite_score", "ahp_score", "min_rank", "max_rank", "median_rank", "top_k_share"):
        result[column] = np.nan
    for column in ("rank", "ahp_rank"):
        result[column] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["index_status"] = np.where(complete, "insufficient variation or observations", "missing indicators")
    result["synthetic"] = result.get("data_flag", pd.Series("missing", index=result.index)).astype(str).str.contains("synthetic", case=False)
    metadata = {"indicator_sources": config.INDICATOR_SOURCES, "scaling": config.SCALING_METHOD,
                "n_complete": int(complete.sum()), "entropy_weights": None, "spearman_rho": None,
                "weight_runs": config.WEIGHT_RUNS, "top_k": config.TOP_K, "seed": config.WEIGHT_SEED}
    ahp, consistency = ahp_weights()
    metadata.update(ahp_weights=dict(zip(indicators, ahp.tolist())), ahp_consistency_ratio=consistency)
    if complete.sum() < 2:
        metadata["reason"] = "At least two complete districts are required. No ranking was invented."
        return result, metadata
    scaled = scale_indicators(values.loc[complete])
    try:
        base = entropy_weights(scaled)
    except ValueError as err:
        metadata["reason"] = str(err)
        return result, metadata
    labels = result.loc[complete, "district_key"]
    score, ahp_score = scaled.to_numpy() @ base, scaled.to_numpy() @ ahp
    result.loc[complete, "composite_score"] = score
    result.loc[complete, "ahp_score"] = ahp_score
    result.loc[complete, "rank"] = ordinal_ranks(score, labels)
    result.loc[complete, "ahp_rank"] = ordinal_ranks(ahp_score, labels)
    sensitivity = rank_sensitivity(scaled, base, labels)
    sensitivity.index = result.index[complete]
    result.loc[complete, sensitivity.columns] = sensitivity
    result.loc[complete, "index_status"] = "ok"
    for column in ("min_rank", "max_rank"):
        result[column] = result[column].astype("Int64")
    # Spearman uses scores and average ranks for ties, not alphabetical tiebreaks.
    rho = spearmanr(score, ahp_score).statistic if np.ptp(ahp_score) > config.NUMERIC_TOLERANCE else np.nan
    metadata.update(entropy_weights=dict(zip(indicators, base.tolist())),
                    spearman_rho=float(rho) if np.isfinite(rho) else None)
    return result, metadata


def assemble_indicators(scores, population, osm):
    """Use the basic score's selected station/port policy consistently."""
    table = scores.copy().rename(columns={"rank": "basic_rank"})
    if "population" in table:
        table = table.rename(columns={"population": "vahan_population"})
    table = table.merge(population[["district_key", "population", "population_source"]], on="district_key", how="left", validate="one_to_one")
    if "vahan_population" in table:
        supplied = table.vahan_population.where(table.vahan_population > 0)
        table.loc[supplied.notna(), "population_source"] = "VAHAN input population (user supplied; verify year and boundaries)"
        table["population"] = supplied.combine_first(table.population)
    table["ev_pressure"] = table.gap_score
    table["evs_per_100k"] = table.ev_total / table.population.where(table.population > 0) * config.PER_100K
    candidate = "population_year" in population and population.population_year.dropna().eq(config.PUBLIC_POPULATION_YEAR).all() and population.population_source.astype(str).str.contains("crosswalk").any()
    table["population_indicator_label"] = config.POPULATION_INDICATOR_LABEL if candidate else config.POPULATION_GENERIC_INDICATOR_LABEL
    return table.merge(osm, on="district_key", how="left", validate="one_to_one")


def main(scores, population, osm):
    ensure_dirs()
    result, metadata = compute_index(assemble_indicators(scores, population, osm))
    metadata["indicator_sources"] = dict(metadata["indicator_sources"])
    metadata["indicator_sources"]["evs_per_100k"] = result.population_indicator_label.iloc[0] if len(result) else config.POPULATION_GENERIC_INDICATOR_LABEL
    result.to_csv(OUTPUTS / "district_gap_index.csv", index=False)
    result[["district", "district_key", "min_rank", "max_rank", "median_rank", "top_k_share", "index_status"]].to_csv(OUTPUTS / "gap_index_sensitivity.csv", index=False)
    save_json(OUTPUTS / "gap_index_methods.json", metadata)
    print("Composite methods:", metadata)
    print(f"Composite ranked: {result['rank'].notna().sum()}/{len(result)}; missing indicators are not filled.")
    return result
