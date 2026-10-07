"""FastAPI REST backend for SmartStock.

Exposes all inventory engine data as JSON API endpoints
so the React / Vite / TailwindCSS frontend can consume it.

Run with:
    uvicorn src.api.server:app --reload --port 8000

CORS is open to localhost:5173 (Vite default dev port).
"""
import os
import json
import math
from typing import List, Optional

import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.inventory.engine import (
    compute_reorder,
    simulate_scenario,
    run_scenario,
    get_copilot_recommendations,
)
from src.inventory.config import SERVICE_LEVEL, REVIEW_PERIOD_DAYS

# ---------------------------------------------------------------------------
# App and CORS
# ---------------------------------------------------------------------------
app = FastAPI(
    title="SmartStock API",
    description="Demand-aware inventory reorder backend for the SmartStock React dashboard.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
DATA_DIR = "data"
FIXTURES_DIR = os.path.join("tests", "fixtures")
OUTPUT_DIR = "output"


def _resolve(real_name: str, stub_name: str) -> Optional[str]:
    real = os.path.join(DATA_DIR, real_name)
    stub = os.path.join(FIXTURES_DIR, stub_name)
    if os.path.exists(real):
        return real
    if os.path.exists(stub):
        return stub
    return None


def _load_products() -> pd.DataFrame:
    path = _resolve("products.csv", "products_stub.csv")
    if not path:
        raise HTTPException(status_code=503, detail="products.csv not found.")
    return pd.read_csv(path)


def _load_forecast() -> pd.DataFrame:
    path = _resolve("forecast.csv", "forecast_stub.csv")
    if not path:
        raise HTTPException(status_code=503, detail="forecast.csv not found.")
    return pd.read_csv(path)


def _load_error() -> Optional[pd.DataFrame]:
    path = _resolve("forecast_error.csv", "error_stub.csv")
    return pd.read_csv(path) if path else None


def _load_sales() -> Optional[pd.DataFrame]:
    path = _resolve("sales.csv", "sales_stub.csv")
    return pd.read_csv(path) if path else None


def _load_holidays() -> Optional[pd.DataFrame]:
    path = _resolve("holidays.csv", "")
    return pd.read_csv(path) if path else None


def _load_future_promos() -> Optional[pd.DataFrame]:
    path = _resolve("future_promos.csv", "")
    return pd.read_csv(path) if path else None


def _load_backtest() -> Optional[pd.DataFrame]:
    path = _resolve("backtest_forecast.csv", "backtest_forecast_stub.csv")
    return pd.read_csv(path) if path else None


def _load_analog() -> Optional[pd.DataFrame]:
    """Loads demand_analog_summary.csv (real or stub). Returns None if unavailable."""
    path = _resolve("demand_analog_summary.csv", "demand_analog_summary_stub.csv")
    return pd.read_csv(path) if path else None


def _df_to_records(df: pd.DataFrame) -> list:
    """Convert a DataFrame to JSON-safe list of dicts, handling NaN and numpy types."""
    records = df.to_dict(orient="records")
    cleaned = []
    for r in records:
        clean_r = {}
        for k, v in r.items():
            if isinstance(v, float) and math.isnan(v):
                clean_r[k] = None
            elif isinstance(v, (np.integer,)):
                clean_r[k] = int(v)
            elif isinstance(v, (np.floating,)):
                clean_r[k] = float(v)
            elif isinstance(v, (np.bool_,)):
                clean_r[k] = bool(v)
            else:
                clean_r[k] = v
        cleaned.append(clean_r)
    return cleaned


# ---------------------------------------------------------------------------
# Pydantic models for request bodies
# ---------------------------------------------------------------------------
class ScenarioRequest(BaseModel):
    uplift_pct: float = 0.0
    start_date: str = "2026-10-07"
    end_date: str = "2026-11-20"
    product_ids: Optional[List[str]] = None
    lead_time_extra_days: int = 0
    service_level: float = SERVICE_LEVEL
    review_period_days: int = REVIEW_PERIOD_DAYS


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root():
    """Health check."""
    return {"status": "ok", "service": "SmartStock API v1.0.0"}


@app.get("/api/products", tags=["Data"])
def get_products():
    """Returns the full product catalog."""
    df = _load_products()
    return {"data": _df_to_records(df)}


@app.get("/api/forecast", tags=["Data"])
def get_forecast(product_id: Optional[str] = Query(None)):
    """Returns 45-day demand forecasts. Optionally filter by product_id."""
    df = _load_forecast()
    if product_id:
        df = df[df["product_id"] == product_id]
    return {"data": _df_to_records(df)}


@app.get("/api/orders", tags=["Inventory Engine"])
def get_orders(
    service_level: float = Query(default=SERVICE_LEVEL),
    review_period_days: int = Query(default=REVIEW_PERIOD_DAYS),
    category: Optional[str] = Query(default=None),
):
    """Computes replenishment orders with real-time parameters from the React UI.

    Supports sidebar service_level and review_period_days controls.
    """
    p_df = _load_products()
    f_df = _load_forecast()
    e_df = _load_error()
    s_df = _load_sales()
    a_df = _load_analog()

    if category:
        p_df = p_df[p_df["category"] == category]

    orders = compute_reorder(
        products_df=p_df,
        forecast_df=f_df,
        error_df=e_df,
        sales_df=s_df,
        service_level=service_level,
        review_period_days=review_period_days,
        include_copilot=False,
        analog_df=a_df,
    )
    return {"data": _df_to_records(orders), "count": len(orders)}


@app.get("/api/copilot", tags=["AI Copilot"])
def get_copilot(
    service_level: float = Query(default=SERVICE_LEVEL),
    review_period_days: int = Query(default=REVIEW_PERIOD_DAYS),
    category: Optional[str] = Query(default=None),
):
    """Returns enriched AI Reorder Copilot data including:
    - stockout early warnings
    - urgency levels (CRITICAL / HIGH / MEDIUM / LOW)
    - dynamic pricing/overstock recommendations
    - copilot_action and copilot_reason
    """
    p_df = _load_products()
    f_df = _load_forecast()
    e_df = _load_error()
    s_df = _load_sales()
    h_df = _load_holidays()
    fp_df = _load_future_promos()
    a_df = _load_analog()

    if category:
        p_df = p_df[p_df["category"] == category]

    orders = compute_reorder(
        products_df=p_df,
        forecast_df=f_df,
        error_df=e_df,
        sales_df=s_df,
        service_level=service_level,
        review_period_days=review_period_days,
        include_copilot=False,
        analog_df=a_df,
    )

    copilot_df = get_copilot_recommendations(
        orders_df=orders,
        forecast_df=f_df,
        holidays_df=h_df,
        future_promos_df=fp_df,
    )
    return {"data": _df_to_records(copilot_df), "count": len(copilot_df)}


@app.post("/api/scenario", tags=["What-If Scenarios"])
def post_scenario(body: ScenarioRequest):
    """Runs a what-if scenario and returns before/after/comparison data.

    The React What-If page sends user slider values here and renders the comparison table.
    """
    p_df = _load_products()
    f_df = _load_forecast()
    e_df = _load_error()

    before_df, after_df, comparison_df = run_scenario(
        products_df=p_df,
        forecast_df=f_df,
        error_df=e_df,
        uplift_pct=body.uplift_pct,
        start_date=body.start_date,
        end_date=body.end_date,
        product_ids=body.product_ids,
        lead_time_extra_days=body.lead_time_extra_days,
        service_level=body.service_level,
        review_period_days=body.review_period_days,
    )

    # Summary delta for React summary banner
    total_before = int(before_df["order_qty"].sum())
    total_after = int(after_df["order_qty"].sum())

    return {
        "summary": {
            "order_qty_before": total_before,
            "order_qty_after": total_after,
            "delta": total_after - total_before,
        },
        "before": _df_to_records(before_df),
        "after": _df_to_records(after_df),
        "comparison": _df_to_records(comparison_df),
    }


@app.get("/api/backtest", tags=["Model & Impact"])
def get_backtest():
    """Returns 28-day holdout backtest results (NAIVE vs SMART policy comparison).

    Used by the React Model & Impact page.
    """
    out_path = os.path.join(OUTPUT_DIR, "backtest_results.csv")
    if not os.path.exists(out_path):
        raise HTTPException(
            status_code=404,
            detail="backtest_results.csv not found. Run: python -m src.inventory.backtest",
        )
    df = pd.read_csv(out_path)
    all_rows = df[df["product_id"] == "ALL"]
    naive_row = all_rows[all_rows["policy"] == "NAIVE"].iloc[0].to_dict() if not all_rows.empty else {}
    smart_row = all_rows[all_rows["policy"] == "SMART"].iloc[0].to_dict() if not all_rows.empty else {}

    return {
        "headline": {
            "naive": naive_row,
            "smart": smart_row,
        },
        "data": _df_to_records(df),
    }


@app.get("/api/alerts", tags=["Data"])
def get_alerts():
    """Returns unexpected demand spike alerts (from alerts.csv if available)."""
    path = os.path.join(DATA_DIR, "alerts.csv")
    if not os.path.exists(path):
        return {"data": [], "message": "No alerts.csv yet. Generated by Person 1."}
    df = pd.read_csv(path)
    return {"data": _df_to_records(df)}


@app.get("/api/accuracy", tags=["Model & Impact"])
def get_accuracy():
    """Returns model vs baseline accuracy metrics (docs/accuracy.csv)."""
    path = os.path.join("docs", "accuracy.csv")
    if not os.path.exists(path):
        return {"data": [], "message": "No accuracy.csv yet. Generated by Person 1."}
    df = pd.read_csv(path)
    return {"data": _df_to_records(df)}


@app.get("/api/categories", tags=["Data"])
def get_categories():
    """Returns distinct product categories for filter dropdowns."""
    p_df = _load_products()
    cats = sorted(p_df["category"].dropna().unique().tolist())
    return {"categories": cats}
