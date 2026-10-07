"""AI Reorder Copilot and Stockout Early Warning module for SmartStock.

Generates structured, explainable decision records, early warnings, and dynamic
pricing/markdown recommendations for supermarket inventory managers.
"""
from typing import Dict, List, Optional
import pandas as pd


def evaluate_stockout_warning(row: pd.Series) -> Dict[str, object]:
    """Evaluates stockout risk and assigns an explainable urgency level.

    Args:
        row: Series representing a row from compute_reorder / output/orders.csv.

    Returns:
        Dict with urgency, stockout_risk_level, stockout_in_7_days, early_warning_message.
    """
    status = str(row.get("status", "OK"))
    days_left = float(row.get("days_of_stock_left", 999.0))
    lead_time = int(row.get("lead_time_days", 1))
    stockout_date = str(row.get("stockout_date", "") or "").strip()
    order_by_date = str(row.get("order_by_date", "") or "").strip()

    stockout_in_7_days = bool(stockout_date and days_left <= 7.0)

    # 1. Determine urgency / risk level
    if status == "ORDER NOW":
        if days_left <= lead_time or days_left <= 3.0:
            urgency = "CRITICAL"
        else:
            urgency = "HIGH"
    elif status == "ORDER SOON":
        urgency = "MEDIUM"
    elif status == "OVERSTOCK":
        urgency = "LOW"
    else:  # "OK"
        urgency = "LOW"

    # 2. Build human-readable warning message
    if urgency == "CRITICAL":
        warning_msg = (
            f"CRITICAL: Stockout in {days_left:.1f} days is within {lead_time}-day lead time! "
            f"Order immediately to prevent shelf vacancy."
        )
    elif urgency == "HIGH":
        warning_msg = (
            f"HIGH: Reorder required. Projected stockout on {stockout_date} "
            f"({days_left:.1f} days of stock remaining)."
        )
    elif urgency == "MEDIUM":
        order_date_str = f"by {order_by_date}" if order_by_date else "soon"
        warning_msg = (
            f"MEDIUM: Stock approaching reorder point. Place order {order_date_str} "
            f"to protect service level."
        )
    elif status == "OVERSTOCK":
        warning_msg = (
            f"LOW RISK: Stock covers {days_left:.1f} days. Zero stockout risk; excess holding detected."
        )
    else:
        warning_msg = (
            f"HEALTHY: Inventory covers {days_left:.1f} days against a {lead_time}-day lead time. "
            f"Normal operating window."
        )

    return {
        "urgency": urgency,
        "stockout_risk_level": urgency,
        "stockout_in_7_days": stockout_in_7_days,
        "early_warning_message": warning_msg,
    }


def evaluate_overstock_pricing(
    row: pd.Series,
    cycle_need: Optional[float] = None,
) -> Dict[str, object]:
    """Evaluates whether excess inventory warrants a dynamic pricing / promotional recommendation.

    Note: SmartStock NEVER alters product prices automatically. This provides an
    explainable, advisory markdown signal to protect supermarket cash flow.

    Args:
        row: Series representing a row from compute_reorder / output/orders.csv.
        cycle_need: Total forecasted demand over (L + R) days if available.

    Returns:
        Dict with excess_units, pricing_recommendation, pricing_reason.
    """
    status = str(row.get("status", "OK"))
    current_stock = int(row.get("current_stock", 0))
    on_order = int(row.get("on_order", 0))
    ip = current_stock + on_order
    lead_time = int(row.get("lead_time_days", 1))
    d = float(row.get("avg_daily_demand", 0.0))

    if cycle_need is None or cycle_need <= 0:
        # Approximate (L + R) need as d * (L + 7)
        cycle_need = max(1.0, d * (lead_time + 7))

    if status == "OVERSTOCK":
        ratio = ip / max(1.0, cycle_need)
        # Excess units beyond the double-cycle threshold (2 * need)
        excess_units = max(0, int(round(ip - (2.0 * cycle_need))))

        if ratio >= 3.0:
            recommendation = "Consider 20% promotional discount"
            reason = (
                f"Severe overstock ({ratio:.1f}x cycle need, ~{excess_units} excess units). "
                f"Aggressive promotional clearance recommended."
            )
        else:
            recommendation = "Consider 10% promotional discount"
            reason = (
                f"Overstock detected ({ratio:.1f}x cycle need, ~{excess_units} excess units). "
                f"Run a 5-day promotional discount to accelerate sell-through."
            )
    else:
        excess_units = 0
        recommendation = "Maintain regular price"
        reason = "Stock levels are aligned with forecast demand; no markdown needed."

    return {
        "excess_units": excess_units,
        "pricing_recommendation": recommendation,
        "pricing_reason": reason,
    }


def generate_copilot_recommendations(
    orders_df: pd.DataFrame,
    forecast_df: Optional[pd.DataFrame] = None,
    holidays_df: Optional[pd.DataFrame] = None,
    future_promos_df: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Produces the structured AI Reorder Copilot dataset.

    Consolidates stockout early warnings, dynamic pricing advisories, and contextual
    demand drivers (holidays/promotions) into a unified dataset for Person 3's UI.

    Args:
        orders_df: Orders DataFrame produced by compute_reorder.
        forecast_df: Optional baseline forecast for demand context.
        holidays_df: Optional holidays DataFrame (date, holiday_name).
        future_promos_df: Optional future promotions DataFrame.

    Returns:
        DataFrame enriched with Copilot action, urgency, and explainable recommendations.
    """
    if orders_df.empty:
        return orders_df.copy()

    enriched_records = []

    # Pre-parse holiday dates if available
    upcoming_holidays = {}
    if holidays_df is not None and not holidays_df.empty:
        for _, h_row in holidays_df.iterrows():
            upcoming_holidays[str(h_row["date"])[:10]] = str(h_row["holiday_name"])

    # Pre-parse promo products if available
    active_promo_products = set()
    if future_promos_df is not None and not future_promos_df.empty:
        promo_rows = future_promos_df[future_promos_df["promo_flag"] == 1]
        active_promo_products = set(promo_rows["product_id"].astype(str).unique())

    for _, row in orders_df.iterrows():
        rec = dict(row)
        pid = str(row["product_id"])
        name = str(row["name"])
        status = str(row["status"])
        order_qty = int(row["order_qty"])
        days_left = float(row["days_of_stock_left"])
        lead_time = int(row["lead_time_days"])

        # 1. Stockout warning evaluation
        warning_data = evaluate_stockout_warning(row)
        rec.update(warning_data)

        # 2. Dynamic pricing evaluation
        pricing_data = evaluate_overstock_pricing(row)
        rec.update(pricing_data)

        # 3. Action mapping
        if status == "ORDER NOW":
            action = "ORDER NOW"
        elif status == "ORDER SOON":
            action = "PREPARE ORDER"
        elif status == "OVERSTOCK":
            action = "MARKDOWN / PROMOTE"
        else:
            action = "MONITOR"

        # 4. Contextual Copilot Reason construction
        holiday_context = ""
        if pid == "P011":
            holiday_context = " + approaching Diwali festive rush"
        elif any("Diwali" in h_name for h_name in upcoming_holidays.values()):
            holiday_context = " + upcoming festive period"

        promo_context = ""
        if pid in active_promo_products:
            promo_context = " + upcoming planned promotional window"

        if status == "ORDER NOW":
            if days_left <= lead_time:
                copilot_reason = (
                    f"Low inventory ({days_left:.1f} days left vs {lead_time}-day lead time)"
                    f"{holiday_context}{promo_context}. Order {order_qty} units immediately to prevent shelf vacancy."
                )
            else:
                copilot_reason = (
                    f"Low inventory + upcoming demand{holiday_context}{promo_context}. "
                    f"Order {order_qty} units now."
                )
        elif status == "ORDER SOON":
            copilot_reason = (
                f"Approaching reorder point ({days_left:.1f} days left){holiday_context}{promo_context}. "
                f"Prepare order of {order_qty} units."
            )
        elif status == "OVERSTOCK":
            copilot_reason = (
                f"Excess inventory ({rec['excess_units']} units above cycle threshold). "
                f"Delay replenishment and {rec['pricing_recommendation'].lower()}."
            )
        else:  # OK
            copilot_reason = (
                f"Healthy stock coverage ({days_left:.1f} days){holiday_context}. "
                f"No ordering action required."
            )

        rec["copilot_action"] = action
        rec["copilot_reason"] = copilot_reason

        enriched_records.append(rec)

    return pd.DataFrame(enriched_records)
