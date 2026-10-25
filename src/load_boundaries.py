"""
STEP 1 - District boundaries.

We use the open DataMeet India districts dataset (Census 2011 boundaries),
keep only Tamil Nadu, and save a cleaned copy. The raw files are cached in
data/raw/ so the next run works offline.
"""
import geopandas as gpd

from utils import PROCESSED, RAW, ensure_dirs, norm_key, request_with_retry

BASE_URL = "https://raw.githubusercontent.com/datameet/maps/master/Districts/Census_2011/"
# A shapefile is really 4 files that belong together.
PARTS = ["2011_Dist.shp", "2011_Dist.dbf", "2011_Dist.shx", "2011_Dist.prj"]
RAW_DIR = RAW / "datameet_districts_2011"
TN_OUT = PROCESSED / "tn_districts.geojson"


def download_boundaries(force=False):
    """Download the shapefile parts into data/raw/ (skipped if already cached)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for part in PARTS:
        target = RAW_DIR / part
        if target.exists() and not force:
            continue
        print(f"  downloading {part} ...")
        response = request_with_retry("GET", BASE_URL + part, timeout=120)
        target.write_bytes(response.content)


def load_boundaries(force=False):
    """Return a GeoDataFrame of Tamil Nadu districts: district, district_key, geometry."""
    ensure_dirs()
    download_boundaries(force)

    india = gpd.read_file(RAW_DIR / "2011_Dist.shp")
    tn = india[india["ST_NM"] == "Tamil Nadu"].copy()
    if tn.empty:
        raise RuntimeError("No Tamil Nadu rows found in the boundary file (column ST_NM).")

    tn = tn.rename(columns={"DISTRICT": "district"})[["district", "geometry"]]

    # Always work in latitude/longitude (EPSG:4326) so every layer shares one CRS.
    tn = tn.to_crs(4326) if tn.crs is not None else tn.set_crs(4326)

    # Some source polygons are slightly "broken"; make_valid repairs them.
    tn["geometry"] = tn.geometry.make_valid()

    # A comparable key used later to match names with the VAHAN file.
    tn["district_key"] = tn["district"].map(norm_key)
    if tn["district_key"].duplicated().any():
        raise RuntimeError("Two boundary districts share the same name key - check the data.")

    tn = tn.sort_values("district").reset_index(drop=True)
    tn.to_file(TN_OUT, driver="GeoJSON")
    return tn


def report_name_mismatches(boundaries, vahan_names):
    """
    Compare boundary district names with the names in the VAHAN file.
    Returns (vahan_names_without_polygon, polygons_without_vahan_row) and prints both.
    """
    boundary_keys = dict(zip(boundaries["district_key"], boundaries["district"]))
    vahan_keys = {norm_key(n): n for n in vahan_names if norm_key(n)}

    only_vahan = [name for key, name in vahan_keys.items() if key not in boundary_keys]
    only_boundary = [name for key, name in boundary_keys.items() if key not in vahan_keys]

    print(f"  VAHAN names with NO matching boundary polygon: {only_vahan or 'none'}")
    print(f"  Boundary districts with NO VAHAN row:          {only_boundary or 'none'}")
    return only_vahan, only_boundary


def main():
    tn = load_boundaries()
    print(f"[1/5] Boundaries: found {len(tn)} Tamil Nadu districts in the DataMeet (Census 2011) file.")
    if len(tn) != 38:
        print("  note: Tamil Nadu has 38 districts today; this file is from 2011, so newer "
              "districts (e.g. Tenkasi, Ranipet, Chengalpattu) are not separate polygons.")
    print(f"  saved cleaned copy -> {TN_OUT}")
    return tn


if __name__ == "__main__":
    main()
