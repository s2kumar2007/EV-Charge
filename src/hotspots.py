"""Queen-neighbour Moran's I and permutation Getis-Ord Gi*, with BH correction."""
import warnings
import numpy as np
import pandas as pd
import config
from utils import OUTPUTS, save_json, ensure_dirs


def fdr_bh(pvalues):
    """Benjamini-Hochberg adjusted p-values, preserving missing entries."""
    p = np.asarray(pvalues, dtype=float)
    adjusted = np.full(len(p), np.nan)
    valid = np.flatnonzero(np.isfinite(p))
    order = valid[np.argsort(p[valid], kind="stable")]
    if len(order):
        candidates = p[order] * len(order) / np.arange(1, len(order) + 1)
        adjusted[order] = np.minimum(np.minimum.accumulate(candidates[::-1])[::-1], 1)
    return adjusted


def classify(z, p):
    if not np.isfinite(z) or not np.isfinite(p):
        return "not tested"
    for confidence in sorted(config.HOTSPOT_CONFIDENCE_LEVELS, reverse=True):
        if p <= 1 - confidence / 100:
            return f"{'hot spot' if z > 0 else 'cold spot'} {confidence}%" if z != 0 else "not significant"
    return "not significant"


def analyse_hotspots(boundaries, values, permutations=None, seed=None):
    """Missing values and islands are excluded; no new neighbour links are invented."""
    permutations = config.HOTSPOT_PERMUTATIONS if permutations is None else permutations
    seed = config.HOTSPOT_SEED if seed is None else seed
    frame = boundaries[["district", "district_key", "geometry"]].merge(
        values[["district_key", "composite_score"]], on="district_key", how="left", validate="one_to_one")
    frame = frame.sort_values("district_key").reset_index(drop=True)
    result = frame[["district", "district_key"]].copy()
    for column in ("z_score", "p_value", "p_value_folded", "p_value_fdr"):
        result[column] = np.nan
    result["class"] = result["class_raw"] = result["class_fdr"] = "not tested"
    finite = np.isfinite(frame.composite_score.astype(float))
    result["reason"] = np.where(finite, "insufficient observations", "missing composite index")
    metadata = {"I": None, "expected_I": None, "p_value": None, "n": int(finite.sum()),
                "permutations": permutations, "seed": seed,
                "warning": "Few districts: indicative, not conclusive. Missing districts and islands are not tested."}
    if finite.sum() < config.HOTSPOT_MIN_OBSERVATIONS:
        return result, metadata
    try:
        from libpysal.weights import Queen
        from esda import Moran, G_Local
    except ImportError as err:
        raise RuntimeError("Hotspot analysis requires libpysal and esda. Install requirements.txt; no substitute statistic is used.") from err
    subset = frame.loc[finite].copy()
    # Removing missing districts can create new islands. Recheck after each removal.
    while len(subset):
        with warnings.catch_warnings(record=True) as notes:
            warnings.simplefilter("always")
            weights = Queen.from_dataframe(subset, ids=subset.index.tolist(), silence_warnings=True)
        for note in notes:
            print(f"[spatial weights] {note.message}")
        islands = weights.islands
        if not islands:
            break
        result.loc[islands, "reason"] = "no neighbours among complete districts"
        subset = subset.drop(index=islands)
    metadata["n"] = len(subset)
    if len(subset) < config.HOTSPOT_MIN_OBSERVATIONS:
        return result, metadata
    y = subset.loc[weights.id_order, "composite_score"].to_numpy(dtype=float)
    if np.ptp(y) <= config.NUMERIC_TOLERANCE:
        result.loc[subset.index, "reason"] = "constant composite index"
        return result, metadata
    weights.transform = "R"
    # Moran uses NumPy's legacy RNG. Restore it to avoid changing other routines.
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        moran = Moran(y, weights, transformation="R", permutations=permutations)
    finally:
        np.random.set_state(state)
    # Pass binary Queen edges; G_Local adds self with weight 1 and then row-
    # standardises. This makes the Gi* self weight equal to each neighbour.
    weights.transform = "B"
    local = G_Local(y, weights, transform="R", star=True, permutations=permutations,
                    seed=seed, n_jobs=config.HOTSPOT_JOBS, island_weight=config.HOTSPOT_ISLAND_WEIGHT)
    order = weights.id_order
    folded = np.asarray(local.p_sim, dtype=float)
    # PySAL returns a folded one-tail permutation probability. Report conservative
    # two-sided probabilities because we classify both high and low clusters.
    p = np.minimum(folded * config.HOTSPOT_TWO_SIDED_MULTIPLIER, 1)
    z = np.asarray(local.Zs, dtype=float)
    # A district neighbouring every other observation has no local contrast.
    testable = np.isfinite(z)
    p[~testable] = np.nan
    q = fdr_bh(p)
    result.loc[order, "z_score"] = z
    result.loc[order, "p_value_folded"] = folded
    result.loc[order, "p_value"] = p
    result.loc[order, "p_value_fdr"] = q
    result.loc[order, "class_raw"] = [classify(a, b) for a, b in zip(z, p)]
    result.loc[order, "class_fdr"] = [classify(a, b) for a, b in zip(z, q)]
    result.loc[order, "class"] = result.loc[order, "class_fdr"]
    result.loc[order, "reason"] = np.where(testable, "tested", "undefined local variance")
    metadata.update(I=float(moran.I), expected_I=float(moran.EI), p_value=float(moran.p_sim),
                    n_components=int(weights.n_components))
    return result, metadata


def main(boundaries, values):
    ensure_dirs()
    result, metadata = analyse_hotspots(boundaries, values)
    result.to_csv(OUTPUTS / "district_hotspots.csv", index=False)
    save_json(OUTPUTS / "hotspot_statistics.json", metadata)
    print("Moran's I:", metadata)
    if metadata["n"] < config.HOTSPOT_SMALL_N:
        print("[WARNING] Few districts: hotspot results are indicative, not conclusive.")
    return result
