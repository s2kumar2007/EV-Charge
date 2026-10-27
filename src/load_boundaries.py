"""
STEP 1 - District boundaries, downloaded from the internet (pinned source in config.py).
The raw file is cached in data/raw/, so later runs work offline.
"""
import geopandas as gpd

import config
from utils import PROCESSED, RAW, ensure_dirs, norm_key, request_with_retry

RAW_FILE = RAW / f"boundaries_{config.STATE_SLUG}.geojson"
CLEAN_OUT = PROCESSED / f"districts_{config.STATE_SLUG}.geojson"


def load_boundaries(force=False):
    """Return a GeoDataFrame with columns: district, district_key, geometry (EPSG:4326)."""
    ensure_dirs()
    if force or not RAW_FILE.exists():
        print(f"  downloading boundaries from {config.BOUNDARY_URL}")
        RAW_FILE.write_bytes(request_with_retry("GET", config.BOUNDARY_URL, timeout=config.NETWORK_TIMEOUT_S).content)

    gdf = gpd.read_file(RAW_FILE)
    column = config.BOUNDARY_DISTRICT_COLUMN
    if column not in gdf.columns:
        raise RuntimeError(f"Column '{column}' not found in the boundary file. Found: {list(gdf.columns)}")

    gdf = gdf.rename(columns={column: "district"})[["district", "geometry"]]
    gdf = gdf.to_crs(config.WGS84) if gdf.crs is not None else gdf.set_crs(config.WGS84)
    gdf["geometry"] = gdf.geometry.make_valid()        # repair slightly broken polygons
    gdf["district_key"] = gdf["district"].map(norm_key)
    if gdf.geometry.is_empty.any() or gdf.geometry.isna().any():
        raise RuntimeError("Boundary file contains empty geometry after repair.")
    if not gdf.geom_type.isin(["Polygon", "MultiPolygon"]).all():
        raise RuntimeError("Boundary repair produced non-polygon geometry; review the source.")
    if (gdf["district_key"] == "").any() or gdf["district_key"].duplicated().any():
        raise RuntimeError("Two boundary districts share the same name key - check the data.")
    gdf = gdf.sort_values("district").reset_index(drop=True)
    gdf.to_file(CLEAN_OUT, driver="GeoJSON")
    return gdf


def main():
    gdf = load_boundaries()
    print(f"[1/5] Boundaries: {len(gdf)} districts for {config.STATE_NAME} (source: {config.BOUNDARY_REPO}).")
    print("  Compare this number with the current official district count; newer districts may be missing.")
    return gdf


if __name__ == "__main__":
    main()
