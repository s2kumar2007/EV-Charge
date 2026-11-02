"""
FastAPI application for ChargeGap India interactive API and dashboard.
"""
"""
FastAPI application for ChargeGap India interactive API and dashboard.
"""
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from utils import OUTPUTS, SAMPLES, norm_key

app = FastAPI(title="ChargeGap India API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = ROOT / "api" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=FileResponse)
def get_index():
    """Serve the static Leaflet interactive dashboard."""
    index_file = STATIC_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Dashboard index.html not found.")
    return FileResponse(index_file)


def _clean_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    clean_df = df.replace({np.nan: None})
    return clean_df.to_dict(orient="records")


def _load_enriched_districts() -> pd.DataFrame:
    """Load district gap scores enriched with charger requirements and Gi* hotspots."""
    gap_file = OUTPUTS / "district_gap_scores.csv"
    if not gap_file.exists():
        sample_file = SAMPLES / "vahan_tn_ev_by_district.csv"
        if sample_file.exists():
            return pd.read_csv(sample_file)
        return pd.DataFrame()

    df = pd.read_csv(gap_file)

    # Enrich with charger requirements (deficits, uncertainty percentiles, drivers)
    req_file = OUTPUTS / "charger_requirements.csv"
    if req_file.exists() and "district_key" in df.columns:
        req_df = pd.read_csv(req_file)
        if "district_key" in req_df.columns:
            merge_cols = [
                c for c in [
                    "district_key", "ports_target", "ports_deficit", "confidence", "drivers",
                    "ports_target_p10", "ports_target_p50", "ports_target_p90",
                    "ports_deficit_p10", "ports_deficit_p50", "ports_deficit_p90"
                ] if c in req_df.columns
            ]
            df = df.merge(req_df[merge_cols], on="district_key", how="left", suffixes=("", "_req"))
            if "drivers_req" in df.columns:
                df["drivers"] = df["drivers_req"].combine_first(df.get("drivers", pd.Series(dtype=object)))
                df.drop(columns=["drivers_req"], inplace=True)
            if "confidence_req" in df.columns:
                df["confidence"] = df["confidence_req"].combine_first(df.get("confidence", pd.Series(dtype=float)))
                df.drop(columns=["confidence_req"], inplace=True)

    # Enrich with Gi* spatial hotspot status
    hot_file = OUTPUTS / "district_hotspots.csv"
    if hot_file.exists() and "district_key" in df.columns:
        hot_df = pd.read_csv(hot_file)
        if "district_key" in hot_df.columns:
            hot_cols = [c for c in ["district_key", "class", "z_score", "p_value"] if c in hot_df.columns]
            hot_subset = hot_df[hot_cols].rename(columns={"class": "hotspot_class"})
            df = df.merge(hot_subset, on="district_key", how="left")

    return df


@app.get("/api/districts")
def get_districts() -> List[Dict[str, Any]]:
    """Retrieve all districts with gap scores and EV infra status."""
    df = _load_enriched_districts()
    if not df.empty:
        return _clean_records(df)
    return []


@app.get("/api/districts/{district_key}")
def get_district(district_key: str) -> Dict[str, Any]:
    """Retrieve single district details by normalized district key."""
    df = _load_enriched_districts()
    if df.empty:
        raise HTTPException(status_code=404, detail="District data not found.")
    target_key = norm_key(district_key)
    if "district_key" in df.columns:
        match = df[df["district_key"].astype(str).str.lower() == target_key.lower()]
    else:
        match = df[df["district"].apply(norm_key) == target_key]

    if match.empty:
        raise HTTPException(status_code=404, detail=f"District '{district_key}' not found.")
    return _clean_records(match)[0]


@app.get("/api/corridors")
def get_corridors() -> List[Dict[str, Any]]:
    """Retrieve highway corridor gap analysis and spacing compliance."""
    corridor_file = OUTPUTS / "corridor_gaps.csv"
    if corridor_file.exists():
        df = pd.read_csv(corridor_file)
        return _clean_records(df)
    sample_file = SAMPLES / "corridors_tamil_nadu.csv"
    if sample_file.exists():
        df = pd.read_csv(sample_file)
        return _clean_records(df)
    return []


@app.get("/api/sites")
def get_sites() -> List[Dict[str, Any]]:
    """Retrieve recommended priority charging sites."""
    sites_file = OUTPUTS / "recommended_sites.csv"
    if sites_file.exists():
        df = pd.read_csv(sites_file)
        return _clean_records(df)
    return []


class WhatIfRequest(BaseModel):
    adoption_growth_pct: float = 20.0
    target_ratio: float = 20.0
    undercount_factor: float = 1.2
    n_simulations: int = 150


@app.post("/api/whatif")
def calculate_whatif(req: WhatIfRequest) -> Dict[str, Any]:
    """Recompute district port deficit ranges under custom what-if assumptions."""
    gap_file = OUTPUTS / "district_gap_scores.csv"
    if not gap_file.exists():
        sample_file = SAMPLES / "vahan_tn_ev_by_district.csv"
        if sample_file.exists():
            df = pd.read_csv(sample_file)
        else:
            raise HTTPException(status_code=404, detail="District data not found.")
    else:
        df = pd.read_csv(gap_file)

    rng = np.random.RandomState(2026)
    results = []

    growth_mult = 1.0 + (req.adoption_growth_pct / 100.0)
    for _, row in df.iterrows():
        d_name = row.get("district", "Unknown")
        d_key = str(row.get("district_key", norm_key(d_name)))
        d_flag = str(row.get("data_flag", "real")).lower()
        ev_total = row.get("ev_total", np.nan)
        ports = float(row.get("port_count", row.get("charger_count", 0)))
        if pd.isna(ports):
            ports = 0.0

        if d_flag != "real" or pd.isna(ev_total) or ev_total <= 0:
            results.append({
                "district": d_name,
                "district_key": d_key,
                "ev_total": None,
                "ports_target_p10": None,
                "ports_target_p50": None,
                "ports_target_p90": None,
                "ports_deficit_p10": None,
                "ports_deficit_p50": None,
                "ports_deficit_p90": None,
                "data_flag": d_flag if d_flag != "real" else "missing",
                "drivers": "No EV data; what-if simulation unavailable",
            })
            continue

        base_evs = float(ev_total) * growth_mult
        sim_evs = base_evs * rng.normal(loc=1.0, scale=0.08, size=req.n_simulations)
        sim_ports = ports * req.undercount_factor * rng.uniform(0.9, 1.1, size=req.n_simulations)
        sim_targets = np.ceil(sim_evs / req.target_ratio)
        sim_deficits = np.clip(np.ceil(sim_targets - sim_ports), 0, None)

        p10_t, p50_t, p90_t = np.percentile(sim_targets, [10, 50, 90])
        p10_d, p50_d, p90_d = np.percentile(sim_deficits, [10, 50, 90])

        results.append({
            "district": d_name,
            "district_key": d_key,
            "ev_total": int(round(base_evs)),
            "ports_target_p10": int(p10_t),
            "ports_target_p50": int(p50_t),
            "ports_target_p90": int(p90_t),
            "ports_deficit_p10": int(p10_d),
            "ports_deficit_p50": int(p50_d),
            "ports_deficit_p90": int(p90_d),
            "data_flag": "projected",
            "drivers": f"What-if ({req.adoption_growth_pct:+g}% EV growth, {req.target_ratio:g} EVs/port): P50 deficit = {int(p50_d)}",
        })

    return {
        "parameters": {
            "adoption_growth_pct": req.adoption_growth_pct,
            "target_ratio": req.target_ratio,
            "undercount_factor": req.undercount_factor,
            "n_simulations": req.n_simulations,
        },
        "districts": results,
        "drivers": f"What-if simulation: {req.adoption_growth_pct:+g}% EV growth, {req.target_ratio:g} EVs/port, {req.undercount_factor:g}x charger undercount",
    }
