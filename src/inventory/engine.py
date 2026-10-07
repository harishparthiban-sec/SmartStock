"""Inventory Engine for SmartStock.

Computes replenishment order quantities, reorder points, stockout projections,
and scenario simulations based on demand forecasts.
"""
import math
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from statistics import NormalDist


def get_z_factor(service_level: float) -> float:
    """Computes normal distribution quantile Z = Phi^-1(service_level)."""
    return float(NormalDist().inv_cdf(service_level))


from src.inventory.config import (
    SERVICE_LEVEL,
    REVIEW_PERIOD_DAYS,
    ORDER_SOON_BUFFER_DAYS,
    OVERSTOCK_FACTOR,
    DEFAULT_SIGMA_PCT,
)
from src.inventory.explain import explain_status
from src.inventory.copilot import (
    generate_copilot_recommendations,
    evaluate_stockout_warning,
    evaluate_overstock_pricing,
)
from src.inventory.analog import load_analog_signals, get_analog_adjustments


def compute_reorder(
    products_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    error_df: Optional[pd.DataFrame] = None,
    service_level: float = SERVICE_LEVEL,
    review_period_days: int = REVIEW_PERIOD_DAYS,
    lead_time_extra_days: int = 0,
    sales_df: Optional[pd.DataFrame] = None,
    include_copilot: bool = False,
    holidays_df: Optional[pd.DataFrame] = None,
    future_promos_df: Optional[pd.DataFrame] = None,
    analog_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Computes reorder recommendations, safety stock, and status for each product.

    Args:
        products_df: DataFrame containing product metadata (A3 schema).
        forecast_df: DataFrame containing demand forecasts (A4 schema).
        error_df: DataFrame with holdout error metrics (product_id, sigma, mae, wape_pct).
        service_level: Desired cycle service level (e.g. 0.95 -> Z = 1.64485).
        review_period_days: Review period R in days (default 7).
        lead_time_extra_days: Extra supplier delay in days for scenario analysis.
        sales_df: Historical sales dataframe for recent demand benchmarking.
        analog_df: Optional DataFrame from data/demand_analog_summary.csv (Person 1's
                   Demand Time Machine output). When provided, analog signals are used
                   to: (a) increase `need` when analogs agree on growth, and
                   (b) inflate sigma when analogs conflict with the Prophet forecast.
                   The forecast CSV (yhat) is NEVER modified.

    Returns:
        DataFrame with columns matching output/orders.csv schema (17 columns).
        Output contract is identical with or without analog_df.
    """
    if products_df.empty or forecast_df.empty:
        return pd.DataFrame(
            columns=[
                "product_id",
                "name",
                "category",
                "current_stock",
                "on_order",
                "avg_daily_demand",
                "lead_time_days",
                "safety_stock",
                "reorder_point",
                "order_qty",
                "order_by_date",
                "expected_arrival_date",
                "days_of_stock_left",
                "stockout_date",
                "status",
                "reason",
                "order_value",
            ]
        )

    # Pre-parse error lookup
    error_lookup = {}
    if error_df is not None and not error_df.empty:
        for _, row in error_df.iterrows():
            error_lookup[str(row["product_id"])] = float(row["sigma"])

    # Pre-process sales for recent 28-day benchmark if supplied
    sales_benchmark = {}
    if sales_df is not None and not sales_df.empty:
        # Determine simulation as-of date (first date in forecast)
        first_forecast_date = pd.to_datetime(forecast_df["date"]).min()
        sales_copy = sales_df.copy()
        sales_copy["parsed_date"] = pd.to_datetime(sales_copy["date"])
        cutoff_start = first_forecast_date - timedelta(days=28)
        recent_sales = sales_copy[
            (sales_copy["parsed_date"] >= cutoff_start)
            & (sales_copy["parsed_date"] < first_forecast_date)
        ]
        if not recent_sales.empty:
            mean_by_prod = recent_sales.groupby("product_id")["units_sold"].mean()
            for pid, val in mean_by_prod.items():
                sales_benchmark[str(pid)] = float(val)

    # Standard normal quantile Z
    z_val = get_z_factor(service_level)

    # Load Demand Time Machine analog signals (safe: returns {} if file missing)
    # analog_df=None  → auto-detect real or stub file from disk
    # analog_df=pd.DataFrame()  → explicit "no analog" (used in tests for isolation)
    # analog_df=<real data>  → parse directly
    _analog_explicitly_passed = analog_df is not None
    if _analog_explicitly_passed and len(analog_df.columns) > 0 and len(analog_df) > 0:
        # Parse directly from the passed-in DataFrame
        from src.inventory.analog import AnalogSignal
        analog_signals: dict = {}
        for _, arow in analog_df.iterrows():
            try:
                pid_a = str(arow["product_id"])
                analog_signals[pid_a] = AnalogSignal(
                    product_id=pid_a,
                    growth_pct=float(arow.get("top_3_consensus_growth_pct", 0.0) or 0.0),
                    confidence=float(arow.get("analog_confidence", 0.0) or 0.0),
                    agreement=float(arow.get("analog_agreement", 0.0) or 0.0),
                    event_alignment=float(arow.get("event_alignment", 0.0) or 0.0),
                    forecast_agreement=float(arow.get("forecast_agreement", 1.0) or 1.0),
                    similarity=float(arow.get("best_similarity_score", 0.0) or 0.0),
                    historical_evidence=str(arow.get("historical_evidence", "") or ""),
                )
            except (ValueError, TypeError):
                continue
    elif _analog_explicitly_passed:
        # Caller passed an empty DataFrame → explicitly disable analog (e.g., tests)
        analog_signals = {}
    else:
        analog_signals = load_analog_signals()  # auto-detects real or stub path

    # Pre-group forecast by product_id
    f_grouped = {}
    for pid, group in forecast_df.groupby("product_id"):
        sorted_g = group.sort_values("date").reset_index(drop=True)
        f_grouped[str(pid)] = sorted_g

    records = []

    for _, prod_row in products_df.iterrows():
        pid = str(prod_row["product_id"])
        name = str(prod_row["name"])
        category = str(prod_row["category"])
        current_stock = int(prod_row["current_stock"])
        on_order = int(prod_row["on_order"])
        unit_cost = float(prod_row["unit_cost"])
        base_lead_time = int(prod_row["lead_time_days"])

        # Edge case: product not in forecast
        if pid not in f_grouped or f_grouped[pid].empty:
            continue

        p_forecast = f_grouped[pid]
        horizon_len = len(p_forecast)
        dates_list = [str(d)[:10] for d in p_forecast["date"]]
        yhat_list = p_forecast["yhat"].astype(float).values

        as_of_date_str = dates_list[0]
        as_of_dt = datetime.strptime(as_of_date_str, "%Y-%m-%d")

        # Effective Lead Time L and Review Period R
        L = max(1, base_lead_time + lead_time_extra_days)
        R = max(1, review_period_days)

        # Slice demand over L and L + R (use whole forecast if horizon is shorter)
        days_L = min(L, horizon_len)
        days_LR = min(L + R, horizon_len)

        demand_LT = float(np.sum(yhat_list[:days_L]))
        need = float(np.sum(yhat_list[:days_LR]))
        d = (demand_LT / days_L) if days_L > 0 else 0.0

        # Forecast error sigma
        if pid in error_lookup and not np.isnan(error_lookup[pid]):
            sigma = error_lookup[pid]
        else:
            sigma = DEFAULT_SIGMA_PCT * d

        # ---- Demand Time Machine analog adjustments (Person 1 integration) ----
        # get_analog_adjustments is a pure function; returns unmodified values
        # when no analog signal is available for this product.
        adj_sigma, adj_need, analog_context, is_analog_conflict = get_analog_adjustments(
            pid=pid,
            signals=analog_signals,
            base_sigma=sigma,
            base_need=need,
        )
        # Only apply analog adjustments; base demand_LT and forecast CSV untouched
        sigma = adj_sigma   # may be inflated on conflict
        need = adj_need     # may be increased on strong growth signal
        # -----------------------------------------------------------------------

        # Safety Stock & Reorder Point
        SS = z_val * sigma * math.sqrt(L)
        ROP_unrounded = demand_LT + SS
        ROP = int(math.ceil(ROP_unrounded))
        IP = current_stock + on_order

        # Status check in exact priority order (A6)
        if IP <= ROP_unrounded:
            status = "ORDER NOW"
        elif IP <= (ROP_unrounded + ORDER_SOON_BUFFER_DAYS * d):
            status = "ORDER SOON"
        elif IP > (OVERSTOCK_FACTOR * need):
            status = "OVERSTOCK"
        else:
            status = "OK"

        # Order quantity & value
        raw_order_qty = need + SS - IP
        if status in ("ORDER NOW", "ORDER SOON"):
            order_qty = int(math.ceil(max(0.0, raw_order_qty)))
        else:
            order_qty = 0

        order_value = round(order_qty * unit_cost, 2)

        # Walk day-by-day to determine stockout_date & days_of_stock_left
        # On-hand = current_stock - cum_demand, on_order added from day L onward
        stockout_date = ""
        days_of_stock_left = float(horizon_len)
        cum_demand = 0.0

        for t in range(horizon_len):
            daily_d = yhat_list[t]
            pipeline_incoming = on_order if t >= L else 0
            on_hand_before_day = (current_stock + pipeline_incoming) - cum_demand

            # Stock at end of day t
            cum_demand += daily_d
            on_hand_end_day = (current_stock + pipeline_incoming) - cum_demand

            if on_hand_end_day < 0:
                stockout_date = dates_list[t]
                if daily_d > 0 and on_hand_before_day > 0:
                    fractional = min(1.0, max(0.0, on_hand_before_day / daily_d))
                    days_of_stock_left = round(t + fractional, 1)
                else:
                    days_of_stock_left = round(float(t), 1)
                break

        # Order by date & expected arrival date
        order_by_date = ""
        expected_arrival_date = ""

        if IP <= ROP_unrounded:
            order_by_date = as_of_date_str
            arrival_dt = as_of_dt + timedelta(days=L)
            expected_arrival_date = arrival_dt.strftime("%Y-%m-%d")
        else:
            cum_ip_demand = 0.0
            for t in range(horizon_len):
                cum_ip_demand += yhat_list[t]
                if (IP - cum_ip_demand) <= ROP_unrounded:
                    order_by_date = dates_list[t]
                    order_by_dt = datetime.strptime(order_by_date, "%Y-%m-%d")
                    arrival_dt = order_by_dt + timedelta(days=L)
                    expected_arrival_date = arrival_dt.strftime("%Y-%m-%d")
                    break

        # Benchmark demand comparison
        demand_vs_recent_pct = None
        if pid in sales_benchmark and sales_benchmark[pid] > 0:
            demand_vs_recent_pct = (
                (d - sales_benchmark[pid]) / sales_benchmark[pid]
            ) * 100.0

        # Plain-English explanation
        reason = explain_status(
            status=status,
            ip=float(IP),
            days_left=days_of_stock_left,
            lead_time=L,
            need_days=L + R,
            need=need,
            order_qty=order_qty,
            rop=ROP,
            order_by_date=order_by_date,
            arrival_date=expected_arrival_date,
            demand_vs_recent_pct=demand_vs_recent_pct,
        )
        # Append Demand Time Machine context when available
        if analog_context:
            reason = f"{reason} [{analog_context}]"

        records.append(
            {
                "product_id": pid,
                "name": name,
                "category": category,
                "current_stock": current_stock,
                "on_order": on_order,
                "avg_daily_demand": round(d, 2),
                "lead_time_days": L,
                "safety_stock": round(SS, 2),
                "reorder_point": ROP,
                "order_qty": order_qty,
                "order_by_date": order_by_date,
                "expected_arrival_date": expected_arrival_date,
                "days_of_stock_left": days_of_stock_left,
                "stockout_date": stockout_date,
                "status": status,
                "reason": reason,
                "order_value": order_value,
            }
        )

    base_df = pd.DataFrame(records)
    if include_copilot:
        return generate_copilot_recommendations(
            orders_df=base_df,
            forecast_df=forecast_df,
            holidays_df=holidays_df,
            future_promos_df=future_promos_df,
        )
    return base_df


def get_copilot_recommendations(
    orders_df: pd.DataFrame,
    forecast_df: Optional[pd.DataFrame] = None,
    holidays_df: Optional[pd.DataFrame] = None,
    future_promos_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Enriches an orders DataFrame with AI Reorder Copilot recommendations."""
    return generate_copilot_recommendations(
        orders_df=orders_df,
        forecast_df=forecast_df,
        holidays_df=holidays_df,
        future_promos_df=future_promos_df,
    )


def simulate_scenario(
    forecast_df: pd.DataFrame,
    uplift_pct: float,
    start_date: str,
    end_date: str,
    product_ids: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Simulate a what-if scenario by applying percentage demand uplift to forecast rows.

    Args:
        forecast_df: Original demand forecast DataFrame.
        uplift_pct: Uplift percentage (e.g. 20 for +20%, -30 for -30%).
        start_date: Scenario start date (YYYY-MM-DD or datetime).
        end_date: Scenario end date (YYYY-MM-DD or datetime).
        product_ids: List of product IDs to affect. None means all products.

    Returns:
        A new DataFrame with adjusted forecast numbers, keeping input dataframe untouched.
    """
    sim_df = forecast_df.copy(deep=True)
    if sim_df.empty:
        return sim_df

    start_str = str(start_date)[:10]
    end_str = str(end_date)[:10]

    date_series = sim_df["date"].astype(str).str[:10]
    date_mask = (date_series >= start_str) & (date_series <= end_str)

    if product_ids is not None:
        p_set = set(str(pid) for pid in product_ids)
        prod_mask = sim_df["product_id"].astype(str).isin(p_set)
        apply_mask = date_mask & prod_mask
    else:
        apply_mask = date_mask

    multiplier = max(0.0, 1.0 + (uplift_pct / 100.0))

    sim_df.loc[apply_mask, "yhat"] = np.round(
        np.maximum(0.0, sim_df.loc[apply_mask, "yhat"] * multiplier), 1
    )
    sim_df.loc[apply_mask, "yhat_lower"] = np.round(
        np.maximum(0.0, sim_df.loc[apply_mask, "yhat_lower"] * multiplier), 1
    )
    sim_df.loc[apply_mask, "yhat_upper"] = np.round(
        np.maximum(0.0, sim_df.loc[apply_mask, "yhat_upper"] * multiplier), 1
    )

    return sim_df


def run_scenario(
    products_df: pd.DataFrame,
    forecast_df: pd.DataFrame,
    error_df: Optional[pd.DataFrame],
    uplift_pct: float,
    start_date: str,
    end_date: str,
    product_ids: Optional[List[str]] = None,
    lead_time_extra_days: int = 0,
    service_level: float = SERVICE_LEVEL,
    review_period_days: int = REVIEW_PERIOD_DAYS,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Runs a complete what-if scenario comparing baseline vs simulated reorders.

    Args:
        products_df: Product metadata DataFrame.
        forecast_df: Baseline forecast DataFrame.
        error_df: Forecast error metrics DataFrame.
        uplift_pct: Demand change percentage.
        start_date: Scenario start date string.
        end_date: Scenario end date string.
        product_ids: List of affected product IDs, or None for all.
        lead_time_extra_days: Additional supplier delay days in scenario.
        service_level: Target cycle service level.
        review_period_days: Review cycle in days.

    Returns:
        Tuple of (before_df, after_df, comparison_df).
    """
    # 1. Baseline compute (normal lead time, zero extra delay)
    before_df = compute_reorder(
        products_df=products_df,
        forecast_df=forecast_df,
        error_df=error_df,
        service_level=service_level,
        review_period_days=review_period_days,
        lead_time_extra_days=0,
    )

    # 2. Simulate forecast changes
    sim_forecast = simulate_scenario(
        forecast_df=forecast_df,
        uplift_pct=uplift_pct,
        start_date=start_date,
        end_date=end_date,
        product_ids=product_ids,
    )

    # 3. Compute simulated orders with extra lead time delay
    after_df = compute_reorder(
        products_df=products_df,
        forecast_df=sim_forecast,
        error_df=error_df,
        service_level=service_level,
        review_period_days=review_period_days,
        lead_time_extra_days=lead_time_extra_days,
    )

    # 4. Build comparison dataframe
    # Schema: product_id, name, order_qty_before, order_qty_after, delta, status_before, status_after
    merged = pd.merge(
        before_df[["product_id", "name", "order_qty", "status"]],
        after_df[["product_id", "order_qty", "status"]],
        on="product_id",
        suffixes=("_before", "_after"),
    )

    merged["delta"] = merged["order_qty_after"] - merged["order_qty_before"]
    comparison_df = merged[
        [
            "product_id",
            "name",
            "order_qty_before",
            "order_qty_after",
            "delta",
            "status_before",
            "status_after",
        ]
    ]

    return before_df, after_df, comparison_df


if __name__ == "__main__":
    import os
    import sys

    # Look for real data files or fall back to test fixtures
    data_dir = "data"
    fixtures_dir = os.path.join("tests", "fixtures")

    products_path = (
        os.path.join(data_dir, "products.csv")
        if os.path.exists(os.path.join(data_dir, "products.csv"))
        else os.path.join(fixtures_dir, "products_stub.csv")
    )
    forecast_path = (
        os.path.join(data_dir, "forecast.csv")
        if os.path.exists(os.path.join(data_dir, "forecast.csv"))
        else os.path.join(fixtures_dir, "forecast_stub.csv")
    )
    error_path = (
        os.path.join(data_dir, "forecast_error.csv")
        if os.path.exists(os.path.join(data_dir, "forecast_error.csv"))
        else os.path.join(fixtures_dir, "error_stub.csv")
    )
    sales_path = (
        os.path.join(data_dir, "sales.csv")
        if os.path.exists(os.path.join(data_dir, "sales.csv"))
        else None
    )

    holidays_path = os.path.join(data_dir, "holidays.csv")
    promos_path = os.path.join(data_dir, "future_promos.csv")
    h_df = pd.read_csv(holidays_path) if os.path.exists(holidays_path) else None
    fp_df = pd.read_csv(promos_path) if os.path.exists(promos_path) else None

    print(f"Loading products from: {products_path}")
    print(f"Loading forecast from: {forecast_path}")
    print(f"Loading error metrics from: {error_path}")

    p_df = pd.read_csv(products_path)
    f_df = pd.read_csv(forecast_path)
    e_df = pd.read_csv(error_path) if os.path.exists(error_path) else None
    s_df = pd.read_csv(sales_path) if sales_path and os.path.exists(sales_path) else None

    # Load Demand Time Machine analog summary (Person 1 output)
    analog_real = os.path.join(data_dir, "demand_analog_summary.csv")
    analog_stub = os.path.join(fixtures_dir, "demand_analog_summary_stub.csv")
    if os.path.exists(analog_real):
        a_df = pd.read_csv(analog_real)
        print(f"Loading analog signals from: {analog_real}")
    elif os.path.exists(analog_stub):
        a_df = pd.read_csv(analog_stub)
        print(f"Loading analog signals from stub: {analog_stub}")
    else:
        a_df = None
        print("No demand_analog_summary.csv found – running without analog signals.")

    # Compute base orders with exact 17 columns
    orders = compute_reorder(
        products_df=p_df,
        forecast_df=f_df,
        error_df=e_df,
        sales_df=s_df,
        include_copilot=False,
        analog_df=a_df,
    )

    os.makedirs("output", exist_ok=True)
    out_file = os.path.join("output", "orders.csv")
    orders.to_csv(out_file, index=False)
    out_json = os.path.join("output", "orders.json")
    orders.to_json(out_json, orient="records", indent=2)
    print(f"\nSuccessfully generated {out_file} and {out_json} ({len(orders)} rows).")

    # Generate enriched AI Reorder Copilot & Early Warning recommendations
    copilot_df = get_copilot_recommendations(
        orders_df=orders,
        forecast_df=f_df,
        holidays_df=h_df,
        future_promos_df=fp_df,
    )
    copilot_file = os.path.join("output", "copilot_recommendations.csv")
    copilot_df.to_csv(copilot_file, index=False)
    copilot_json = os.path.join("output", "copilot_recommendations.json")
    copilot_df.to_json(copilot_json, orient="records", indent=2)
    print(f"Successfully generated {copilot_file} and {copilot_json} ({len(copilot_df)} rows).")

    print("\n--- Status Counts ---")
    print(orders["status"].value_counts())

    print("\n--- AI Reorder Copilot Urgent Highlights ---")
    urgent_items = copilot_df[copilot_df["urgency"].isin(["CRITICAL", "HIGH"])]
    if not urgent_items.empty:
        print(
            urgent_items[
                ["product_id", "name", "urgency", "copilot_action", "order_qty", "copilot_reason"]
            ].to_string(index=False)
        )
    else:
        print("No urgent reorder alerts at this time.")

    print("\n--- Dynamic Pricing / Overstock Recommendations ---")
    overstock_items = copilot_df[copilot_df["status"] == "OVERSTOCK"]
    if not overstock_items.empty:
        print(
            overstock_items[
                ["product_id", "name", "pricing_recommendation", "excess_units", "pricing_reason"]
            ].to_string(index=False)
        )
    else:
        print("No overstocked products currently detected.")

    # Demand Time Machine analog summary
    if a_df is not None and not a_df.empty:
        from src.inventory.analog import load_analog_signals as _la
        import tempfile as _tf, os as _os2
        with _tf.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as _t:
            a_df.to_csv(_t.name, index=False)
            _sigs = _la(_t.name)
        _os2.unlink(_t.name)
        print("\n--- Demand Time Machine Analog Signal Summary ---")
        for pid, sig in _sigs.items():
            tag = "CONFLICT" if sig.is_conflict else ("UPLIFT" if sig.has_meaningful_growth and sig.is_high_quality else "AGREE")
            print(f"  {pid}: [{tag}] growth={sig.growth_pct:.1f}% "
                  f"confidence={sig.confidence:.2f} "
                  f"forecast_agreement={sig.forecast_agreement:.2f} "
                  f"uplift_factor={sig.demand_uplift_factor():.3f} "
                  f"sigma_factor={sig.sigma_inflate_factor():.2f}")

