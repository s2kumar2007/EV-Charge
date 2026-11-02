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


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(corridors)")
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
