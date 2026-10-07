"""Unit tests for the backtest policy simulation."""
import os
import pytest
import pandas as pd
import numpy as np

from src.inventory.backtest import simulate_single_product_policy, run_backtest


def test_simulate_policy_shortage_detection():
    """Verify that a surge in demand causes shortage counting and fill rate degradation."""
    # 28 days with demand 100, but day 5 has an unexpected spike of 1000
    actuals = [100.0] * 28
    actuals[5] = 1000.0
    forecasts = [100.0] * 28

    res_naive = simulate_single_product_policy(
        lead_time=4,
        actual_units=actuals,
        forecast_units=forecasts,
        policy="NAIVE",
        m_naive=100.0,
    )

    assert res_naive["stockout_days"] > 0
    assert res_naive["units_short"] > 0
    assert res_naive["fill_rate_pct"] < 100.0


def test_run_backtest_output_structure():
    """Verify run_backtest outputs the required columns and ALL summary rows."""
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    p_df = pd.read_csv(os.path.join(fixtures_dir, "products_stub.csv"))
    bt_df = pd.read_csv(os.path.join(fixtures_dir, "backtest_forecast_stub.csv"))
    s_df = pd.read_csv(os.path.join(fixtures_dir, "sales_stub.csv"))
    e_df = pd.read_csv(os.path.join(fixtures_dir, "error_stub.csv"))

    results = run_backtest(p_df, bt_df, s_df, e_df)

    # Columns: product_id, policy, stockout_days, units_short, fill_rate_pct, avg_on_hand_units
    expected_cols = [
        "product_id",
        "policy",
        "stockout_days",
        "units_short",
        "fill_rate_pct",
        "avg_on_hand_units",
    ]
    assert list(results.columns) == expected_cols

    # Should contain ALL rows for both NAIVE and SMART
    all_rows = results[results["product_id"] == "ALL"]
    assert len(all_rows) == 2
    assert set(all_rows["policy"]) == {"NAIVE", "SMART"}
