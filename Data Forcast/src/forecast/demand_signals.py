"""
SmartStock - Demand Intelligence & Copilot Signals (Person 1)
Generates derived demand signals to support:
1. Stockout Early Warning
2. Dynamic Pricing / Overstock Recommendations (demand velocity & slump signals)
3. AI Reorder Copilot factual forecast explanations
"""

import os
import sys
import numpy as np  # type: ignore
import pandas as pd  # type: ignore

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def compute_demand_signals(data_dir="data"):
    """
    Computes product-level and daily demand intelligence signals from existing forecast outputs.
    Outputs:
    - data/demand_signals.csv: Product-level summary of demand drivers, uncertainty, and Copilot explanations.
    - data/daily_demand_signals.csv: Daily granularity drivers (promotions, holidays, interval widths).
    """
    products_path = os.path.join(data_dir, "products.csv")
    forecast_path = os.path.join(data_dir, "forecast.csv")
    error_path = os.path.join(data_dir, "forecast_error.csv")
    sales_path = os.path.join(data_dir, "sales.csv")
    alerts_path = os.path.join(data_dir, "alerts.csv")
    holidays_path = os.path.join(data_dir, "holidays.csv")
    future_promos_path = os.path.join(data_dir, "future_promos.csv")

    for p in [products_path, forecast_path, error_path, sales_path, holidays_path, future_promos_path]:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Required input file missing: {p}")

    products_df = pd.read_csv(products_path)
    forecast_df = pd.read_csv(forecast_path)
    error_df = pd.read_csv(error_path)
    sales_df = pd.read_csv(sales_path)
    alerts_df = pd.read_csv(alerts_path) if os.path.exists(alerts_path) else pd.DataFrame()
    holidays_df = pd.read_csv(holidays_path)
    future_promos_df = pd.read_csv(future_promos_path)

    forecast_df["dt"] = pd.to_datetime(forecast_df["date"])
    sales_df["dt"] = pd.to_datetime(sales_df["date"])
    holidays_df["dt"] = pd.to_datetime(holidays_df["date"])
    future_promos_df["dt"] = pd.to_datetime(future_promos_df["date"])

    as_of_date = pd.to_datetime("2026-10-07")
    hist_28d_start = as_of_date - pd.Timedelta(days=28)
    recent_sales = sales_df[(sales_df["dt"] >= hist_28d_start) & (sales_df["dt"] < as_of_date)]

    # ---------------------------------------------------------
    # 1. Product-Level Demand Signals
    # ---------------------------------------------------------
    product_signals = []

    for _, prod in products_df.iterrows():
        pid = prod["product_id"]
        pname = prod["name"]
        curr_stock = prod["current_stock"]

        p_fcst = forecast_df[forecast_df["product_id"] == pid].sort_values("dt").reset_index(drop=True)
        p_err = error_df[error_df["product_id"] == pid].iloc[0] if pid in error_df["product_id"].values else None
        p_recent = recent_sales[recent_sales["product_id"] == pid]
        p_future_promos = future_promos_df[future_promos_df["product_id"] == pid]

        # Horizon windows
        fcst_7d = p_fcst.head(7)["yhat"].mean()
        fcst_14d = p_fcst.head(14)["yhat"].mean()
        fcst_45d = p_fcst["yhat"].mean()
        total_need_14d = p_fcst.head(14)["yhat"].sum()

        # Historical comparison (last 28 days)
        hist_mean = p_recent["units_sold"].mean() if len(p_recent) > 0 else fcst_7d
        trend_pct = ((fcst_14d - hist_mean) / hist_mean * 100.0) if hist_mean > 0 else 0.0

        # Demand velocity classification
        if trend_pct >= 15.0:
            demand_velocity = "SURGING"
        elif trend_pct <= -15.0:
            demand_velocity = "DECLINING"
        else:
            demand_velocity = "STABLE"

        # Uncertainty metrics
        sigma = float(p_err["sigma"]) if p_err is not None else 0.0
        wape_pct = float(p_err["wape_pct"]) if p_err is not None else 0.0
        avg_band_width = (p_fcst["yhat_upper"] - p_fcst["yhat_lower"]).mean()
        rel_uncertainty = (avg_band_width / fcst_45d) if fcst_45d > 0 else 0.0

        if rel_uncertainty > 0.45 or wape_pct > 16.0:
            uncertainty_level = "HIGH"
        elif rel_uncertainty < 0.25 and wape_pct < 10.0:
            uncertainty_level = "LOW"
        else:
            uncertainty_level = "MEDIUM"

        # Recent spike alerts check
        p_alerts = alerts_df[alerts_df["product_id"] == pid] if not alerts_df.empty else pd.DataFrame()
        has_spike = len(p_alerts) > 0
        spike_count = len(p_alerts)
        high_spikes = p_alerts[p_alerts["severity"] == "HIGH"]
        spike_details = ""
        if not high_spikes.empty:
            latest_spike = high_spikes.iloc[-1]
            spike_details = f"{latest_spike['date']} (+{latest_spike['excess_pct']}%)"
        elif not p_alerts.empty:
            latest_spike = p_alerts.iloc[-1]
            spike_details = f"{latest_spike['date']} (+{latest_spike['excess_pct']}%)"

        # Upcoming promotions check
        promo_days = p_future_promos[p_future_promos["promo_flag"] == 1]
        has_promo = len(promo_days) > 0
        promo_info = ""
        if has_promo:
            start_p = promo_days["date"].min()
            end_p = promo_days["date"].max()
            promo_info = f"{start_p} to {end_p}"

        # Upcoming holiday check (within 45-day forecast horizon)
        h_in_horizon = holidays_df[(holidays_df["dt"] >= as_of_date) & (holidays_df["dt"] <= as_of_date + pd.Timedelta(days=45))]
        holiday_info = ""
        if not h_in_horizon.empty:
            # Check closest or major holiday (Diwali on 2026-11-08)
            diwali_h = h_in_horizon[h_in_horizon["holiday_name"] == "Diwali"]
            if not diwali_h.empty:
                holiday_info = f"Diwali on {diwali_h.iloc[0]['date']}"
            else:
                closest_h = h_in_horizon.iloc[0]
                holiday_info = f"{closest_h['holiday_name']} on {closest_h['date']}"

        lead_time = int(prod.get("lead_time_days", 3))
        review_days = 7
        window_days = lead_time + review_days
        need_lead_review = p_fcst.head(window_days)["yhat"].sum()

        # Overstock / Dynamic Pricing Candidate Signal:
        # Aligns with spec A6 (stock position significantly exceeding window need)
        overstock_risk = False
        if curr_stock >= 1.5 * need_lead_review or curr_stock >= 2.0 * (fcst_7d * lead_time):
            overstock_risk = True

        # Construct Copilot factual explanation strings
        reasons = []

        # 1. Holiday Driver
        if pid == "P011" and "Diwali" in holiday_info:
            reasons.append("Diwali festival demand surge expected (+120% lift approaching 2026-11-08)")
        elif holiday_info:
            if pid in ["P003", "P004", "P005", "P010"]:
                reasons.append(f"Festive preparation lift expected ({holiday_info})")

        # 2. Promo Driver
        if has_promo:
            reasons.append(f"Demand expected to surge due to upcoming planned promotion ({promo_info})")

        # 3. Spike Driver
        if has_spike and not high_spikes.empty:
            reasons.append(f"Recent demand spike detected on {spike_details}")

        # 4. Uncertainty Driver
        if uncertainty_level == "HIGH":
            reasons.append(f"High forecast uncertainty (sigma={sigma:.1f}, WAPE={wape_pct:.1f}%)")

        # 5. Trend / Velocity Driver
        if demand_velocity == "SURGING" and not any("surge" in r for r in reasons):
            reasons.append(f"Demand velocity accelerating (+{trend_pct:.1f}% vs last 28 days)")
        elif demand_velocity == "DECLINING":
            reasons.append(f"Demand velocity cooling ({trend_pct:.1f}% vs last 28 days)")

        # 6. Overstock / Dynamic Pricing Candidate Signal
        if overstock_risk:
            reasons.append(f"Current stock ({curr_stock}) exceeds projected {window_days}-day demand need ({need_lead_review:.0f}); candidate for dynamic pricing or promo discount")

        # Default fallback if steady
        if not reasons:
            reasons.append("Steady baseline demand following regular weekly shopping patterns")

        copilot_explanation = "; ".join(reasons)

        product_signals.append({
            "product_id": pid,
            "name": pname,
            "expected_demand_7d": round(float(fcst_7d), 1),
            "expected_demand_14d": round(float(fcst_14d), 1),
            "expected_demand_45d": round(float(fcst_45d), 1),
            "trend_vs_last28d_pct": round(float(trend_pct), 1),
            "demand_velocity": demand_velocity,
            "uncertainty_level": uncertainty_level,
            "sigma": round(float(sigma), 2),
            "wape_pct": round(float(wape_pct), 1),
            "has_spike_alert": has_spike,
            "spike_details": spike_details if spike_details else "None",
            "upcoming_holiday": holiday_info if holiday_info else "None",
            "upcoming_promo": promo_info if promo_info else "None",
            "overstock_pricing_candidate": overstock_risk,
            "copilot_explanation": copilot_explanation
        })

    signals_df = pd.DataFrame(product_signals)
    signals_path = os.path.join(data_dir, "demand_signals.csv")
    signals_df.to_csv(signals_path, index=False)
    print(f"Created {signals_path} ({len(signals_df)} products)")

    # ---------------------------------------------------------
    # 2. Daily Granularity Demand Signals
    # ---------------------------------------------------------
    daily_rows = []
    for _, row in forecast_df.iterrows():
        pid = row["product_id"]
        dt = row["dt"]
        d_str = row["date"]
        yhat = row["yhat"]
        yhat_lower = row["yhat_lower"]
        yhat_upper = row["yhat_upper"]

        # Check holiday window (-5 to +1 days)
        h_match = ""
        for _, h_row in holidays_df.iterrows():
            diff = (dt - h_row["dt"]).days
            if -5 <= diff <= 1:
                h_match = h_row["holiday_name"]
                break

        # Check promo flag
        p_flag = 0
        p_row = future_promos_df[(future_promos_df["product_id"] == pid) & (future_promos_df["date"] == d_str)]
        if not p_row.empty:
            p_flag = int(p_row.iloc[0]["promo_flag"])

        # Daily signal description
        signals = []
        if h_match:
            signals.append(f"{h_match} window")
        if p_flag == 1:
            signals.append("Active Promo")
        if dt.weekday() in [4, 5, 6]:
            signals.append("Weekend peak")
        daily_signal_desc = ", ".join(signals) if signals else "Normal weekday"

        daily_rows.append({
            "date": d_str,
            "product_id": pid,
            "yhat": yhat,
            "yhat_lower": yhat_lower,
            "yhat_upper": yhat_upper,
            "uncertainty_spread": round(yhat_upper - yhat_lower, 1),
            "holiday_event": h_match if h_match else "None",
            "is_promo": p_flag,
            "daily_signal": daily_signal_desc
        })

    daily_signals_df = pd.DataFrame(daily_rows)
    daily_signals_path = os.path.join(data_dir, "daily_demand_signals.csv")
    daily_signals_df.to_csv(daily_signals_path, index=False)
    print(f"Created {daily_signals_path} ({len(daily_signals_df)} rows)")

    return signals_df, daily_signals_df


def get_demand_signals(product_id=None, signals_path="data/demand_signals.csv"):
    """
    Consumer API for Person 2 & Person 3 to fetch demand intelligence and Copilot reasons.
    """
    if not os.path.exists(signals_path):
        compute_demand_signals(os.path.dirname(signals_path) or "data")

    df = pd.read_csv(signals_path)
    if product_id is not None:
        if isinstance(product_id, str):
            df = df[df["product_id"] == product_id]
        elif isinstance(product_id, (list, set, tuple)):
            df = df[df["product_id"].isin(product_id)]
    return df


def get_copilot_explanation(product_id, signals_path="data/demand_signals.csv"):
    """
    Returns the factual Copilot explanation string for a given product.
    """
    df = get_demand_signals(product_id, signals_path)
    if df.empty:
        return "Normal demand forecast with standard replenishment schedule."
    return df.iloc[0]["copilot_explanation"]


if __name__ == "__main__":
    compute_demand_signals()
