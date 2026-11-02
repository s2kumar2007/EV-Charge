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


def _clean_records(df: pd.DataFrame) -> List[Dict[str, Any]]:
    clean_df = df.replace({np.nan: None})
    return clean_df.to_dict(orient="records")


@app.get("/api/districts")
def get_districts() -> List[Dict[str, Any]]:
    """Retrieve all districts with gap scores and EV infra status."""
    gap_file = OUTPUTS / "district_gap_scores.csv"
    if gap_file.exists():
        df = pd.read_csv(gap_file)
        return _clean_records(df)
    return []


@app.get("/api/districts/{district_key}")
def get_district(district_key: str) -> Dict[str, Any]:
    """Retrieve single district details by normalized district key."""
    gap_file = OUTPUTS / "district_gap_scores.csv"
    if not gap_file.exists():
        raise HTTPException(status_code=404, detail="District gap scores not found.")
    df = pd.read_csv(gap_file)
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


@app.post("/api/whatif")
def calculate_whatif(req: WhatIfRequest):
    """Recompute district port deficit ranges under custom what-if assumptions."""
    raise NotImplementedError("Skeleton for test")
