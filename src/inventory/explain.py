"""Generates plain-English explanatory reason strings for reorder recommendations.

These explanations help supermarket managers quickly understand the 'why'
behind every stock status and quantity recommendation.
"""
from typing import Optional


def explain_status(
    status: str,
    ip: float,
    days_left: float,
    lead_time: int,
    need_days: int,
    need: float,
    order_qty: int,
    rop: float,
    order_by_date: str = "",
    arrival_date: str = "",
    demand_vs_recent_pct: Optional[float] = None,
) -> str:
    """Generate a concise, human-readable explanation sentence for an inventory row.

    Args:
        status: One of 'ORDER NOW', 'ORDER SOON', 'OVERSTOCK', 'OK'
        ip: Inventory Position (current_stock + on_order)
        days_left: Days of stock remaining before stockout
        lead_time: Effective supplier lead time in days (L)
        need_days: Combined lead time + review period days (L + R)
        need: Total forecast units required over (L + R) days
        order_qty: Recommended order quantity (units)
        rop: Reorder Point in units
        order_by_date: YYYY-MM-DD string to place order by
        arrival_date: YYYY-MM-DD expected arrival date
        demand_vs_recent_pct: Percentage change vs last 28 days sales (optional)

    Returns:
        A plain-English explanation string.
    """
    # Optional demand comparison note
    demand_note = ""
    if demand_vs_recent_pct is not None:
        pct_val = round(demand_vs_recent_pct)
        if pct_val > 0:
            demand_note = f" Demand is {pct_val}% above the last 28 days."
        elif pct_val < 0:
            demand_note = f" Demand is {abs(pct_val)}% below the last 28 days."

    if status == "ORDER NOW":
        arriving_str = f", arriving {arrival_date}" if arrival_date else ""
        return (
            f"Stock position {int(round(ip))} covers {days_left:.1f} days but lead time is {lead_time} days. "
            f"Forecast demand for the next {need_days} days is {int(round(need))}. "
            f"Order {order_qty} now{arriving_str}.{demand_note}"
        ).strip()

    elif status == "ORDER SOON":
        date_str = f"on {order_by_date}" if order_by_date else "soon"
        return (
            f"Stock will reach the reorder point of {int(round(rop))} {date_str}. "
            f"Place an order of {order_qty} by then."
        )

    elif status == "OVERSTOCK":
        return (
            f"Stock position {int(round(ip))} is more than twice the {need_days}-day need of {int(round(need))}. "
            f"Delay ordering and consider a promotion."
        )

    else:  # 'OK'
        return (
            f"Stock covers {days_left:.1f} days against a {lead_time} day lead time. "
            f"No action needed."
        )
