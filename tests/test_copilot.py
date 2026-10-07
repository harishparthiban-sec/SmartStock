"""Unit tests for the Stockout Early Warning, Dynamic Pricing, and AI Reorder Copilot features."""
import os
import pytest
import pandas as pd
import numpy as np

from src.inventory.engine import compute_reorder, simulate_scenario, run_scenario, get_copilot_recommendations
from src.inventory.copilot import evaluate_stockout_warning, evaluate_overstock_pricing, generate_copilot_recommendations


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def stub_data(fixtures_dir):
    products = pd.read_csv(os.path.join(fixtures_dir, "products_stub.csv"))
    forecast = pd.read_csv(os.path.join(fixtures_dir, "forecast_stub.csv"))
    error = pd.read_csv(os.path.join(fixtures_dir, "error_stub.csv"))
    return products, forecast, error


def test_normal_inventory_copilot(stub_data):
    """Normal inventory should produce OK status, LOW urgency, no markdown recommendation."""
    products, forecast, error = stub_data

    # Product with healthy stock (15 days worth of demand = 1500 units, need for 11 days = 1100 units)
    p001_prod = products[products["product_id"] == "P001"].copy()
    p001_prod["current_stock"] = 1500  # < 2 * need (2200), but > ROP (466) -> OK status

    orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )

    row = orders.iloc[0]
    assert row["status"] == "OK"
    assert row["urgency"] == "LOW"
    assert row["copilot_action"] == "MONITOR"
    assert row["pricing_recommendation"] == "Maintain regular price"
    assert not row["stockout_in_7_days"]
    assert "Healthy stock coverage" in row["copilot_reason"]


def test_stockout_early_warning_critical_and_high(stub_data):
    """Tests CRITICAL and HIGH urgency classification based on lead time and days left."""
    products, forecast, error = stub_data

    # 1. CRITICAL: stock covers 1.3 days, but lead time is 4 days -> stockout before arrival!
    p001_prod = products[products["product_id"] == "P001"].copy()
    p001_prod["current_stock"] = 130  # 1.3 days of 100/day demand, lead time = 4

    orders_crit = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )

    row_crit = orders_crit.iloc[0]
    assert row_crit["status"] == "ORDER NOW"
    assert row_crit["urgency"] == "CRITICAL"
    assert row_crit["copilot_action"] == "ORDER NOW"
    assert bool(row_crit["stockout_in_7_days"]) is True
    assert "CRITICAL:" in row_crit["early_warning_message"]

    # 2. HIGH: stock covers 5.0 days (> lead time 4), but status is ORDER NOW
    p001_prod_high = products[products["product_id"] == "P001"].copy()
    p001_prod_high["current_stock"] = 450  # ROP is 466, so IP <= ROP triggers ORDER NOW

    orders_high = compute_reorder(
        products_df=p001_prod_high,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )

    row_high = orders_high.iloc[0]
    assert row_high["status"] == "ORDER NOW"
    assert row_high["urgency"] == "HIGH"
    assert row_high["copilot_action"] == "ORDER NOW"


def test_order_by_date_calculation_consistency(stub_data):
    """Verifies order_by_date logic and that expected_arrival_date is order_by_date + L days."""
    products, forecast, error = stub_data

    # Product with stock approaching ROP
    p001_prod = products[products["product_id"] == "P001"].copy()
    p001_prod["current_stock"] = 600  # ROP is 466, daily demand is 100

    orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )

    row = orders.iloc[0]
    assert row["status"] == "ORDER SOON"
    assert row["urgency"] == "MEDIUM"
    assert row["order_by_date"] != ""
    assert row["expected_arrival_date"] != ""
    # Check arrival is order_by_date + 4 days
    ob_dt = pd.to_datetime(row["order_by_date"])
    arr_dt = pd.to_datetime(row["expected_arrival_date"])
    assert (arr_dt - ob_dt).days == int(row["lead_time_days"])


def test_overstock_detection_and_pricing_recommendation(stub_data):
    """Current stock > 2 * need triggers OVERSTOCK and markdown recommendation."""
    products, forecast, error = stub_data

    p001_prod = products[products["product_id"] == "P001"].copy()
    # Need is 1100.
    # Case A: Stock = 2500 (> 2 * need = 2200, but < 3 * need = 3300) -> 10% discount
    p001_prod["current_stock"] = 2500

    orders_10 = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )

    row_10 = orders_10.iloc[0]
    assert row_10["status"] == "OVERSTOCK"
    assert row_10["pricing_recommendation"] == "Consider 10% promotional discount"
    assert row_10["excess_units"] > 0
    assert row_10["copilot_action"] == "MARKDOWN / PROMOTE"
    assert row_10["order_qty"] == 0

    # Case B: Severe overstock: Stock = 4000 (> 3 * need) -> 20% discount
    p001_prod["current_stock"] = 4000
    orders_20 = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )

    row_20 = orders_20.iloc[0]
    assert row_20["status"] == "OVERSTOCK"
    assert row_20["pricing_recommendation"] == "Consider 20% promotional discount"
    assert "Severe overstock" in row_20["pricing_reason"]


def test_scenario_changes_affecting_recommendations(stub_data):
    """What-if demand surges or drops correctly alter urgency and pricing signals."""
    products, forecast, error = stub_data

    # Product currently in OK status with 1500 units
    p001_prod = products[products["product_id"] == "P001"].copy()
    p001_prod["current_stock"] = 1500

    # Baseline: OK, LOW urgency, maintain price
    base_orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=forecast[forecast["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )
    assert base_orders.iloc[0]["status"] == "OK"
    assert base_orders.iloc[0]["pricing_recommendation"] == "Maintain regular price"

    # Scenario 1: Demand drops by 60% -> 1500 units now becomes OVERSTOCK!
    drop_fc = simulate_scenario(
        forecast_df=forecast,
        uplift_pct=-60.0,
        start_date="2026-10-07",
        end_date="2026-11-20",
    )
    drop_orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=drop_fc[drop_fc["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )
    assert drop_orders.iloc[0]["status"] == "OVERSTOCK"
    assert "Consider" in drop_orders.iloc[0]["pricing_recommendation"]

    # Scenario 2: Demand surges by +150% -> stock burns faster, urgency escalates to CRITICAL/HIGH
    surge_fc = simulate_scenario(
        forecast_df=forecast,
        uplift_pct=150.0,
        start_date="2026-10-07",
        end_date="2026-11-20",
    )
    surge_orders = compute_reorder(
        products_df=p001_prod,
        forecast_df=surge_fc[surge_fc["product_id"] == "P001"],
        error_df=error[error["product_id"] == "P001"],
        include_copilot=True,
    )
    assert surge_orders.iloc[0]["status"] in ("ORDER NOW", "ORDER SOON")
    assert surge_orders.iloc[0]["urgency"] in ("CRITICAL", "HIGH", "MEDIUM")
