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
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

import config
from utils import RAW, SAMPLES


def load_monthly_vahan(
    file_path: Optional[Union[str, Path]] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Load and validate monthly VAHAN time series, refusing annual or irregular series.

    Inputs:
      file_path: Optional path to CSV file. If None, checks data/raw/vahan_monthly.csv,
                 then data/samples/vahan_monthly.csv.
    Returns:
      (df, metadata_dict)
    Raises:
      ValueError: if the series has non-monthly granularity (e.g. annual or irregular).
      FileNotFoundError: if a specific file_path was requested but does not exist.
    """
    if file_path is None:
        raw_file = RAW / getattr(config, "VAHAN_MONTHLY_FILE", "vahan_monthly.csv")
        sample_file = SAMPLES / getattr(config, "VAHAN_MONTHLY_FILE", "vahan_monthly.csv")
        if raw_file.exists():
            target = raw_file
            source_label = f"data/raw/{raw_file.name}"
        elif sample_file.exists():
            target = sample_file
            source_label = f"data/samples/{sample_file.name}"
        else:
            return pd.DataFrame(), {
                "status": "missing_file",
                "reason": f"No monthly VAHAN file found at {raw_file} or {sample_file}.",
                "granularity": "none",
            }
    else:
        target = Path(file_path)
        if not target.exists():
            raise FileNotFoundError(f"Requested monthly VAHAN file not found: {target}")
        source_label = str(target)

    df = pd.read_csv(target)
    if df.empty:
        return df, {"status": "empty", "source": source_label, "granularity": "none"}

    # Validate required columns
    if "date" not in df.columns:
        raise ValueError(f"Monthly VAHAN CSV must contain 'date' column. Found columns: {list(df.columns)}")
    if "ev_total" not in df.columns:
        raise ValueError(f"Monthly VAHAN CSV must contain 'ev_total' column. Found columns: {list(df.columns)}")

    df["date"] = pd.to_datetime(df["date"])
    unique_dates = df["date"].drop_duplicates().sort_values()

    # Granularity validation: check interval lengths between consecutive dates
    if len(unique_dates) >= 2:
        intervals_days = unique_dates.diff().iloc[1:].dt.days
        # Monthly intervals typically span 28 to 31 days (allowing 25 to 35 for calendar variance)
        is_irregular = (intervals_days < 25) | (intervals_days > 35)
        if is_irregular.any():
            bad_intervals = intervals_days[is_irregular].tolist()
            raise ValueError(
                f"Invalid series frequency: expected monthly frequency with ~28-31 day intervals, "
                f"but found intervals spanning {bad_intervals} days. Annual or irregular series cannot be treated as monthly."
            )

    # Data flag normalization
    if "data_flag" in df.columns:
        df["data_flag"] = df["data_flag"].fillna("real").astype(str).str.lower()
    else:
        df["data_flag"] = "real"

    date_range = (
        unique_dates.min().strftime("%Y-%m-%d"),
        unique_dates.max().strftime("%Y-%m-%d"),
    ) if len(unique_dates) > 0 else None

    return df, {
        "status": "ok",
        "source": source_label,
        "granularity": "monthly",
        "rows": len(df),
        "date_range": date_range,
    }


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
