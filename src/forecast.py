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
from utils import OUTPUTS, PROCESSED, RAW, SAMPLES, ensure_dirs


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


from scipy.optimize import curve_fit


def _logistic_curve(t: np.ndarray, L: float, k: float, t0: float) -> np.ndarray:
    """Standard 3-parameter logistic sigmoid cumulative adoption curve."""
    return L / (1.0 + np.exp(-np.clip(k * (t - t0), -500, 500)))


def fit_logistic_model(
    series: pd.Series,
    horizon_months: int = 36,
    carrying_capacity: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Fit Logistic / S-curve adoption model to historical EV series.

    Inputs:
      series: pd.Series of monthly registrations (positive numbers).
      horizon_months: Number of months ahead to project (default 36).
      carrying_capacity: Optional upper ceiling (L). If None, estimated via bounded fit.
    Returns:
      dict with keys: 'status', 'r_squared', 'params', 'forecast', 'residuals', 'reason' (if skipped).
    """
    clean_series = series.dropna().astype(float)
    n = len(clean_series)
    if n < 4:
        return {
            "status": "skipped",
            "reason": f"Insufficient observations for logistic fit: {n} points provided, minimum 4 required.",
            "r_squared": 0.0,
            "params": {},
            "forecast": pd.DataFrame(),
        }

    t_obs = np.arange(n, dtype=float)
    y_obs_cum = np.cumsum(clean_series.values)
    max_cum = float(y_obs_cum[-1])

    # Parameter guesses and bounds
    if carrying_capacity is not None and carrying_capacity > max_cum:
        p0 = [carrying_capacity, 0.15, n / 2.0]
        bounds = ([max_cum, 0.001, -n * 2], [carrying_capacity * 1.5, 2.0, n * 5])
    else:
        p0 = [max_cum * 3.0, 0.15, n / 2.0]
        bounds = ([max_cum * 1.05, 0.001, -n * 2], [max_cum * 100.0, 2.0, n * 5])

    try:
        popt, _ = curve_fit(_logistic_curve, t_obs, y_obs_cum, p0=p0, bounds=bounds, maxfev=10000)
        L_fit, k_fit, t0_fit = popt
    except Exception as e:
        return {
            "status": "failed",
            "reason": f"Logistic curve optimization failed: {e}",
            "r_squared": 0.0,
            "params": {},
            "forecast": pd.DataFrame(),
        }

    y_fit_cum = _logistic_curve(t_obs, L_fit, k_fit, t0_fit)
    ss_tot = np.sum((y_obs_cum - np.mean(y_obs_cum)) ** 2)
    ss_res = np.sum((y_obs_cum - y_fit_cum) ** 2)
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    # Project into future
    t_future = np.arange(n, n + horizon_months, dtype=float)
    y_future_cum = _logistic_curve(t_future, L_fit, k_fit, t0_fit)
    all_cum = np.concatenate(([max_cum], y_future_cum))
    monthly_pred = np.diff(all_cum)
    monthly_pred = np.clip(monthly_pred, 0, None)

    # Date handling
    if isinstance(clean_series.index, pd.DatetimeIndex):
        last_dt = clean_series.index[-1]
        future_dates = pd.date_range(start=last_dt + pd.offsets.MonthBegin(1), periods=horizon_months, freq="MS")
    else:
        future_dates = pd.date_range(start="2026-01-01", periods=horizon_months, freq="MS")

    forecast_df = pd.DataFrame({
        "date": future_dates,
        "year": future_dates.year,
        "month": future_dates.month,
        "ev_predicted": monthly_pred,
        "ev_predicted_cumulative": y_future_cum,
        "model": "logistic",
        "data_flag": "projected",
        "confidence": round(max(0.0, min(1.0, float(r2))), 4),
        "drivers": f"Logistic diffusion fit (L={L_fit:.0f}, k={k_fit:.4f}, t0={t0_fit:.1f}, R2={r2:.4f})",
    })

    return {
        "status": "ok",
        "r_squared": float(r2),
        "params": {"L": float(L_fit), "k": float(k_fit), "t0": float(t0_fit)},
        "forecast": forecast_df,
        "fitted_values": y_fit_cum,
        "residuals": y_obs_cum - y_fit_cum,
    }


import warnings
from statsmodels.tsa.statespace.sarimax import SARIMAX


def fit_sarima_model(
    series: pd.Series,
    horizon_months: int = 36,
    seasonal_period: int = 12,
    min_observations: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Fit SARIMA time series model when series length is sufficient, else skip with reason.

    Inputs:
      series: pd.Series of monthly registrations.
      horizon_months: forecast horizon in months (default 36).
      seasonal_period: seasonal cycle length (default 12 for annual seasonality).
      min_observations: minimum observations required (default config.FORECAST_SARIMA_MIN_OBS or 24).
    Returns:
      dict with status ('ok', 'skipped', or 'failed'), forecast df, aic, and diagnostics.
    """
    min_obs = min_observations or getattr(config, "FORECAST_SARIMA_MIN_OBS", 24)
    clean_series = series.dropna().astype(float)
    n = len(clean_series)

    if n < min_obs:
        return {
            "status": "skipped",
            "reason": f"Insufficient observations for SARIMA: {n} points provided, minimum {min_obs} required for seasonal modeling.",
            "aic": None,
            "forecast": pd.DataFrame(),
            "model": "sarima",
        }

    try:
        # Fit SARIMA with robust convergence settings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                mod = SARIMAX(
                    clean_series.values,
                    order=(1, 1, 1),
                    seasonal_order=(1, 0, 0, seasonal_period),
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                res = mod.fit(disp=False, maxiter=100)
            except Exception:
                mod = SARIMAX(
                    clean_series.values,
                    order=(1, 1, 0),
                    enforce_stationarity=False,
                    enforce_invertibility=False,
                )
                res = mod.fit(disp=False, maxiter=100)

        # Forecast
        forecast_res = res.get_forecast(steps=horizon_months)
        pred_vals = np.clip(forecast_res.predicted_mean, 0, None)
        ci = forecast_res.conf_int(alpha=0.05)
        ci_matrix = np.asarray(ci)
        lower_95 = np.clip(ci_matrix[:, 0], 0, None)
        upper_95 = np.clip(ci_matrix[:, 1], 0, None)

        if isinstance(clean_series.index, pd.DatetimeIndex):
            last_dt = clean_series.index[-1]
            future_dates = pd.date_range(start=last_dt + pd.offsets.MonthBegin(1), periods=horizon_months, freq="MS")
        else:
            future_dates = pd.date_range(start="2026-01-01", periods=horizon_months, freq="MS")

        forecast_df = pd.DataFrame({
            "date": future_dates,
            "year": future_dates.year,
            "month": future_dates.month,
            "ev_predicted": pred_vals,
            "ci_lower_95": lower_95,
            "ci_upper_95": upper_95,
            "model": "sarima",
            "data_flag": "projected",
            "confidence": 0.75,
            "drivers": f"SARIMA time series model (AIC={res.aic:.1f})",
        })

        return {
            "status": "ok",
            "aic": float(res.aic),
            "forecast": forecast_df,
            "fitted_values": res.fittedvalues,
            "residuals": res.resid,
            "model": "sarima",
        }
    except Exception as e:
        return {
            "status": "failed",
            "reason": f"SARIMA model fitting error: {e}",
            "aic": None,
            "forecast": pd.DataFrame(),
            "model": "sarima",
        }


def generate_ensemble_forecast(
    historical_series: pd.Series,
    horizon_months: int = 36,
    n_bootstrap: int = 200,
    random_seed: Optional[int] = None,
) -> pd.DataFrame:
    """
    Combine models and compute residual-bootstrap prediction intervals (80% and 95%).

    Inputs:
      historical_series: pd.Series of monthly registrations.
      horizon_months: number of future projection months.
      n_bootstrap: number of residual bootstrap iterations.
      random_seed: PRNG seed for bootstrap reproducibility.
    Returns:
      pd.DataFrame with projected months, point estimates, confidence intervals, drivers, and data_flag.
    """
    clean_series = historical_series.dropna().astype(float)
    if len(clean_series) < 4:
        return pd.DataFrame([{
            "date": pd.NaT,
            "year": 0,
            "month": 0,
            "ev_predicted": np.nan,
            "ci_lower_80": np.nan,
            "ci_upper_80": np.nan,
            "ci_lower_95": np.nan,
            "ci_upper_95": np.nan,
            "models_used": "none",
            "confidence": 0.0,
            "drivers": "Insufficient history for forecasting (less than 4 observations)",
            "data_flag": "insufficient_data",
        }])

    seed = random_seed or getattr(config, "RANDOM_SEED", 2026)
    rng = np.random.RandomState(seed)

    # 1. Fit individual models
    log_res = fit_logistic_model(clean_series, horizon_months=horizon_months)
    sar_res = fit_sarima_model(clean_series, horizon_months=horizon_months)

    models_succeeded = []
    preds = []
    weights = []

    if log_res.get("status") == "ok":
        models_succeeded.append("logistic")
        preds.append(log_res["forecast"]["ev_predicted"].values)
        weights.append(0.60 if sar_res.get("status") == "ok" else 1.0)

    if sar_res.get("status") == "ok":
        models_succeeded.append("sarima")
        preds.append(sar_res["forecast"]["ev_predicted"].values)
        weights.append(0.40)

    if not models_succeeded:
        return pd.DataFrame([{
            "date": pd.NaT,
            "year": 0,
            "month": 0,
            "ev_predicted": np.nan,
            "ci_lower_80": np.nan,
            "ci_upper_80": np.nan,
            "ci_lower_95": np.nan,
            "ci_upper_95": np.nan,
            "models_used": "none",
            "confidence": 0.0,
            "drivers": f"All forecasting models failed: logistic={log_res.get('reason')}",
            "data_flag": "failed",
        }])

    norm_weights = np.array(weights) / np.sum(weights)
    ensemble_pred = np.zeros(horizon_months, dtype=float)
    for p, w in zip(preds, norm_weights):
        ensemble_pred += p * w
    ensemble_pred = np.clip(ensemble_pred, 0, None)

    # Extract dates from primary model forecast
    primary_fc = log_res["forecast"] if log_res.get("status") == "ok" else sar_res["forecast"]
    future_dates = primary_fc["date"]
    years = primary_fc["year"]
    months = primary_fc["month"]

    # 2. Residual bootstrap for prediction intervals
    resids = []
    if "residuals" in log_res and len(log_res["residuals"]) > 0:
        diff_res = np.diff(log_res["residuals"], prepend=log_res["residuals"][0])
        resids.extend(diff_res.tolist())
    if "residuals" in sar_res and len(sar_res["residuals"]) > 0:
        resids.extend(sar_res["residuals"].tolist())

    if len(resids) < 3:
        resids = [0.05 * np.mean(clean_series.values), -0.05 * np.mean(clean_series.values)]

    resids_arr = np.array(resids)
    boot_matrix = np.zeros((n_bootstrap, horizon_months), dtype=float)
    for b in range(n_bootstrap):
        sampled_noise = rng.choice(resids_arr, size=horizon_months, replace=True)
        horizon_scaling = np.sqrt(np.arange(1, horizon_months + 1))
        sim_path = ensemble_pred + (sampled_noise * horizon_scaling)
        boot_matrix[b, :] = np.clip(sim_path, 0, None)

    ci_lower_80 = np.percentile(boot_matrix, 10, axis=0)
    ci_upper_80 = np.percentile(boot_matrix, 90, axis=0)
    ci_lower_95 = np.percentile(boot_matrix, 2.5, axis=0)
    ci_upper_95 = np.percentile(boot_matrix, 97.5, axis=0)

    # Monotonic interval bounds encompassing point estimate
    ci_lower_80 = np.minimum(ci_lower_80, ensemble_pred)
    ci_upper_80 = np.maximum(ci_upper_80, ensemble_pred)
    ci_lower_95 = np.minimum(ci_lower_95, ci_lower_80)
    ci_upper_95 = np.maximum(ci_upper_95, ci_upper_80)

    avg_conf = 0.85 if len(models_succeeded) > 1 else (log_res.get("confidence", 0.70) if "logistic" in models_succeeded else 0.65)
    model_str = "+".join(models_succeeded)
    drivers = f"Ensemble ({model_str}) with {n_bootstrap}-iteration residual bootstrap intervals"

    return pd.DataFrame({
        "date": future_dates.values,
        "year": years.values,
        "month": months.values,
        "ev_predicted": np.round(ensemble_pred, 2),
        "ci_lower_80": np.round(ci_lower_80, 2),
        "ci_upper_80": np.round(ci_upper_80, 2),
        "ci_lower_95": np.round(ci_lower_95, 2),
        "ci_upper_95": np.round(ci_upper_95, 2),
        "models_used": model_str,
        "confidence": round(float(avg_conf), 4),
        "drivers": drivers,
        "data_flag": "projected",
    })


def rolling_origin_backtest(
    series: pd.Series,
    min_train_months: Optional[int] = None,
    horizon_months: Optional[int] = None,
    save_output: bool = True,
) -> pd.DataFrame:
    """
    Run rolling-origin backtest reporting MAPE and MAE per model; flags insufficient history.

    Inputs:
      series: Historical monthly EV registrations pd.Series.
      min_train_months: Minimum training observations before evaluating first forecast (default 18).
      horizon_months: Forecast horizon steps to evaluate at each origin (default 6).
      save_output: If True, writes results to outputs/forecast_backtest.csv.
    Returns:
      pd.DataFrame containing backtest metrics per cutoff and model.
    """
    min_train = min_train_months or getattr(config, "FORECAST_MIN_TRAIN_MONTHS", 18)
    h_months = horizon_months or 6
    clean_series = series.dropna().astype(float)
    n = len(clean_series)

    if n < (min_train + 1):
        report = pd.DataFrame([{
            "origin_index": 0,
            "origin_date": "none",
            "model": "none",
            "horizon_months": h_months,
            "mae": np.nan,
            "mape": np.nan,
            "observations": n,
            "confidence": 0.0,
            "drivers": f"Insufficient history for rolling-origin backtest ({n} observations, minimum {min_train + 1} needed)",
            "data_flag": "insufficient_data",
        }])
        if save_output:
            ensure_dirs()
            out_file = OUTPUTS / getattr(config, "FORECAST_BACKTEST_FILE", "forecast_backtest.csv")
            report.to_csv(out_file, index=False)
        return report

    records = []
    # Test cutoffs from min_train up to n - 1
    max_origins = min(n - 1, min_train + 12)
    for split_idx in range(min_train, max_origins + 1):
        train_s = clean_series.iloc[:split_idx]
        actual_h = min(h_months, n - split_idx)
        if actual_h <= 0:
            continue
        test_actual = clean_series.iloc[split_idx : split_idx + actual_h].values

        origin_dt = clean_series.index[split_idx - 1] if isinstance(clean_series.index, pd.DatetimeIndex) else f"T{split_idx}"
        origin_str = origin_dt.strftime("%Y-%m-%d") if hasattr(origin_dt, "strftime") else str(origin_dt)

        # 1. Logistic model backtest
        log_res = fit_logistic_model(train_s, horizon_months=actual_h)
        if log_res.get("status") == "ok":
            pred_vals = log_res["forecast"]["ev_predicted"].iloc[:actual_h].values
            mae = float(np.mean(np.abs(test_actual - pred_vals)))
            denom = np.where(test_actual > 0, test_actual, 1.0)
            mape = float(np.mean(np.abs((test_actual - pred_vals) / denom)) * 100.0)
            records.append({
                "origin_index": split_idx,
                "origin_date": origin_str,
                "model": "logistic",
                "horizon_months": actual_h,
                "mae": round(mae, 2),
                "mape": round(mape, 2),
                "observations": split_idx,
                "confidence": round(max(0.0, min(1.0, 1.0 - (mape / 100.0))), 4),
                "drivers": f"Logistic fit on {split_idx} points, evaluated over {actual_h} months",
                "data_flag": "backtest",
            })

        # 2. SARIMA model backtest (if points sufficient)
        sar_res = fit_sarima_model(train_s, horizon_months=actual_h, min_observations=20)
        if sar_res.get("status") == "ok":
            pred_vals = sar_res["forecast"]["ev_predicted"].iloc[:actual_h].values
            mae = float(np.mean(np.abs(test_actual - pred_vals)))
            denom = np.where(test_actual > 0, test_actual, 1.0)
            mape = float(np.mean(np.abs((test_actual - pred_vals) / denom)) * 100.0)
            records.append({
                "origin_index": split_idx,
                "origin_date": origin_str,
                "model": "sarima",
                "horizon_months": actual_h,
                "mae": round(mae, 2),
                "mape": round(mape, 2),
                "observations": split_idx,
                "confidence": round(max(0.0, min(1.0, 1.0 - (mape / 100.0))), 4),
                "drivers": f"SARIMA fit on {split_idx} points, evaluated over {actual_h} months",
                "data_flag": "backtest",
            })

    if not records:
        records.append({
            "origin_index": 0,
            "origin_date": "none",
            "model": "none",
            "horizon_months": h_months,
            "mae": np.nan,
            "mape": np.nan,
            "observations": n,
            "confidence": 0.0,
            "drivers": "Models failed during rolling backtest",
            "data_flag": "failed",
        })

    report = pd.DataFrame(records)
    if save_output:
        ensure_dirs()
        out_file = OUTPUTS / getattr(config, "FORECAST_BACKTEST_FILE", "forecast_backtest.csv")
        report.to_csv(out_file, index=False)

    return report


def disaggregate_forecast_to_districts(
    state_forecast_df: pd.DataFrame,
    district_ev_shares: pd.DataFrame,
    save_output: bool = True,
) -> pd.DataFrame:
    """
    Convert state-level EV projections to district projections where real shares exist.

    Rules:
      - Only districts with observed real historical EV counts receive future demand.
      - Missing or synthetic districts are never allocated projected numbers.
      - Each output row carries year, month, district, district_key, ev_predicted,
        share_of_state, confidence, drivers, and data_flag.
    """
    if state_forecast_df.empty or district_ev_shares.empty:
        return pd.DataFrame()

    shares_df = district_ev_shares.copy()
    if "district_key" not in shares_df.columns and "district" in shares_df.columns:
        from utils import norm_key
        shares_df["district_key"] = shares_df["district"].apply(norm_key)

    if "data_flag" not in shares_df.columns:
        shares_df["data_flag"] = "real"

    real_mask = (shares_df["data_flag"] == "real") & (shares_df["ev_total"].notna()) & (shares_df["ev_total"] > 0)
    total_real = float(shares_df.loc[real_mask, "ev_total"].sum())

    if total_real > 0:
        shares_df["share_of_state"] = np.where(real_mask, shares_df["ev_total"] / total_real, np.nan)
    else:
        shares_df["share_of_state"] = np.nan

    out_records = []
    for _, state_row in state_forecast_df.iterrows():
        yr = int(state_row.get("year", 0))
        mo = int(state_row.get("month", 0))
        dt = state_row.get("date", None)
        state_pred = float(state_row.get("state_ev_forecast", state_row.get("ev_predicted", 0.0)))
        state_conf = float(state_row.get("confidence", 0.75))
        state_drivers = str(state_row.get("drivers", "State projection"))

        for _, dist_row in shares_df.iterrows():
            d_name = dist_row.get("district", "Unknown")
            d_key = dist_row.get("district_key", "")
            d_flag = str(dist_row.get("data_flag", "missing")).lower()
            share = dist_row["share_of_state"]

            if pd.notna(share) and share > 0 and d_flag == "real":
                ev_pred = round(state_pred * share, 2)
                out_records.append({
                    "date": dt,
                    "year": yr,
                    "month": mo,
                    "district": d_name,
                    "district_key": d_key,
                    "ev_predicted": ev_pred,
                    "share_of_state": round(float(share), 4),
                    "confidence": round(state_conf * 0.95, 4),
                    "drivers": f"Share {share:.2%} of state projection ({state_drivers})",
                    "data_flag": "real",
                })
            else:
                out_records.append({
                    "date": dt,
                    "year": yr,
                    "month": mo,
                    "district": d_name,
                    "district_key": d_key,
                    "ev_predicted": np.nan,
                    "share_of_state": np.nan,
                    "confidence": 0.0,
                    "drivers": "No historical EV data; excluded from projection allocation",
                    "data_flag": "missing",
                })

    res_df = pd.DataFrame(out_records)
    if save_output:
        ensure_dirs()
        out_file = OUTPUTS / getattr(config, "FORECAST_DISTRICT_FILE", "ev_forecast_district.csv")
        res_df.to_csv(out_file, index=False)

    return res_df


def main():
    """Run EV forecasting pipeline if monthly series is available, or report graceful degradation."""
    print("[1/3] Loading monthly VAHAN data...")
    df, meta = load_monthly_vahan()
    if meta.get("status") != "ok" or df.empty:
        print(f"Monthly VAHAN data not available: {meta.get('reason')}. Skipping forecast projection.")
        return

    print(f"[2/3] Fitting forecasting models for {config.STATE_NAME} ({len(df)} monthly observations)...")
    series = df.set_index("date")["ev_total"] if "date" in df.columns else df["ev_total"]
    rolling_origin_backtest(series, save_output=True)
    ensemble_df = generate_ensemble_forecast(series, horizon_months=getattr(config, "FORECAST_HORIZON_MONTHS", 36))

    state_out = OUTPUTS / getattr(config, "FORECAST_STATE_FILE", "ev_forecast_state.csv")
    ensemble_df.to_csv(state_out, index=False)
    print(f"Saved state forecast to {state_out}")

    print("[3/3] Disaggregating projections to districts with observed historical shares...")
    vahan_file = PROCESSED / "vahan_by_district.csv"
    if vahan_file.exists():
        dist_shares = pd.read_csv(vahan_file)
        disaggregate_forecast_to_districts(ensemble_df, dist_shares, save_output=True)
        print(f"Saved district forecast to {OUTPUTS / getattr(config, 'FORECAST_DISTRICT_FILE', 'ev_forecast_district.csv')}")
    else:
        print("Processed district EV shares not found; state forecast saved.")


if __name__ == "__main__":
    main()
