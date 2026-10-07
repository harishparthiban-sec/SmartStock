"""Unit tests for the SmartStock inventory engine."""
import math
import os
import pytest
import pandas as pd
import numpy as np

from src.inventory.engine import compute_reorder, simulate_scenario, run_scenario
from src.inventory.config import SERVICE_LEVEL, REVIEW_PERIOD_DAYS


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def stub_data(fixtures_dir):
    products = pd.read_csv(os.path.join(fixtures_dir, "products_stub.csv"))
    forecast = pd.read_csv(os.path.join(fixtures_dir, "forecast_stub.csv"))
    error = pd.read_csv(os.path.join(fixtures_dir, "error_stub.csv"))
    return products, forecast, error


def test_hand_calculated_reorder(stub_data):
    """Verifies the exact hand-calculated test from Spec Task 5.

    Given:
      yhat = 100/day flat, L = 4, current_stock = 300, on_order = 0,
      sigma = 20, service_level = 0.95, review_period = 7.
    Expected:
      Z = 1.64485
      SS = 1.64485 * 20 * sqrt(4) = 65.794
      ROP = 400 + 65.794 = 465.794 -> reported 466
      need = (4 + 7) * 100 = 1100
      order_qty = ceil(1100 + 65.794 - 300) = 866
      status = ORDER NOW
    """
    products, forecast, error = stub_data

    # Filter to product P001 which has lead_time 4, current_stock 300, on_order 0
    p001_prod = products[products["product_id"] == "P001"].copy()
    p001_fc = forecast[forecast["product_id"] == "P001"].copy()
    p001_err = error[error["product_id"] == "P001"].copy()

    orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=p001_fc,
        error_df=p001_err,
        service_level=0.95,
        review_period_days=7,
        lead_time_extra_days=0,
    )

    assert len(orders) == 1
    row = orders.iloc[0]

    assert row["status"] == "ORDER NOW"
    assert row["reorder_point"] == 466
    assert row["order_qty"] == 866
    assert row["safety_stock"] == 65.79
    assert row["lead_time_days"] == 4
    assert row["avg_daily_demand"] == 100.0
    assert row["order_by_date"] == "2026-10-07"
    assert row["expected_arrival_date"] == "2026-10-11"
    assert "Order 866 now" in row["reason"]


def test_overstock_status(stub_data):
    """Current stock far above 2 * need should result in OVERSTOCK and order_qty = 0."""
    products, forecast, error = stub_data

    p001_prod = products[products["product_id"] == "P001"].copy()
    # Need for 11 days = 1100. Set current_stock = 2500 (> 2 * 1100 = 2200)
    p001_prod.loc[p001_prod["product_id"] == "P001", "current_stock"] = 2500

    orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
    )

    row = orders.iloc[0]
    assert row["status"] == "OVERSTOCK"
    assert row["order_qty"] == 0
    assert "more than twice" in row["reason"]


def test_order_soon_status(stub_data):
    """Inventory position between ROP and ROP + 3*d should trigger ORDER SOON."""
    products, forecast, error = stub_data

    p001_prod = products[products["product_id"] == "P001"].copy()
    # ROP = 465.794, d = 100, ROP + 3*d = 765.794. Set stock to 600
    p001_prod.loc[p001_prod["product_id"] == "P001", "current_stock"] = 600

    orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
    )

    row = orders.iloc[0]
    assert row["status"] == "ORDER SOON"
    assert row["order_qty"] > 0
    assert "reach the reorder point" in row["reason"]


def test_zero_forecast_demand(stub_data):
    """Zero demand should not cause division by zero errors and order_qty should be 0."""
    products, forecast, error = stub_data

    zero_fc = forecast[forecast["product_id"] == "P001"].copy()
    zero_fc["yhat"] = 0.0

    p001_prod = products[products["product_id"] == "P001"].copy()

    orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=zero_fc,
        error_df=error[error["product_id"] == "P001"],
    )

    row = orders.iloc[0]
    assert row["avg_daily_demand"] == 0.0
    assert row["order_qty"] == 0
    assert row["status"] in ("OK", "OVERSTOCK")


def test_lead_time_longer_than_forecast_horizon(stub_data):
    """Short forecast horizon must not crash the engine; it uses the whole available forecast."""
    products, forecast, error = stub_data

    # Forecast only 2 days long, while lead time is 4 days
    short_fc = forecast[
        (forecast["product_id"] == "P001")
        & (forecast["date"].isin(["2026-10-07", "2026-10-08"]))
    ].copy()

    p001_prod = products[products["product_id"] == "P001"].copy()

    orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=short_fc,
        error_df=error[error["product_id"] == "P001"],
    )

    assert len(orders) == 1
    assert orders.iloc[0]["days_of_stock_left"] <= 3


def test_simulate_scenario_and_run_scenario(stub_data):
    """Simulate scenario must be immutable and accurately scale demand and order quantities."""
    products, forecast, error = stub_data

    orig_forecast_copy = forecast.copy(deep=True)

    # 1. 50% uplift on 2026-10-10 to 2026-10-15
    sim_fc = simulate_scenario(
        forecast_df=forecast,
        uplift_pct=50.0,
        start_date="2026-10-10",
        end_date="2026-10-15",
        product_ids=["P001"],
    )

    # Assert immutability of original forecast dataframe
    pd.testing.assert_frame_equal(forecast, orig_forecast_copy)

    # Assert simulated rows for P001 increased from 100 to 150
    p001_uplifted = sim_fc[
        (sim_fc["product_id"] == "P001") & (sim_fc["date"] == "2026-10-10")
    ]
    assert p001_uplifted.iloc[0]["yhat"] == 150.0

    # Other products untouched
    p002_row = sim_fc[
        (sim_fc["product_id"] == "P002") & (sim_fc["date"] == "2026-10-10")
    ]
    assert p002_row.iloc[0]["yhat"] == 100.0

    # 2. Uplift 0% is an identity transformation
    sim_zero = simulate_scenario(forecast, 0.0, "2026-10-07", "2026-11-20")
    assert np.allclose(sim_zero["yhat"], forecast["yhat"])

    # 3. run_scenario produces correct comparison
    before_df, after_df, comp_df = run_scenario(
        products_df=products,
        forecast_df=forecast,
        error_df=error,
        uplift_pct=50.0,
        start_date="2026-10-07",
        end_date="2026-10-17",
        product_ids=["P001"],
    )

    p001_comp = comp_df[comp_df["product_id"] == "P001"].iloc[0]
    assert p001_comp["order_qty_after"] > p001_comp["order_qty_before"]
    assert p001_comp["delta"] == (
        p001_comp["order_qty_after"] - p001_comp["order_qty_before"]
    )


def test_supplier_delay_extra_lead_time(stub_data):
    """Adding extra lead time increases safety stock and reorder point."""
    products, forecast, error = stub_data
    p001_prod = products[products["product_id"] == "P001"]
    p001_fc = forecast[forecast["product_id"] == "P001"]
    p001_err = error[error["product_id"] == "P001"]

    base_order = compute_reorder(
        products_df=p001_prod,
        forecast_df=p001_fc,
        error_df=p001_err,
        lead_time_extra_days=0,
    ).iloc[0]

    delayed_order = compute_reorder(
        products_df=p001_prod,
        forecast_df=p001_fc,
        error_df=p001_err,
        lead_time_extra_days=2,
    ).iloc[0]

    assert delayed_order["safety_stock"] > base_order["safety_stock"]
    assert delayed_order["reorder_point"] > base_order["reorder_point"]
