"""Backtesting module for SmartStock.

Simulates and compares inventory replenishment under two policies over the 28-day
holdout period (2026-09-09 to 2026-10-06):
1. NAIVE policy: Simple historical 30-day moving average heuristics (ROP = 5m, order to 12m).
2. SMART policy: Dynamic forecast-aware reorder points with safety stock (ROP_t = sum(yhat_L) + SS).
"""
import math
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from statistics import NormalDist


def get_z_factor(service_level: float) -> float:
    """Computes normal distribution quantile Z = Phi^-1(service_level)."""
    return float(NormalDist().inv_cdf(service_level))


from src.inventory.config import REVIEW_PERIOD_DAYS, SERVICE_LEVEL


def simulate_single_product_policy(
    lead_time: int,
    actual_units: List[float],
    forecast_units: List[float],
    policy: str,
    sigma: float = 0.0,
    m_naive: float = 0.0,
    service_level: float = SERVICE_LEVEL,
    review_period_days: int = REVIEW_PERIOD_DAYS,
) -> Dict[str, float]:
    """Simulates 28 days of inventory operations for a single product under a specified policy.

    Args:
        lead_time: Supplier lead time in days (L).
        actual_units: Daily actual demand realization over the 28 holdout days.
        forecast_units: Pre-computed daily forecast (yhat) for the 28 holdout days.
        policy: 'NAIVE' or 'SMART'.
        sigma: Forecast standard error (used for SMART policy safety stock).
        m_naive: Mean daily sales over 30 days prior to holdout window.
        service_level: Target cycle service level (default 0.95).
        review_period_days: Review period R in days (default 7).

    Returns:
        Dictionary with stockout_days, units_short, fill_rate_pct, avg_on_hand_units.
    """
    H = len(actual_units)
    L = lead_time
    R = review_period_days

    # Initial on-hand inventory: round((L + R) * mean yhat of the window)
    mean_yhat = float(np.mean(forecast_units)) if len(forecast_units) > 0 else m_naive
    on_hand = float(round((L + R) * mean_yhat))

    # Pipeline tracking: list of dicts: {'arrival_day': int, 'qty': int}
    pipeline: List[Dict[str, float]] = []

    total_demand = 0.0
    total_sold = 0.0
    units_short = 0.0
    stockout_days = 0
    daily_on_hand: List[float] = []

    # Z-factor and safety stock for SMART policy
    z_val = get_z_factor(service_level)
    SS = z_val * sigma * math.sqrt(L)

    for t in range(H):
        # 1. Add any orders arriving today
        arrived_qty = sum(order["qty"] for order in pipeline if order["arrival_day"] == t)
        on_hand += arrived_qty

        # 2. Demand happens
        demand = float(actual_units[t])
        total_demand += demand

        sold = min(on_hand, demand)
        shortage = demand - sold

        total_sold += sold
        units_short += shortage
        if shortage > 0:
            stockout_days += 1

        on_hand -= sold
        daily_on_hand.append(max(0.0, on_hand))

        # 3. End of day: compute IP = on_hand + pipeline
        pending_pipeline = sum(
            order["qty"] for order in pipeline if order["arrival_day"] > t
        )
        IP = on_hand + pending_pipeline

        # Decide order
        if policy == "NAIVE":
            rop_naive = 5.0 * m_naive
            if IP <= rop_naive:
                raw_qty = 12.0 * m_naive - IP
                order_qty = int(math.ceil(max(0.0, raw_qty)))
                if order_qty > 0:
                    pipeline.append({"arrival_day": t + L, "qty": order_qty})

        elif policy == "SMART":
            # Forecast remaining days after day t: indices from t + 1 onwards
            days_remaining = H - (t + 1)
            # Skip ordering when fewer than L forecast days remain
            if days_remaining >= L:
                next_L_slice = forecast_units[t + 1 : t + 1 + L]
                next_LR_slice = forecast_units[t + 1 : min(H, t + 1 + L + R)]

                sum_next_L = float(np.sum(next_L_slice))
                sum_next_LR = float(np.sum(next_LR_slice))

                rop_smart = sum_next_L + SS
                if IP <= rop_smart:
                    raw_qty = sum_next_LR + SS - IP
                    order_qty = int(math.ceil(max(0.0, raw_qty)))
                    if order_qty > 0:
                        pipeline.append({"arrival_day": t + L, "qty": order_qty})

    fill_rate_pct = (
        round((total_sold / total_demand) * 100.0, 2) if total_demand > 0 else 100.0
    )
    avg_on_hand = round(float(np.mean(daily_on_hand)), 2) if daily_on_hand else 0.0

    return {
        "stockout_days": stockout_days,
        "units_short": round(units_short, 2),
        "fill_rate_pct": fill_rate_pct,
        "avg_on_hand_units": avg_on_hand,
    }


def run_backtest(
    products_df: pd.DataFrame,
    backtest_forecast_df: pd.DataFrame,
    sales_df: pd.DataFrame,
    error_df: Optional[pd.DataFrame] = None,
    service_level: float = SERVICE_LEVEL,
    review_period_days: int = REVIEW_PERIOD_DAYS,
) -> pd.DataFrame:
    """Runs the 28-day holdout simulation for both NAIVE and SMART policies across all products.

    Args:
        products_df: Products master catalog (Table A3).
        backtest_forecast_df: Forecast + actual units on holdout (Table A4).
        sales_df: Historical sales records (Table A4).
        error_df: Forecast errors (sigma per product).
        service_level: Target cycle service level.
        review_period_days: Review cycle in days.

    Returns:
        DataFrame matching output/backtest_results.csv schema (15 products x 2 policies + 2 ALL rows).
    """
    # Parse holdout dates
    bt_dates = pd.to_datetime(backtest_forecast_df["date"])
    holdout_start = bt_dates.min()
    prior_30_start = holdout_start - pd.Timedelta(days=30)

    # Pre-calculate 30-day prior average demand per product for NAIVE policy
    sales_copy = sales_df.copy()
    sales_copy["dt"] = pd.to_datetime(sales_copy["date"])
    prior_30_sales = sales_copy[
        (sales_copy["dt"] >= prior_30_start) & (sales_copy["dt"] < holdout_start)
    ]
    naive_m_lookup = prior_30_sales.groupby("product_id")["units_sold"].mean().to_dict()

    # Pre-calculate sigma lookup
    sigma_lookup = {}
    if error_df is not None and not error_df.empty:
        for _, r in error_df.iterrows():
            sigma_lookup[str(r["product_id"])] = float(r["sigma"])

    results = []

    for _, prod in products_df.iterrows():
        pid = str(prod["product_id"])
        lead_time = int(prod["lead_time_days"])

        # Filter holdout forecast & actuals for this product
        p_bt = backtest_forecast_df[
            backtest_forecast_df["product_id"] == pid
        ].sort_values("date")
        if p_bt.empty:
            continue

        actuals = p_bt["actual_units"].astype(float).tolist()
        forecasts = p_bt["yhat"].astype(float).tolist()

        m_naive = float(naive_m_lookup.get(pid, np.mean(actuals)))
        sigma = float(
            sigma_lookup.get(pid, np.std(np.array(actuals) - np.array(forecasts)))
        )

        for policy in ["NAIVE", "SMART"]:
            metrics = simulate_single_product_policy(
                lead_time=lead_time,
                actual_units=actuals,
                forecast_units=forecasts,
                policy=policy,
                sigma=sigma,
                m_naive=m_naive,
                service_level=service_level,
                review_period_days=review_period_days,
            )
            results.append(
                {
                    "product_id": pid,
                    "policy": policy,
                    "stockout_days": metrics["stockout_days"],
                    "units_short": metrics["units_short"],
                    "fill_rate_pct": metrics["fill_rate_pct"],
                    "avg_on_hand_units": metrics["avg_on_hand_units"],
                }
            )

    df_results = pd.DataFrame(results)

    # Compute ALL rows (totals / weighted averages)
    all_rows = []
    for policy in ["NAIVE", "SMART"]:
        p_sub = df_results[df_results["policy"] == policy]
        tot_stockout_days = int(p_sub["stockout_days"].sum())
        tot_units_short = round(float(p_sub["units_short"].sum()), 2)
        mean_on_hand = round(float(p_sub["avg_on_hand_units"].mean()), 2)

        # Overall fill rate across all units demanded in holdout
        all_actuals_sum = float(backtest_forecast_df["actual_units"].sum())
        all_sold = max(0.0, all_actuals_sum - tot_units_short)
        overall_fill_rate = (
            round((all_sold / all_actuals_sum) * 100.0, 2)
            if all_actuals_sum > 0
            else 100.0
        )

        all_rows.append(
            {
                "product_id": "ALL",
                "policy": policy,
                "stockout_days": tot_stockout_days,
                "units_short": tot_units_short,
                "fill_rate_pct": overall_fill_rate,
                "avg_on_hand_units": mean_on_hand,
            }
        )

    all_df = pd.DataFrame(all_rows)
    final_df = pd.concat([df_results, all_df], ignore_index=True)

    return final_df


if __name__ == "__main__":
    # Script entry point: loads real data and generates output/backtest_results.csv
    data_dir = "data"
    fixtures_dir = os.path.join("tests", "fixtures")

    p_path = (
        os.path.join(data_dir, "products.csv")
        if os.path.exists(os.path.join(data_dir, "products.csv"))
        else os.path.join(fixtures_dir, "products_stub.csv")
    )
    bt_path = (
        os.path.join(data_dir, "backtest_forecast.csv")
        if os.path.exists(os.path.join(data_dir, "backtest_forecast.csv"))
        else os.path.join(fixtures_dir, "backtest_forecast_stub.csv")
    )
    s_path = (
        os.path.join(data_dir, "sales.csv")
        if os.path.exists(os.path.join(data_dir, "sales.csv"))
        else os.path.join(fixtures_dir, "sales_stub.csv")
    )
    e_path = (
        os.path.join(data_dir, "forecast_error.csv")
        if os.path.exists(os.path.join(data_dir, "forecast_error.csv"))
        else os.path.join(fixtures_dir, "error_stub.csv")
    )

    print(f"Loading products from: {p_path}")
    print(f"Loading backtest forecast from: {bt_path}")
    print(f"Loading sales history from: {s_path}")

    p_df = pd.read_csv(p_path)
    bt_df = pd.read_csv(bt_path)
    s_df = pd.read_csv(s_path)
    e_df = pd.read_csv(e_path) if os.path.exists(e_path) else None

    results = run_backtest(p_df, bt_df, s_df, e_df)

    os.makedirs("output", exist_ok=True)
    out_csv = os.path.join("output", "backtest_results.csv")
    results.to_csv(out_csv, index=False)
    out_json = os.path.join("output", "backtest_results.json")
    results.to_json(out_json, orient="records", indent=2)
    print(f"\nSaved {out_csv} and {out_json} ({len(results)} rows).")

    # Print summary comparison for ALL
    naive_all = results[(results["product_id"] == "ALL") & (results["policy"] == "NAIVE")].iloc[0]
    smart_all = results[(results["product_id"] == "ALL") & (results["policy"] == "SMART")].iloc[0]

    shortage_reduction = naive_all["units_short"] - smart_all["units_short"]
    stockout_reduction = naive_all["stockout_days"] - smart_all["stockout_days"]

    print("\n================== BACKTEST HEADLINE SUMMARY ==================")
    print(f"NAIVE Policy  : Stockout Days = {naive_all['stockout_days']}, Units Short = {naive_all['units_short']:.1f}, Fill Rate = {naive_all['fill_rate_pct']}%, Avg On-Hand = {naive_all['avg_on_hand_units']:.1f}")
    print(f"SMART Policy  : Stockout Days = {smart_all['stockout_days']}, Units Short = {smart_all['units_short']:.1f}, Fill Rate = {smart_all['fill_rate_pct']}%, Avg On-Hand = {smart_all['avg_on_hand_units']:.1f}")
    print(f"Reduction in Units Short   : {shortage_reduction:.1f}")
    print(f"Reduction in Stockout Days : {stockout_reduction}")
    print("================================================================")
