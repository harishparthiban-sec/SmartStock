"""
SmartStock - Output Validation Suite (Person 1)
Validates all data and forecast outputs according to the SmartStock specification.
Prints 'PASS' on success or fails with an informative assertion error.
"""

import os
import sys
import pandas as pd

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from src.forecast.forecast import get_forecast
except ImportError:
    try:
        from .forecast import get_forecast
    except ImportError:
        from forecast import get_forecast


def check_all_outputs():
    # ---------------------------------------------------------
    # 1. File existence & exact columns (Table A4)
    # ---------------------------------------------------------
    specs = {
        "data/products.csv": [
            "product_id", "name", "category", "lead_time_days", "current_stock", "on_order", "unit_cost"
        ],
        "data/sales.csv": [
            "date", "product_id", "units_sold", "promo_flag", "price"
        ],
        "data/holidays.csv": [
            "date", "holiday_name"
        ],
        "data/future_promos.csv": [
            "date", "product_id", "promo_flag"
        ],
        "data/forecast.csv": [
            "date", "product_id", "yhat", "yhat_lower", "yhat_upper"
        ],
        "data/forecast_error.csv": [
            "product_id", "sigma", "mae", "wape_pct"
        ],
        "data/backtest_forecast.csv": [
            "date", "product_id", "yhat", "yhat_lower", "yhat_upper", "actual_units"
        ],
        "data/alerts.csv": [
            "date", "product_id", "actual_units", "yhat_upper", "excess_pct", "severity"
        ],
        "docs/accuracy.csv": [
            "product_id", "mae_model", "wape_model", "mae_baseline", "wape_baseline", "improvement_pct"
        ],
    }

    dfs = {}
    for filepath, expected_cols in specs.items():
        assert os.path.exists(filepath), f"Assertion Error: Missing required file '{filepath}'"
        df = pd.read_csv(filepath)
        actual_cols = list(df.columns)
        assert actual_cols == expected_cols, f"Assertion Error: File '{filepath}' columns {actual_cols} != {expected_cols}"
        assert not df.isnull().values.any(), f"Assertion Error: NaN values detected in '{filepath}'"
        dfs[filepath] = df

    # ---------------------------------------------------------
    # 2. Row counts
    # ---------------------------------------------------------
    assert len(dfs["data/products.csv"]) == 15, f"products.csv expected 15 rows, got {len(dfs['data/products.csv'])}"
    assert len(dfs["data/sales.csv"]) == 10950, f"sales.csv expected 10,950 rows, got {len(dfs['data/sales.csv'])}"
    assert len(dfs["data/future_promos.csv"]) == 675, f"future_promos.csv expected 675 rows, got {len(dfs['data/future_promos.csv'])}"
    assert len(dfs["data/forecast.csv"]) == 675, f"forecast.csv expected 675 rows, got {len(dfs['data/forecast.csv'])}"
    assert len(dfs["data/backtest_forecast.csv"]) == 420, f"backtest_forecast.csv expected 420 rows, got {len(dfs['data/backtest_forecast.csv'])}"
    assert len(dfs["data/forecast_error.csv"]) == 15, f"forecast_error.csv expected 15 rows, got {len(dfs['data/forecast_error.csv'])}"
    assert len(dfs["docs/accuracy.csv"]) == 15, f"accuracy.csv expected 15 rows, got {len(dfs['docs/accuracy.csv'])}"

    # ---------------------------------------------------------
    # 3. Numeric bounds & invariants
    # ---------------------------------------------------------
    # forecast.csv
    fcst = dfs["data/forecast.csv"]
    assert (fcst["yhat"] >= 0).all(), "Assertion Error: Negative yhat in forecast.csv"
    assert (fcst["yhat_lower"] >= 0).all(), "Assertion Error: Negative yhat_lower in forecast.csv"
    assert (fcst["yhat_upper"] >= 0).all(), "Assertion Error: Negative yhat_upper in forecast.csv"
    assert (fcst["yhat_lower"] <= fcst["yhat"]).all(), "Assertion Error: yhat_lower > yhat in forecast.csv"
    assert (fcst["yhat"] <= fcst["yhat_upper"]).all(), "Assertion Error: yhat > yhat_upper in forecast.csv"

    # backtest_forecast.csv
    bt = dfs["data/backtest_forecast.csv"]
    assert (bt["actual_units"] >= 0).all(), "Assertion Error: Negative actual_units in backtest_forecast.csv"
    assert (bt["yhat"] >= 0).all(), "Assertion Error: Negative yhat in backtest_forecast.csv"
    assert (bt["yhat_lower"] >= 0).all(), "Assertion Error: Negative yhat_lower in backtest_forecast.csv"
    assert (bt["yhat_upper"] >= 0).all(), "Assertion Error: Negative yhat_upper in backtest_forecast.csv"
    assert (bt["yhat_lower"] <= bt["yhat"]).all(), "Assertion Error: yhat_lower > yhat in backtest_forecast.csv"
    assert (bt["yhat"] <= bt["yhat_upper"]).all(), "Assertion Error: yhat > yhat_upper in backtest_forecast.csv"

    # forecast_error.csv
    err = dfs["data/forecast_error.csv"]
    assert (err["sigma"] >= 0).all(), "Assertion Error: sigma < 0 in forecast_error.csv"
    assert (err["mae"] >= 0).all(), "Assertion Error: mae < 0 in forecast_error.csv"
    assert (err["wape_pct"] >= 0).all(), "Assertion Error: wape_pct < 0 in forecast_error.csv"

    # ---------------------------------------------------------
    # 4. Domain & Acceptance Behavioral Checks
    # ---------------------------------------------------------
    # P011 forecast rises approaching Diwali (2026-11-08)
    p011_fcst = fcst[fcst["product_id"] == "P011"].copy()
    p011_fcst["dt"] = pd.to_datetime(p011_fcst["date"])
    diwali_date = pd.to_datetime("2026-11-08")
    diwali_peak = p011_fcst[(p011_fcst["dt"] >= diwali_date - pd.Timedelta(days=3)) & (p011_fcst["dt"] <= diwali_date)]["yhat"].mean()
    early_oct = p011_fcst[(p011_fcst["dt"] >= pd.to_datetime("2026-10-07")) & (p011_fcst["dt"] <= pd.to_datetime("2026-10-14"))]["yhat"].mean()
    assert diwali_peak > early_oct, f"Assertion Error: P011 does not rise approaching Diwali ({diwali_peak:.1f} <= {early_oct:.1f})"

    # P007 forecast responds to its October promotion (2026-10-14 to 2026-10-18)
    p007_fcst = fcst[fcst["product_id"] == "P007"].copy()
    p007_fcst["dt"] = pd.to_datetime(p007_fcst["date"])
    promo_mean = p007_fcst[(p007_fcst["dt"] >= pd.to_datetime("2026-10-14")) & (p007_fcst["dt"] <= pd.to_datetime("2026-10-18"))]["yhat"].mean()
    non_promo_mean = p007_fcst[(p007_fcst["dt"] >= pd.to_datetime("2026-10-22")) & (p007_fcst["dt"] <= pd.to_datetime("2026-10-26"))]["yhat"].mean()
    assert promo_mean > non_promo_mean, f"Assertion Error: P007 promo lift not observed ({promo_mean:.1f} <= {non_promo_mean:.1f})"

    # alerts.csv contains the expected spike detections (P008, P012, P003)
    alerts = dfs["data/alerts.csv"]
    alert_products = set(alerts["product_id"].unique())
    assert {"P008", "P012", "P003"}.issubset(alert_products), f"Assertion Error: Missing expected spike products in alerts: {alert_products}"

    # ---------------------------------------------------------
    # 5. Forecast API verification
    # ---------------------------------------------------------
    api_df = get_forecast("P001", horizon_days=10)
    assert len(api_df) == 10, f"get_forecast returned {len(api_df)} rows instead of 10"
    assert list(api_df.columns) == ["date", "product_id", "yhat", "yhat_lower", "yhat_upper"]

    api_all = get_forecast()
    assert len(api_all) == 675, f"get_forecast() returned {len(api_all)} rows instead of 675"

    # ---------------------------------------------------------
    # 6. Demand Intelligence & Copilot Signals verification
    # ---------------------------------------------------------
    signals_path = "data/demand_signals.csv"
    daily_signals_path = "data/daily_demand_signals.csv"
    if os.path.exists(signals_path):
        ds_df = pd.read_csv(signals_path)
        assert len(ds_df) == 15, f"Expected 15 products in {signals_path}, got {len(ds_df)}"
        assert "copilot_explanation" in ds_df.columns, "Missing copilot_explanation column"
        assert not ds_df["copilot_explanation"].isnull().any(), "NaN found in copilot_explanation"

    # ---------------------------------------------------------
    # 7. Demand Time Machine validation
    # ---------------------------------------------------------
    analogs_path = "data/demand_analogs.csv"
    summary_path = "data/demand_analog_summary.csv"
    bt_path = "data/demand_analog_backtest.csv"
    plot_path = "docs/plots/demand_time_machine.png"

    assert os.path.exists(analogs_path), f"Missing {analogs_path}"
    assert os.path.exists(summary_path), f"Missing {summary_path}"
    assert os.path.exists(bt_path), f"Missing {bt_path}"
    assert os.path.exists(plot_path), f"Missing {plot_path}"

    an_df = pd.read_csv(analogs_path)
    expected_an_cols = [
        "product_id", "as_of_date", "window_days", "analog_rank",
        "historical_match_date", "similarity_score", "current_avg_demand",
        "historical_match_avg_demand", "historical_future_avg_demand",
        "historical_change_pct", "historical_holiday", "historical_promo",
        "current_holiday", "current_promo", "event_alignment",
        "analog_agreement", "analog_confidence", "prophet_change_pct",
        "forecast_agreement", "explanation"
    ]
    assert list(an_df.columns) == expected_an_cols, f"Mismatch in {analogs_path} columns"
    assert not an_df.isnull().values.any(), f"NaN values detected in {analogs_path}"
    assert (an_df["similarity_score"] >= 0).all() and (an_df["similarity_score"] <= 100).all(), "Invalid similarity score bounds"
    assert set(an_df["analog_rank"].unique()).issubset({1, 2, 3}), "Invalid analog ranks"

    # Zero future leakage verification
    as_of_dates = pd.to_datetime(an_df["as_of_date"])
    hist_match_dates = pd.to_datetime(an_df["historical_match_date"])
    assert (hist_match_dates < as_of_dates).all(), "Future leakage: historical match date >= as-of date"

    sum_df = pd.read_csv(summary_path)
    expected_sum_cols = [
        "product_id", "as_of_date", "best_match_date", "best_similarity_score",
        "top_3_consensus_growth_pct", "analog_agreement", "analog_confidence",
        "event_alignment", "prophet_change_pct", "forecast_agreement",
        "historical_evidence"
    ]
    assert list(sum_df.columns) == expected_sum_cols, f"Mismatch in {summary_path} columns"
    assert len(sum_df) == 15, f"Expected 15 products in {summary_path}, got {len(sum_df)}"
    assert not sum_df.isnull().values.any(), f"NaN values detected in {summary_path}"

    bt_df = pd.read_csv(bt_path)
    expected_bt_cols = [
        "as_of_date", "product_id", "predicted_change_pct", "actual_change_pct",
        "absolute_error", "best_similarity", "analog_confidence"
    ]
    assert list(bt_df.columns) == expected_bt_cols, f"Mismatch in {bt_path} columns"
    assert len(bt_df) > 0, "Backtest output empty"
    assert not bt_df["absolute_error"].isnull().any(), "NaN found in backtest absolute_error"

    print("PASS")


if __name__ == "__main__":
    check_all_outputs()
