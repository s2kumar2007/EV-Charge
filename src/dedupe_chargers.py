"""Merge nearby charger records conservatively; keep an auditable membership table."""
import difflib
import json
import numpy as np
import pandas as pd
import geopandas as gpd
from scipy.spatial import cKDTree

import config
from utils import PROCESSED, OUTPUTS, ensure_dirs, norm_key

COLUMNS = ["cluster_id", "latitude", "longitude", "sources", "n_source_records", "ports",
           "ports_known", "name", "operator", "spread_m", "confidence"]
AUDIT_COLUMNS = ["cluster_id", "raw_record", "source", "source_id", "name", "operator"]


def _text(value):
    return "" if pd.isna(value) else str(value).strip()


def _similar(left, right, threshold):
    return difflib.SequenceMatcher(None, norm_key(left), norm_key(right)).ratio() >= threshold


def compatible(a, b, distance, radius):
    """An operator disagreement blocks merging, even when names look similar."""
    names = (_text(a["name"]), _text(b["name"]))
    operators = (_text(a["operator"]), _text(b["operator"]))
    if all(operators) and not _similar(*operators, config.DEDUP_OPERATOR_SIMILARITY):
        return False
    if all(names):
        return _similar(*names, config.DEDUP_NAME_SIMILARITY)
    if all(operators):
        return True
    # Without enough labels, only merge records that are extremely close.
    return distance <= radius * config.DEDUP_UNNAMED_RADIUS_FRACTION


def confidence(components):
    """Weighted mean of documented evidence, never a probability of correctness."""
    weights = config.CONFIDENCE_WEIGHTS
    if set(weights) != set(components) or min(weights.values()) < 0 or sum(weights.values()) <= 0:
        raise ValueError("Confidence weights must cover all components and have positive total.")
    return sum(weights[k] * components[k] for k in weights) / sum(weights.values())


def deduplicate(chargers, radius=None, geodesic=False):
    """Distance components are DBSCAN with min_samples=1; labels refine merges.

    The final groups must pass every pairwise distance and label check. This
    stops a long chain of nearby records from swallowing separate stations.
    """
    radius = config.DEDUP_RADIUS_M if radius is None else radius
    if radius <= 0:
        raise ValueError("Deduplication radius must be positive metres.")
    if chargers.empty:
        return pd.DataFrame(columns=COLUMNS), pd.DataFrame(columns=AUDIT_COLUMNS)
    raw = chargers.copy().sort_values(["source", "source_id"], kind="stable").reset_index(drop=True)
    if raw[["source", "source_id"]].duplicated().any():
        raise ValueError("Duplicate source IDs in fetched records; review the source response.")
    raw["ports_known"] = raw["ports_known"].astype(str).str.lower().isin(["true", "1"])
    points = gpd.GeoDataFrame(raw, geometry=gpd.points_from_xy(raw.longitude, raw.latitude), crs=config.WGS84)
    if geodesic:
        from pyproj import Geod
        geod = Geod(ellps="WGS84")
        # Geocentric metres avoid choosing one UTM zone for the whole country.
        # A 3D transform needs explicit zero-height coordinates.
        from pyproj import Transformer
        transform = Transformer.from_crs(config.WGS84, config.INDIA_GEOCENTRIC_CRS, always_xy=True)
        xyz = transform.transform(raw.longitude.to_numpy(), raw.latitude.to_numpy(), np.zeros(len(raw)))
        xy = np.column_stack(xyz)
        metric_crs = None
    else:
        metric_crs = points.estimate_utm_crs()
    if metric_crs is None and not geodesic:
        raise ValueError("Could not choose a metric CRS for deduplication.")
    if not geodesic:
        metric = points.to_crs(metric_crs)
        xy = np.column_stack([metric.geometry.x, metric.geometry.y])
    def distance(a, b):
        if geodesic:
            return geod.inv(raw.iloc[a].longitude, raw.iloc[a].latitude,
                            raw.iloc[b].longitude, raw.iloc[b].latitude)[2]
        return np.linalg.norm(xy[a] - xy[b])
    pairs = sorted(cKDTree(xy).query_pairs(radius))
    # Connected components give the coarse distance clusters without another library.
    parent = list(range(len(raw)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b in pairs:
        parent[root(b)] = root(a)
    components = {}
    for i in range(len(raw)):
        components.setdefault(root(i), []).append(i)
    groups = []
    for members in components.values():
        refined = []
        for i in members:
            for group in refined:
                if all(distance(i, j) <= radius and
                       compatible(raw.iloc[i], raw.iloc[j], distance(i, j), radius)
                       for j in group):
                    group.append(i)
                    break
            else:
                refined.append([i])
        groups.extend(refined)
    merged, audit = [], []
    for number, members in enumerate(groups, start=1):
        rows = raw.iloc[members]
        if geodesic:
            from shapely.geometry import Point
            location = Point(float(rows.longitude.mean()), float(rows.latitude.mean()))
            spread = float(max(geod.inv(location.x, location.y, r.longitude, r.latitude)[2] for r in rows.itertuples()))
        else:
            centre = xy[members].mean(axis=0)
            spread = float(np.linalg.norm(xy[members] - centre, axis=1).max())
            location = gpd.GeoSeries(gpd.points_from_xy([centre[0]], [centre[1]]), crs=metric_crs).to_crs(config.WGS84).iloc[0]
        sources = sorted(set(rows.source))
        known = rows.loc[rows.ports_known, "ports"]
        # Longest nonempty label is deterministic and usually the most informative.
        name = max((_text(v) for v in rows.name), key=lambda v: (len(v), v))
        operator = max((_text(v) for v in rows.operator), key=lambda v: (len(v), v))
        parts = {"sources": min(len(sources) / config.CONFIDENCE_SOURCE_TARGET, 1),
                 "name": bool(name), "operator": bool(operator), "ports": not known.empty,
                 "spread": max(0, 1 - spread / radius)}
        cluster_id = f"cluster_{number}"
        record = dict(cluster_id=cluster_id, latitude=location.y, longitude=location.x,
                      sources=json.dumps(sources), n_source_records=len(rows),
                      ports=int(known.max()) if len(known) else config.DEFAULT_PORTS,
                      ports_known=not known.empty, name=name, operator=operator,
                      spread_m=spread, confidence=confidence(parts))
        record.update({f"confidence_{key}": float(value) for key, value in parts.items()})
        merged.append(record)
        for i in members:
            audit.append({"cluster_id": cluster_id, "raw_record": i,
                          **raw.loc[i, ["source", "source_id", "name", "operator"]].to_dict()})
    return pd.DataFrame(merged), pd.DataFrame(audit, columns=AUDIT_COLUMNS)


def main(chargers=None):
    ensure_dirs()
    if chargers is None:
        chargers = pd.read_csv(PROCESSED / "chargers_raw.csv").fillna({"name": "", "operator": ""})
    merged, audit = deduplicate(chargers)
    merged.to_csv(PROCESSED / "chargers_deduplicated.csv", index=False)
    audit.to_csv(PROCESSED / "chargers_merge_audit.csv", index=False)
    sensitivity = pd.DataFrame([{"radius_m": radius, "raw_count": len(chargers),
                                 "charger_count": len(deduplicate(chargers, radius)[0])}
                                for radius in config.DEDUP_RADII_M])
    sensitivity.to_csv(OUTPUTS / "dedup_radius_sensitivity.csv", index=False)
    sample = merged.sample(n=min(len(merged), config.VALIDATION_SAMPLE_SIZE), random_state=config.VALIDATION_SEED).copy()
    sample["checked_ok"], sample["notes"] = "", ""
    sample_path = OUTPUTS / "validation_sample.csv"
    # Never erase the user's hand-written review on a later pipeline run.
    if sample_path.exists():
        # Keep every reviewed file. New samples receive a unique suffix.
        from datetime import datetime, timezone
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        sample_path = OUTPUTS / f"validation_sample_{stamp}.csv"
    sample.to_csv(sample_path, index=False)
    print(f"Deduplication: {len(chargers)} raw -> {len(merged)} stations; {len(chargers) - len(merged)} removed")
    print(sensitivity.to_string(index=False))
    return merged


if __name__ == "__main__":
    main()
