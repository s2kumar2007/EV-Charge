"""Resolver tests use invented districts and an injected geocoder, never downloads."""
import sys
from pathlib import Path
import geopandas as gpd
from shapely.geometry import box
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import config
from resolve_districts import clean_rto_name, resolve_one


def boundaries():
    return gpd.GeoDataFrame({"district": ["Alphaville", "Betatown"], "district_key": ["alphaville", "betatown"]},
                            geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1)], crs=config.WGS84)


def test_exact():
    assert resolve_one("ALPHAVILLE", boundaries(), geocode_fn=lambda q: None) == ("alphaville", "exact")


def test_fuzzy():
    assert resolve_one("Alphavile", boundaries(), geocode_fn=lambda q: None) == ("alphaville", "fuzzy")


def test_geocode():
    assert resolve_one("Unrelated locality", boundaries(), geocode_fn=lambda q: [0.5, 1.5]) == ("betatown", "geocode")


def test_rto():
    assert clean_rto_name("ALPHAVILLE (CENTRAL) RTO - ZZ01") == "ALPHAVILLE"
    assert resolve_one("UNRELATED LOCALITY RTO - ZZ01", boundaries(), kind="rto", geocode_fn=lambda q: [0.5, 0.5]) == ("alphaville", "geocode")


def test_ambiguous_and_shared_border():
    b = boundaries()
    b["district_key"] = ["alphavillea", "alphavilleb"]
    assert resolve_one("Alphaville", b, geocode_fn=lambda q: None) == (None, "unresolved")
    assert resolve_one("Unknown", b, geocode_fn=lambda q: [0.5, 1.0]) == (None, "unresolved")


if __name__ == "__main__":
    for test in (test_exact, test_fuzzy, test_geocode, test_rto, test_ambiguous_and_shared_border):
        test()
        print(f"PASS {test.__name__}")
    print("5 resolver tests passed (offline).")
