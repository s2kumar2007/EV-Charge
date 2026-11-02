"""
EV Adoption Forecasting and Backtesting Module.

Inputs:
  - Monthly VAHAN EV registration series (or annual / state historical series)
  - District share distributions from historical EV registrations
Outputs:
  - outputs/forecast_backtest.csv: Rolling-origin backtest performance (MAPE, MAE)
  - outputs/ev_forecast_state.csv: State-level future EV projections (3-5 years) with prediction intervals
  - outputs/ev_forecast_district.csv: District-level future EV demand projections
Assumptions:
  - Diffusion follows Bass / Logistic S-curve dynamics bounded by vehicle fleet carrying capacity.
  - Granularity is strictly checked; annual data is never treated as monthly.
  - District forecasts only apply to districts with observed real historical shares.
"""
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


def load_monthly_vahan(
    file_path: Optional[str] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Load and validate monthly VAHAN time series, refusing annual or irregular series."""
    raise NotImplementedError("Skeleton for test")


def fit_logistic_model(
    series: pd.Series,
    horizon_months: int = 36,
    carrying_capacity: Optional[float] = None,
) -> Dict[str, Any]:
    """Fit Logistic / S-curve adoption model to historical EV series."""
    raise NotImplementedError("Skeleton for test")


def fit_sarima_model(
    series: pd.Series,
    horizon_months: int = 36,
    seasonal_period: int = 12,
) -> Dict[str, Any]:
    """Fit SARIMA time series model when series length is sufficient, else skip with reason."""
    raise NotImplementedError("Skeleton for test")


def generate_ensemble_forecast(
    historical_series: pd.Series,
    horizon_months: int = 36,
    n_bootstrap: int = 200,
) -> pd.DataFrame:
    """Combine models and compute residual-bootstrap prediction intervals (80% and 95%)."""
    raise NotImplementedError("Skeleton for test")


def rolling_origin_backtest(
    series: pd.Series,
    min_train_months: int = 18,
    horizon_months: int = 6,
) -> pd.DataFrame:
    """Run rolling-origin backtest reporting MAPE and MAE per model; flags insufficient history."""
    raise NotImplementedError("Skeleton for test")


def disaggregate_forecast_to_districts(
    state_forecast_df: pd.DataFrame,
    district_ev_shares: pd.DataFrame,
) -> pd.DataFrame:
    """Convert state-level EV projections to district projections where real shares exist."""
    raise NotImplementedError("Skeleton for test")
