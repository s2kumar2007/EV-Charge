"""
EV Charging Infrastructure Requirements Sizing and Queueing Model.

Inputs:
  - Current or projected EV vehicle populations per district
  - Observed public charging ports and confidence weights
  - Charging behavior parameters (daily km, kWh/km, charging duration, peak arrival share)
Outputs:
  - outputs/charger_requirements.csv: Net charger/port requirements per district with confidence and ranges
Assumptions:
  - Ratio method: baseline sizing based on MoP / CEA planning ratios (e.g. 20-30 EVs per public port).
  - Queueing method: M/M/c multi-server queue with Poisson arrivals and exponential charging times.
  - Monte Carlo simulation: accounts for uncertainty in EV adoption, charger undercount, and peak arrival concentration.
"""
import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


def erlang_c_probability(c: int, traffic_erlangs: float) -> float:
    """Compute Erlang C probability that an arriving vehicle must wait in queue."""
    raise NotImplementedError("Skeleton for test")


def erlang_c_waiting_time(c: int, arrival_rate: float, service_rate: float) -> float:
    """Compute expected waiting time in queue (in hours) for an M/M/c queue."""
    raise NotImplementedError("Skeleton for test")


def size_ports_erlang_c(
    arrival_rate: float,
    service_rate: float,
    target_wait_hours: float = 0.1667,  # 10 minutes target
    max_wait_prob: float = 0.15,
) -> int:
    """Find minimum number of ports c such that waiting time and wait probability meet target."""
    raise NotImplementedError("Skeleton for test")


def calculate_net_charger_requirements(
    district_df: pd.DataFrame,
    evs_per_port: float = 20.0,
    confidence_weighting: bool = True,
) -> pd.DataFrame:
    """Compute transparent EV-to-port ratio sizing with confidence-weighted existing capacity."""
    raise NotImplementedError("Skeleton for test")


def monte_carlo_charger_requirements(
    district_df: pd.DataFrame,
    n_simulations: int = 500,
    random_seed: Optional[int] = None,
) -> pd.DataFrame:
    """Run seeded Monte Carlo simulation over adoption growth, undercount and charging behavior."""
    raise NotImplementedError("Skeleton for test")
