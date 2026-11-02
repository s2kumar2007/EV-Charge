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

import config
from utils import OUTPUTS, PROCESSED, ensure_dirs


def erlang_c_probability(c: int, traffic_erlangs: float) -> float:
    """
    Compute Erlang C probability that an arriving vehicle must wait in queue.
    Formula:
      P_C(c, A) = [ (A^c / c!) * (1 / (1 - rho)) ] / [ sum_{k=0}^{c-1} (A^k / k!) + (A^c / c!) * (1 / (1 - rho)) ]
      where rho = A / c.
    """
    if c <= 0:
        raise ValueError("Number of servers c must be a positive integer.")
    if traffic_erlangs <= 0.0:
        return 0.0
    A = float(traffic_erlangs)
    rho = A / float(c)
    if rho >= 1.0:
        return 1.0  # System overloaded; queue is unstable

    # Sum_{k=0}^{c-1} A^k / k!
    sum_terms = 0.0
    term = 1.0
    for k in range(c):
        if k > 0:
            term *= (A / k)
        sum_terms += term

    term_c = term * (A / c)
    last_term = term_c / (1.0 - rho)
    denom = sum_terms + last_term
    if denom <= 0:
        return 1.0
    return float(np.clip(last_term / denom, 0.0, 1.0))


def erlang_c_waiting_time(c: int, arrival_rate: float, service_rate: float) -> float:
    """Compute expected waiting time in queue (in hours) for an M/M/c queue."""
    if arrival_rate <= 0.0 or service_rate <= 0.0:
        return 0.0
    A = arrival_rate / service_rate
    rho = A / float(c)
    if rho >= 1.0:
        return float("inf")

    p_c = erlang_c_probability(c, A)
    denom = (c * service_rate) - arrival_rate
    if denom <= 0:
        return float("inf")
    return float(p_c / denom)


def calculate_net_charger_requirements(
    district_df: pd.DataFrame,
    evs_per_port: Optional[float] = None,
    confidence_weighting: Optional[bool] = None,
    save_output: bool = True,
) -> pd.DataFrame:
    """
    Compute transparent EV-to-port ratio sizing with confidence-weighted existing capacity.

    Inputs:
      district_df: DataFrame with district EV counts and existing port counts.
      evs_per_port: Planning ratio (default config.REQUIREMENTS_EVS_PER_PORT or 20.0).
      confidence_weighting: Weight existing ports by confidence (default True).
      save_output: Save to outputs/charger_requirements.csv.
    Returns:
      pd.DataFrame with target ports, effective existing ports, net deficit, drivers, data_flag.
    """
    ratio = evs_per_port or getattr(config, "REQUIREMENTS_EVS_PER_PORT", 20.0)
    use_conf = confidence_weighting if confidence_weighting is not None else getattr(config, "REQUIREMENTS_CONFIDENCE_WEIGHTING", True)

    records = []
    for _, row in district_df.iterrows():
        d_name = row.get("district", "Unknown")
        d_key = row.get("district_key", str(d_name).lower().strip())
        d_flag = str(row.get("data_flag", "real")).lower()
        ev_total = row.get("ev_total", np.nan)
        existing_ports = float(row.get("port_count", row.get("charger_count", 0)))
        if pd.isna(existing_ports):
            existing_ports = 0.0
        conf_score = float(row.get("avg_confidence", row.get("confidence", 0.85)))
        if pd.isna(conf_score) or conf_score <= 0:
            conf_score = 0.85

        if d_flag != "real" or pd.isna(ev_total) or ev_total <= 0:
            records.append({
                "district": d_name,
                "district_key": d_key,
                "ev_total": np.nan,
                "ports_target": np.nan,
                "ports_existing_raw": int(existing_ports),
                "ports_existing_effective": np.nan,
                "ports_deficit": np.nan,
                "confidence": 0.0,
                "drivers": "No EV data available; requirements sizing unavailable",
                "data_flag": d_flag if d_flag != "real" else "missing",
            })
            continue

        ports_target = int(math.ceil(ev_total / ratio))
        effective_existing = round(existing_ports * conf_score, 1) if use_conf else float(existing_ports)
        deficit = max(0, int(math.ceil(ports_target - effective_existing)))

        records.append({
            "district": d_name,
            "district_key": d_key,
            "ev_total": int(ev_total),
            "ports_target": ports_target,
            "ports_existing_raw": int(existing_ports),
            "ports_existing_effective": effective_existing,
            "ports_deficit": deficit,
            "confidence": round(conf_score, 4),
            "drivers": f"Ratio sizing ({ratio:.0f} EVs/port): target {ports_target} - effective existing {effective_existing:.1f} = deficit {deficit}",
            "data_flag": "real",
        })

    res_df = pd.DataFrame(records)
    if save_output:
        ensure_dirs()
        out_file = OUTPUTS / getattr(config, "REQUIREMENTS_OUTPUT_FILE", "charger_requirements.csv")
        res_df.to_csv(out_file, index=False)

    return res_df


def size_ports_erlang_c(
    arrival_rate: float,
    service_rate: float,
    target_wait_hours: float = 0.1667,  # 10 minutes target
    max_wait_prob: float = 0.15,
) -> Dict[str, Any]:
    """
    Find minimum number of ports c such that waiting time and wait probability meet target.

    Inputs:
      arrival_rate: lambda (arrivals per hour).
      service_rate: mu (service rate per port, arrivals per hour).
      target_wait_hours: max acceptable queue delay (default 10 min = 0.1667 hr).
      max_wait_prob: max acceptable probability that an arrival must queue (default 0.15).
    Returns:
      dict with 'ports_needed', 'traffic_erlangs', 'utilization', 'wait_probability',
      'expected_wait_minutes', 'assumptions'.
    """
    if arrival_rate <= 0.0 or service_rate <= 0.0:
        return {
            "ports_needed": 0,
            "traffic_erlangs": 0.0,
            "utilization": 0.0,
            "wait_probability": 0.0,
            "expected_wait_minutes": 0.0,
            "assumptions": "Zero arrival rate; zero ports needed.",
        }

    A = arrival_rate / service_rate
    # Smallest c such that rho < 1
    c = max(1, int(math.floor(A)) + 1)

    while c <= (int(A) + 500):
        prob_wait = erlang_c_probability(c, A)
        wait_hr = erlang_c_waiting_time(c, arrival_rate, service_rate)
        if prob_wait <= max_wait_prob and wait_hr <= target_wait_hours:
            break
        c += 1

    prob_wait = erlang_c_probability(c, A)
    wait_hr = erlang_c_waiting_time(c, arrival_rate, service_rate)
    utilization = A / float(c)

    assumptions = (
        f"M/M/c queue assuming Poisson arrivals (lambda={arrival_rate:.2f}/hr) "
        f"and exponential charging duration (mu={service_rate:.2f}/hr, avg {60.0/service_rate:.1f} min). "
        f"Target queue waiting time <= {target_wait_hours*60:.1f} min and wait probability <= {max_wait_prob:.0%}."
    )

    return {
        "ports_needed": c,
        "traffic_erlangs": round(A, 3),
        "utilization": round(utilization, 3),
        "wait_probability": round(prob_wait, 4),
        "expected_wait_minutes": round(wait_hr * 60.0, 2),
        "target_wait_minutes": round(target_wait_hours * 60.0, 1),
        "assumptions": assumptions,
    }


def monte_carlo_charger_requirements(
    district_df: pd.DataFrame,
    n_simulations: int = 500,
    random_seed: Optional[int] = None,
) -> pd.DataFrame:
    """
    Run seeded Monte Carlo simulation over adoption growth, undercount and charging behavior.

    Inputs:
      district_df: DataFrame with district EV counts and existing port counts.
      n_simulations: Number of Monte Carlo iterations (default 500).
      random_seed: PRNG seed for reproducible simulation (default config.RANDOM_SEED).
    Returns:
      pd.DataFrame containing median (P50) and uncertainty ranges (P10, P90) per district.
    """
    seed = random_seed or getattr(config, "RANDOM_SEED", 2026)
    rng = np.random.RandomState(seed)

    records = []
    for _, row in district_df.iterrows():
        d_name = row.get("district", "Unknown")
        d_key = row.get("district_key", str(d_name).lower().strip())
        d_flag = str(row.get("data_flag", "real")).lower()
        ev_total = row.get("ev_total", np.nan)
        existing_ports = float(row.get("port_count", row.get("charger_count", 0)))
        if pd.isna(existing_ports):
            existing_ports = 0.0
        conf_score = float(row.get("avg_confidence", row.get("confidence", 0.85)))
        if pd.isna(conf_score) or conf_score <= 0:
            conf_score = 0.85

        if d_flag != "real" or pd.isna(ev_total) or ev_total <= 0:
            records.append({
                "district": d_name,
                "district_key": d_key,
                "ev_total": np.nan,
                "ports_target_p10": np.nan,
                "ports_target_p50": np.nan,
                "ports_target_p90": np.nan,
                "ports_deficit_p10": np.nan,
                "ports_deficit_p50": np.nan,
                "ports_deficit_p90": np.nan,
                "confidence": 0.0,
                "drivers": "No EV data available; Monte Carlo range unavailable",
                "data_flag": d_flag if d_flag != "real" else "missing",
            })
            continue

        # Draw uncertainty distributions
        ev_mult = np.clip(rng.normal(loc=1.15, scale=0.12, size=n_simulations), 0.90, 1.60)
        undercount = rng.uniform(1.0, 1.8, size=n_simulations)
        ratios = rng.uniform(16.0, 26.0, size=n_simulations)

        sim_evs = ev_total * ev_mult
        sim_existing = existing_ports * undercount * conf_score
        sim_targets = np.ceil(sim_evs / ratios)
        sim_deficits = np.clip(np.ceil(sim_targets - sim_existing), 0, None)

        p10_t, p50_t, p90_t = np.percentile(sim_targets, [10, 50, 90])
        p10_d, p50_d, p90_d = np.percentile(sim_deficits, [10, 50, 90])

        records.append({
            "district": d_name,
            "district_key": d_key,
            "ev_total": int(ev_total),
            "ports_target_p10": int(p10_t),
            "ports_target_p50": int(p50_t),
            "ports_target_p90": int(p90_t),
            "ports_deficit_p10": int(p10_d),
            "ports_deficit_p50": int(p50_d),
            "ports_deficit_p90": int(p90_d),
            "confidence": round(conf_score, 4),
            "drivers": f"Monte Carlo ({n_simulations} draws): P10={int(p10_d)}, P50={int(p50_d)}, P90={int(p90_d)} deficit ports",
            "data_flag": "real",
        })

    return pd.DataFrame(records)
