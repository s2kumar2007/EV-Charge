"""Explicit boundary providers, release metadata and reproducible attribution."""
import hashlib
import json
from pathlib import Path
import geopandas as gpd
import pandas as pd
import config
from utils import RAW, cached_json, request_with_retry, save_json, norm_key


def clean_boundaries(frame, name_column, id_column=None, prefix=None):
    if frame.crs is None:
        raise ValueError("Boundary CRS is missing; do not guess coordinate units.")
    if name_column not in frame or (id_column and id_column not in frame):
        raise ValueError("Boundary name/ID columns are missing.")
    result = frame[[name_column, "geometry"]].rename(columns={name_column: "district"}).to_crs(config.WGS84)
    result["district_key"] = frame[id_column].astype("string") if id_column else result.district.map(norm_key)
    if prefix:
        result["district_key"] = prefix + ":" + result.district_key
    result.geometry = result.geometry.make_valid()
    if result.district.isna().any() or result.district.astype(str).str.strip().eq("").any():
        raise ValueError("Boundary names must be nonempty.")
    if result.district_key.isna().any() or result.district_key.eq("").any() or result.district_key.duplicated().any():
        raise ValueError("Boundary IDs/keys must be nonempty and unique.")
    if result.geometry.isna().any() or result.geometry.is_empty.any() or not result.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise ValueError("Boundary geometry is missing or non-polygon after repair.")
    return result.sort_values("district_key").reset_index(drop=True)


def download_geoboundaries(level, force=False):
    metadata_path = RAW / f"{config.GEOBOUNDARIES_CACHE_PREFIX}_{level}_metadata.json"
    def validate(metadata):
        if not isinstance(metadata, dict) or not metadata.get("gjDownloadURL") or not metadata.get("boundaryLicense"):
            raise ValueError("geoBoundaries metadata lacks download URL or licence.")
        if metadata.get("boundaryISO") != config.GEOBOUNDARIES_COUNTRY_ISO or metadata.get("boundaryType") != level:
            raise ValueError("geoBoundaries metadata describes the wrong country/level.")
    metadata = cached_json(metadata_path, "GET", config.GEOBOUNDARIES_METADATA_URLS[level], force=force, validator=validate)
    path = RAW / f"{config.GEOBOUNDARIES_CACHE_PREFIX}_{level}.geojson"
    receipt = path.with_suffix(".receipt.json")
    matching = False
    if receipt.exists():
        previous = json.loads(receipt.read_text())
        matching = previous.get("url") == metadata["gjDownloadURL"] and path.exists() and previous.get("sha256") == hashlib.sha256(path.read_bytes()).hexdigest()
    if force or not matching:
        payload = request_with_retry("GET", metadata["gjDownloadURL"]).content
        # Validate before replacing the last usable geometry snapshot.
        value = json.loads(payload)
        if value.get("type") != "FeatureCollection" or not value.get("features"):
            raise ValueError("geoBoundaries returned empty/invalid GeoJSON.")
        candidate = gpd.GeoDataFrame.from_features(value["features"], crs=config.WGS84)
        clean_boundaries(candidate, config.GEOBOUNDARIES_NAME_COLUMN, config.GEOBOUNDARIES_ID_COLUMN)
        pending = path.with_suffix(".tmp")
        pending.write_bytes(payload)
        pending.replace(path)
        save_json(receipt, {"url": metadata["gjDownloadURL"], "sha256": hashlib.sha256(payload).hexdigest()})
    attribution = "\n".join(f"{key}: {metadata.get(key, 'not supplied')}" for key in
        ["boundaryID", "boundaryYearRepresented", "boundarySource", "boundarySourceURL", "boundaryLicense", "licenseSource", "gjDownloadURL"])
    (RAW / f"{config.GEOBOUNDARIES_CACHE_PREFIX}_{level}_attribution.txt").write_text(attribution + "\n", encoding="utf-8")
    frame = clean_boundaries(gpd.read_file(path), config.GEOBOUNDARIES_NAME_COLUMN, config.GEOBOUNDARIES_ID_COLUMN)
    frame.attrs["source_manifest"] = {"provider": "geoboundaries", "level": level, "metadata": metadata, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "district_count": len(frame)}
    return frame


def select_state(districts, states):
    selected = states[states.district.map(norm_key).eq(norm_key(config.STATE_NAME))]
    if len(selected) != 1:
        raise ValueError("Exactly one ADM1 state must match STATE_NAME by exact normalised name.")
    state = selected.geometry.iloc[0]
    points = districts.to_crs(states.crs).geometry.representative_point()
    return districts.loc[points.within(state)].copy().reset_index(drop=True)


def geoboundaries_state(force=False):
    districts = download_geoboundaries("ADM2", force)
    states = download_geoboundaries("ADM1", force)
    result = select_state(districts, states)
    # State keys stay name-based; national IDs remain release-specific shapeIDs.
    result["district_key"] = result.district.map(norm_key)
    if result.district_key.duplicated().any():
        raise ValueError("geoBoundaries state names are not unique.")
    result.attrs["source_manifest"] = {"provider": "geoboundaries", "ADM2": districts.attrs["source_manifest"], "ADM1": states.attrs["source_manifest"], "district_count": len(result)}
    return result


def pinned_state(force=False):
    path = RAW / f"boundaries_{config.STATE_SLUG}.geojson"
    if force or not path.exists():
        payload = request_with_retry("GET", config.BOUNDARY_URL).content
        candidate = json.loads(payload)
        clean_boundaries(gpd.GeoDataFrame.from_features(candidate["features"], crs=config.WGS84), config.BOUNDARY_DISTRICT_COLUMN)
        path.write_bytes(payload)
    result = clean_boundaries(gpd.read_file(path), config.BOUNDARY_DISTRICT_COLUMN)
    result.attrs["source_manifest"] = {"provider": "pinned_repo", "url": config.BOUNDARY_URL, "commit": config.BOUNDARY_COMMIT,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rights": config.BOUNDARY_RIGHTS_NOTE, "district_count": len(result)}
    return result


def pinned_national(force=False):
    tree = cached_json(RAW / f"boundary_tree_{config.BOUNDARY_COMMIT}.json", "GET", config.BOUNDARY_REPO_TREE_URL, force=force)
    if tree.get("truncated") or "tree" not in tree:
        raise ValueError("Pinned repository file listing is incomplete.")
    paths = sorted(item["path"] for item in tree["tree"] if item.get("type") == "blob" and item["path"].startswith(config.BOUNDARY_REPO_STATE_PREFIX) and item["path"].endswith(".geojson"))
    if not paths:
        raise ValueError("No state boundary files found in pinned repository listing.")
    frames = []
    for source_path in paths:
        slug = Path(source_path).stem
        path = RAW / f"boundaries_{slug}.geojson"
        if force or not path.exists():
            payload = request_with_retry("GET", config.BOUNDARY_REPO_RAW_BASE + source_path).content
            value = json.loads(payload)
            clean_boundaries(gpd.GeoDataFrame.from_features(value["features"], crs=config.WGS84), config.BOUNDARY_DISTRICT_COLUMN, prefix=slug)
            pending = path.with_suffix(".tmp")
            pending.write_bytes(payload)
            pending.replace(path)
        frame = clean_boundaries(gpd.read_file(path), config.BOUNDARY_DISTRICT_COLUMN, prefix=slug)
        frames.append(frame)
    result = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=config.WGS84)
    if result.district_key.duplicated().any():
        raise ValueError("National pinned-repository IDs are not unique.")
    result.attrs["source_manifest"] = {"provider": "pinned_repo", "commit": config.BOUNDARY_COMMIT, "state_files": paths, "district_count": len(result), "rights": config.BOUNDARY_RIGHTS_NOTE}
    return result


def load_provider(national=False, force=False):
    if config.BOUNDARY_PROVIDER == "pinned_repo":
        return pinned_national(force) if national else pinned_state(force)
    if config.BOUNDARY_PROVIDER == "geoboundaries":
        return download_geoboundaries("ADM2", force) if national else geoboundaries_state(force)
    raise ValueError("BOUNDARY_PROVIDER must be pinned_repo or geoboundaries.")


def compare_providers(pinned, geo):
    left, right = set(pinned.district), set(geo.district)
    report = {"pinned_repo_count": len(pinned), "geoboundaries_count": len(geo),
              "only_pinned_repo": sorted(left - right), "only_geoboundaries": sorted(right - left)}
    print("Boundary comparison: " + json.dumps(report, ensure_ascii=False, indent=2))
    return report
