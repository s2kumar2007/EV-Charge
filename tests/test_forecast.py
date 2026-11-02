"""
Tests for EV adoption forecasting, diffusion curves, and backtesting.
All datasets are synthetic in-memory fixtures defined strictly inside this test module.
"""
import pytest
import numpy as np
import pandas as pd

from forecast import (
    load_monthly_vahan,
    fit_logistic_model,
    fit_sarima_model,
    generate_ensemble_forecast,
    rolling_origin_backtest,
    disaggregate_forecast_to_districts,
)


def make_synthetic_logistic_series(n_months: int = 36, L: float = 200000.0, k: float = 0.18, t0: float = 18.0) -> pd.Series:
    """Generate in-memory synthetic logistic adoption curve."""
    t = np.arange(n_months)
    # Logistic cumulative curve
    cum_ev = L / (1.0 + np.exp(-k * (t - t0)))
    # Monthly increments (new registrations)
    monthly = np.diff(cum_ev, prepend=cum_ev[0] * 0.8)
    dates = pd.date_range(start="2022-01-01", periods=n_months, freq="MS")
    return pd.Series(monthly, index=dates, name="ev_registrations")


def test_load_monthly_vahan_valid_and_reject_annual(tmp_path):
    """Verify loader accepts monthly intervals and rejects annual or irregular timestamps."""
    # 1. Valid monthly series
    valid_csv = tmp_path / "valid_monthly.csv"
    valid_csv.write_text(
        "date,state,district,ev_total,data_flag\n"
        "2023-01-01,Tamil Nadu,Chennai,500,real\n"
        "2023-02-01,Tamil Nadu,Chennai,600,real\n"
        "2023-03-01,Tamil Nadu,Chennai,750,real\n"
    )
    df, meta = load_monthly_vahan(str(valid_csv))
    assert len(df) == 3
    assert meta["status"] == "ok"
    assert meta["granularity"] == "monthly"

    # 2. Annual series must be rejected
    annual_csv = tmp_path / "annual.csv"
    annual_csv.write_text(
        "date,state,district,ev_total,data_flag\n"
        "2021-01-01,Tamil Nadu,Chennai,1000,real\n"
        "2022-01-01,Tamil Nadu,Chennai,2500,real\n"
        "2023-01-01,Tamil Nadu,Chennai,5000,real\n"
    )
    with pytest.raises(ValueError, match="Invalid series frequency"):
        load_monthly_vahan(str(annual_csv))


def test_logistic_fit_synthetic_curve():
    """Verify logistic curve fitting and parameter recovery on known synthetic data."""
    series = make_synthetic_logistic_series(n_months=36)
    result = fit_logistic_model(series, horizon_months=36)

    assert result["status"] == "ok"
    assert "forecast" in result
    forecast = result["forecast"]
    assert len(forecast) == 36
    # Future forecasts must be positive and follow monotonic cumulative growth
    assert (forecast["ev_predicted"] >= 0).all()
    assert result["r_squared"] > 0.90
    assert "data_flag" in forecast.columns


def test_sarima_handles_short_series_gracefully():
    """Verify SARIMA skips with clear reason when time series is too short."""
    short_series = make_synthetic_logistic_series(n_months=8)
    result = fit_sarima_model(short_series, horizon_months=12)
    assert result["status"] == "skipped"
    assert "insufficient observations" in result["reason"].lower()


def test_sarima_fits_sufficient_series():
    """Verify SARIMA fits and returns positive forecast on sufficient time series."""
    series = make_synthetic_logistic_series(n_months=26)
    result = fit_sarima_model(series, horizon_months=12, min_observations=24)
    assert result["status"] == "ok"
    assert len(result["forecast"]) == 12
    assert (result["forecast"]["ev_predicted"] >= 0).all()


def test_generate_ensemble_forecast_with_intervals():
    """Verify ensemble forecast combines models and computes ordered bootstrap prediction intervals."""
    series = make_synthetic_logistic_series(n_months=30)
    fc = generate_ensemble_forecast(series, horizon_months=12, n_bootstrap=80)
    assert len(fc) == 12
    assert (fc["ev_predicted"] >= 0).all()
    # Check interval ordering: lower_95 <= lower_80 <= upper_80 <= upper_95
    assert (fc["ci_lower_95"] <= fc["ci_lower_80"] + 1e-4).all()
    assert (fc["ci_lower_80"] <= fc["ev_predicted"] + 1e-4).all()
    assert (fc["ev_predicted"] <= fc["ci_upper_80"] + 1e-4).all()
    assert (fc["ci_upper_80"] <= fc["ci_upper_95"] + 1e-4).all()
    assert fc["data_flag"].iloc[0] == "projected"


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(forecast)")
def test_backtest_flags_insufficient_history():
    """Verify backtest returns clear insufficient history diagnostics for short series."""
    short_series = make_synthetic_logistic_series(n_months=10)
    report = rolling_origin_backtest(short_series, min_train_months=18, horizon_months=6)
    assert not report.empty
    assert "insufficient history" in report.iloc[0]["drivers"].lower()
    assert report.iloc[0]["data_flag"] == "insufficient_data"


@pytest.mark.xfail(raises=NotImplementedError, reason="Implementation pending in feat(forecast)")
def test_disaggregate_forecast_respects_missing_shares():
    """Verify future EV allocations only apply to districts with real positive shares."""
    state_forecast = pd.DataFrame([
        {"year": 2027, "month": 1, "state_ev_forecast": 10000, "data_flag": "real", "confidence": 0.85, "drivers": "Ensemble"}
    ])
    # 2 districts with real counts, 1 with missing data
    shares = pd.DataFrame([
        {"district": "DistA", "district_key": "dista", "ev_total": 800, "data_flag": "real"},
        {"district": "DistB", "district_key": "distb", "ev_total": 200, "data_flag": "real"},
        {"district": "DistC", "district_key": "distc", "ev_total": np.nan, "data_flag": "missing"},
    ])
    dist_forecast = disaggregate_forecast_to_districts(state_forecast, shares)
    assert not dist_forecast.empty

    a_rows = dist_forecast[dist_forecast["district_key"] == "dista"]
    c_rows = dist_forecast[dist_forecast["district_key"] == "distc"]

    # DistA gets 80% (800 / (800+200)) of 10000 = 8000
    assert round(a_rows.iloc[0]["ev_predicted"]) == 8000
    assert a_rows.iloc[0]["data_flag"] == "real"

    # DistC must be flagged missing and not allocated fictitious demand
    assert c_rows.iloc[0]["data_flag"] == "missing"
    assert pd.isna(c_rows.iloc[0]["ev_predicted"])
