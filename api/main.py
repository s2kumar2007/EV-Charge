"""
FastAPI application for ChargeGap India interactive API and dashboard.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="ChargeGap India API", version="0.2.0")


@app.get("/api/districts")
def get_districts():
    """Retrieve all districts with gap scores and EV infra status."""
    raise NotImplementedError("Skeleton for test")


@app.get("/api/districts/{district_key}")
def get_district(district_key: str):
    """Retrieve single district details by normalized district key."""
    raise NotImplementedError("Skeleton for test")


@app.get("/api/corridors")
def get_corridors():
    """Retrieve highway corridor gap analysis and spacing compliance."""
    raise NotImplementedError("Skeleton for test")


@app.get("/api/sites")
def get_sites():
    """Retrieve recommended priority charging sites."""
    raise NotImplementedError("Skeleton for test")


class WhatIfRequest(BaseModel):
    adoption_growth_pct: float = 20.0
    target_ratio: float = 20.0
    undercount_factor: float = 1.2


@app.post("/api/whatif")
def calculate_whatif(req: WhatIfRequest):
    """Recompute district port deficit ranges under custom what-if assumptions."""
    raise NotImplementedError("Skeleton for test")
