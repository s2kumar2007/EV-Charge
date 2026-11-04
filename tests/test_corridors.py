"""
Tests for highway corridor charging site spacing and gap identification.
Uses fictional geometries with exact known distances (no network).
"""
import pytest
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point

from corridors import (
    load_corridors,
    snap_chargers_to_corridor,
    calculate_corridor_spacing,
)


def test_load_corridors_fallback():
    """Verify loading highway corridors from the audited sample fallback."""
    corridors = load_corridors(force_fetch=False)
    assert isinstance(corridors, gpd.GeoDataFrame)
    assert not corridors.empty
    assert "corridor_id" in corridors.columns
    assert "geometry" in corridors.columns
    assert "data_flag" in corridors.columns
    assert "source" in corridors.columns

    # Verify Chennai-Vellore-Bengaluru corridor (NH-48) is present
    nh48 = corridors[corridors["corridor_id"] == "NH-48"]
    assert len(nh48) == 1
    geom = nh48.iloc[0].geometry
    assert isinstance(geom, LineString)
    assert geom.length > 0


def test_snap_chargers_metric_projection():
    """Verify snapping geographic chargers to corridor with UTM metric projection."""
    # Segment near Chennai: (80.20, 13.05) to (80.20, 13.15)
    corridor_geom = LineString([(80.20, 13.05), (80.20, 13.15)])

    chargers_df = pd.DataFrame([
        {"id": "NEAR", "longitude": 80.205, "latitude": 13.10, "confidence": 0.9, "data_flag": "real"},   # ~540 m offset (within 5 km)
        {"id": "FAR", "longitude": 80.35, "latitude": 13.10, "confidence": 0.9, "data_flag": "real"},     # ~16 km offset (outside 5 km)
    ])

    snapped = snap_chargers_to_corridor(
        corridor_geom=corridor_geom,
        chargers_df=chargers_df,
        buffer_meters=5000.0,
        metric_crs="EPSG:32644",
    )
    assert len(snapped) == 1
    assert snapped.iloc[0]["id"] == "NEAR"
    assert snapped.iloc[0]["offset_m"] < 1000.0
    assert snapped.iloc[0]["distance_along_m"] > 0


def test_corridor_dual_confidence_run():
    """Verify dual-run (all chargers vs high confidence) flags larger gaps when low-confidence sites are excluded."""
    from corridors import analyze_corridors

    corridor_geom = LineString([(80.0, 13.0), (80.0, 13.9)])  # ~100 km north-south line
    corridors_gdf = gpd.GeoDataFrame([
        {"corridor_id": "TEST-DUAL", "corridor_name": "Dual Test Line", "geometry": corridor_geom}
    ], crs="EPSG:4326")

    # Three chargers:
    # 1. Near start (high confidence)
    # 2. Midway (low confidence 0.3)
    # 3. Near end (high confidence)
    chargers_df = pd.DataFrame([
        {"id": "CH1", "name": "Start Site", "longitude": 80.001, "latitude": 13.1, "confidence": 0.9, "data_flag": "real"},
        {"id": "CH2_LOW", "name": "Mid Site Low Conf", "longitude": 80.001, "latitude": 13.5, "confidence": 0.3, "data_flag": "real"},
        {"id": "CH3", "name": "End Site", "longitude": 80.001, "latitude": 13.8, "confidence": 0.95, "data_flag": "real"},
    ])

    df, gdf = analyze_corridors(
        corridors_gdf=corridors_gdf,
        chargers_df=chargers_df,
        confidence_cutoff=0.5,
        save_outputs=False,
    )

    assert not df.empty
    modes = set(df["filter_mode"])
    assert modes == {"all_chargers", "high_confidence"}

    df_all = df[df["filter_mode"] == "all_chargers"]
    df_hc = df[df["filter_mode"] == "high_confidence"]

    # When low-confidence site is excluded, the number of segments decreases and max gap increases
    assert len(df_hc) < len(df_all)
    assert df_hc["gap_km"].max() > df_all["gap_km"].max()


def test_corridor_outputs_contract(tmp_path, monkeypatch):
    """Verify corridor gap CSV and GeoJSON contracts when running pipeline."""
    from corridors import analyze_corridors
    import config

    monkeypatch.setattr(config, "CORRIDOR_OUTPUT_CSV", "test_corridor_gaps.csv")
    monkeypatch.setattr(config, "CORRIDOR_OUTPUT_GEOJSON", "test_corridor_gaps.geojson")
    from utils import OUTPUTS

    corridor_geom = LineString([(80.0, 13.0), (80.0, 13.5)])
    corridors_gdf = gpd.GeoDataFrame([
        {"corridor_id": "TEST-CONTRACT", "corridor_name": "Contract Line", "geometry": corridor_geom}
    ], crs="EPSG:4326")
    chargers_df = pd.DataFrame([
        {"id": "CH1", "name": "Test Charger", "longitude": 80.001, "latitude": 13.2, "confidence": 0.9, "data_flag": "real"}
    ])

    df, gdf = analyze_corridors(corridors_gdf=corridors_gdf, chargers_df=chargers_df, save_outputs=True)
    csv_file = OUTPUTS / "test_corridor_gaps.csv"
    geojson_file = OUTPUTS / "test_corridor_gaps.geojson"
    try:
        assert csv_file.exists()
        assert geojson_file.exists()
        loaded_df = pd.read_csv(csv_file)
        assert not loaded_df.empty
        for req_col in ("corridor_id", "from_location", "to_location", "gap_km", "flag_regular_gap", "flag_heavy_gap", "drivers", "data_flag"):
            assert req_col in loaded_df.columns
    finally:
        if csv_file.exists():
            csv_file.unlink()
        if geojson_file.exists():
            geojson_file.unlink()


def test_corridor_spacing_fictional_line():
    """Verify consecutive-site spacing and gap flagging on a 100 km fictional corridor."""
    # Fictional straight corridor of length 100,000 meters (100 km) in a Cartesian plane
    # Line from (0, 0) to (100000, 0)
    corridor_geom = LineString([(0, 0), (100000, 0)])

    # Fictional chargers along the corridor at:
    # Charger 1: 10,000 m (10 km) along, 500 m offset
    # Charger 2: 35,000 m (35 km) along, 100 m offset  -> gap from ch1 = 25 km (> 20 km)
    # Charger 3: 45,000 m (45 km) along, 0 m offset    -> gap from ch2 = 10 km (<= 20 km)
    # Charger 4: 80,000 m (80 km) along, 300 m offset  -> gap from ch3 = 35 km (> 20 km)
    # Beyond 80 km to end (100 km) -> gap = 20 km (<= 20 km)
    chargers_df = pd.DataFrame([
        {"id": "C1", "name": "Site 1", "longitude": 10000, "latitude": 500, "confidence": 0.9, "data_flag": "real"},
        {"id": "C2", "name": "Site 2", "longitude": 35000, "latitude": 100, "confidence": 0.8, "data_flag": "real"},
        {"id": "C3", "name": "Site 3", "longitude": 45000, "latitude": 0, "confidence": 0.4, "data_flag": "real"},
        {"id": "C4", "name": "Site 4", "longitude": 80000, "latitude": -300, "confidence": 0.95, "data_flag": "real"},
        {"id": "C_FAR", "name": "Off Corridor", "longitude": 50000, "latitude": 20000, "confidence": 0.9, "data_flag": "real"},  # 20km offset, outside 5km buffer
    ])

    snapped = snap_chargers_to_corridor(
        corridor_geom=corridor_geom,
        chargers_df=chargers_df,
        buffer_meters=5000.0,
        metric_crs=None,  # Already Cartesian coordinates
    )
    assert len(snapped) == 4, f"Expected 4 chargers snapped, got {len(snapped)}"
    assert list(snapped["id"]) == ["C1", "C2", "C3", "C4"]

    gaps_df, gaps_gdf = calculate_corridor_spacing(
        corridor_id="NH-TEST",
        corridor_name="Test Highway",
        corridor_geom=corridor_geom,
        snapped_chargers=snapped,
        max_gap_km=20.0,
        max_gap_heavy_km=100.0,
        metric_crs=None,
    )

    # Stretches:
    # 0 to 10 km: gap 10 km (not flagged)
    # 10 to 35 km: gap 25 km (flagged regular)
    # 35 to 45 km: gap 10 km (not flagged)
    # 45 to 80 km: gap 35 km (flagged regular)
    # 80 to 100 km: gap 20 km (not flagged)
    assert len(gaps_df) == 5
    flagged_regular = gaps_df[gaps_df["gap_km"] > 20.0]
    assert len(flagged_regular) == 2
    assert set(flagged_regular["gap_km"].round(1)) == {25.0, 35.0}

    # Verify audit columns
    for col in ("confidence", "drivers", "data_flag"):
        assert col in gaps_df.columns, f"Missing required column {col}"


def test_zero_length_corridor_gap_maintains_linestring_geometry():
    """Verify that 0-length gaps (e.g. charger at corridor origin) produce LineString geometries, not Point."""
    corridor_geom = LineString([(0, 0), (50000, 0)])
    chargers_df = pd.DataFrame([
        {"id": "ORIGIN_SITE", "name": "At Origin", "longitude": 0, "latitude": 0, "confidence": 0.9, "data_flag": "real"}
    ])
    snapped = snap_chargers_to_corridor(
        corridor_geom=corridor_geom,
        chargers_df=chargers_df,
        buffer_meters=1000.0,
        metric_crs=None,
    )
    gaps_df, gaps_gdf = calculate_corridor_spacing(
        corridor_id="NH-ZERO",
        corridor_name="Zero Gap Test",
        corridor_geom=corridor_geom,
        snapped_chargers=snapped,
        max_gap_km=20.0,
        metric_crs=None,
    )
    assert len(gaps_df) >= 1
    # First segment (origin to origin site) has gap_km == 0
    assert gaps_df.iloc[0]["gap_km"] == 0.0
    # Every feature geometry MUST be a LineString for GIS layer homogeneity
    geom_types = [g.geom_type for g in gaps_gdf.geometry]
    assert all(gt == "LineString" for gt in geom_types), f"Found non-LineString geometries: {geom_types}"
