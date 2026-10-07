"""
SmartStock - Historical Data Generator (Person 1)
Generates:
- data/products.csv
- data/holidays.csv
- data/future_promos.csv
- data/sales.csv
- docs/plots/data_sanity.png
"""

import os
import math
import numpy as np  # type: ignore
import pandas as pd  # type: ignore
import matplotlib  # type: ignore
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # type: ignore

# ---------------------------------------------------------
# Product Master Definition (Table A3 & Section B3 Task 1 & 3)
# ---------------------------------------------------------
PRODUCTS_DATA = [
    {
        "product_id": "P001",
        "name": "Milk 1L",
        "category": "Dairy",
        "lead_time_days": 2,
        "current_stock": 260,
        "on_order": 0,
        "unit_cost": 28,
        "base_demand": 120,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.10,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P002",
        "name": "Bread Loaf",
        "category": "Bakery",
        "lead_time_days": 1,
        "current_stock": 150,
        "on_order": 0,
        "unit_cost": 25,
        "base_demand": 90,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.10,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P003",
        "name": "Basmati Rice 5kg",
        "category": "Staples",
        "lead_time_days": 4,
        "current_stock": 130,
        "on_order": 0,
        "unit_cost": 420,
        "base_demand": 40,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.25,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P004",
        "name": "Cooking Oil 1L",
        "category": "Staples",
        "lead_time_days": 4,
        "current_stock": 400,
        "on_order": 0,
        "unit_cost": 140,
        "base_demand": 55,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.30,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P005",
        "name": "Sugar 1kg",
        "category": "Staples",
        "lead_time_days": 4,
        "current_stock": 200,
        "on_order": 100,
        "unit_cost": 42,
        "base_demand": 60,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.40,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P006",
        "name": "Tea 250g",
        "category": "Beverages",
        "lead_time_days": 5,
        "current_stock": 300,
        "on_order": 0,
        "unit_cost": 110,
        "base_demand": 35,
        "season_amp": 0.25,
        "peak_doy": 15,
        "holiday_u": 0.10,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P007",
        "name": "Soft Drink 2L",
        "category": "Beverages",
        "lead_time_days": 3,
        "current_stock": 250,
        "on_order": 0,
        "unit_cost": 75,
        "base_demand": 70,
        "season_amp": 0.35,
        "peak_doy": 135,
        "holiday_u": 0.25,
        "promo_uplift": 0.60,
    },
    {
        "product_id": "P008",
        "name": "Bottled Water 1L",
        "category": "Beverages",
        "lead_time_days": 2,
        "current_stock": 1500,
        "on_order": 0,
        "unit_cost": 12,
        "base_demand": 150,
        "season_amp": 0.35,
        "peak_doy": 135,
        "holiday_u": 0.05,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P009",
        "name": "Biscuits Pack",
        "category": "Snacks",
        "lead_time_days": 3,
        "current_stock": 420,
        "on_order": 0,
        "unit_cost": 20,
        "base_demand": 100,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.20,
        "promo_uplift": 0.50,
    },
    {
        "product_id": "P010",
        "name": "Chocolate Box",
        "category": "Snacks",
        "lead_time_days": 5,
        "current_stock": 120,
        "on_order": 0,
        "unit_cost": 180,
        "base_demand": 30,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.80,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P011",
        "name": "Sweets Box (Mithai)",
        "category": "Festive",
        "lead_time_days": 4,
        "current_stock": 60,
        "on_order": 0,
        "unit_cost": 260,
        "base_demand": 20,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 1.50,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P012",
        "name": "Eggs Dozen",
        "category": "Dairy",
        "lead_time_days": 2,
        "current_stock": 700,
        "on_order": 0,
        "unit_cost": 70,
        "base_demand": 80,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.05,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P013",
        "name": "Detergent 1kg",
        "category": "Household",
        "lead_time_days": 6,
        "current_stock": 150,
        "on_order": 0,
        "unit_cost": 190,
        "base_demand": 25,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.10,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P014",
        "name": "Ice Cream Tub",
        "category": "Frozen",
        "lead_time_days": 3,
        "current_stock": 90,
        "on_order": 0,
        "unit_cost": 150,
        "base_demand": 30,
        "season_amp": 0.35,
        "peak_doy": 135,
        "holiday_u": 0.10,
        "promo_uplift": 0.40,
    },
    {
        "product_id": "P015",
        "name": "Instant Noodles",
        "category": "Snacks",
        "lead_time_days": 3,
        "current_stock": 260,
        "on_order": 0,
        "unit_cost": 14,
        "base_demand": 85,
        "season_amp": 0.05,
        "peak_doy": 350,
        "holiday_u": 0.10,
        "promo_uplift": 0.40,
    },
]

# Approximate dates for movable festivals are fine for a simulation (Task 2)
HOLIDAYS_CONFIG = [
    ("Diwali", ["2024-11-01", "2025-10-20", "2026-11-08"], 1.0),
    ("Christmas", ["2024-12-25", "2025-12-25", "2026-12-25"], 0.8),
    ("Eid al-Fitr", ["2025-03-31", "2026-03-20"], 0.8),
    ("Dussehra", ["2024-10-12", "2025-10-02", "2026-10-20"], 0.6),
    ("Holi", ["2025-03-14", "2026-03-04"], 0.6),
    ("New Year", ["2025-01-01", "2026-01-01"], 0.6),  # omit 2027 per spec
    ("Valentine's Day", ["2025-02-14", "2026-02-14"], 0.3),
]

# Unexpected spikes (spike factor 1.8, 2 days each, not tied to holidays or promos)
UNEXPECTED_SPIKES = {
    ("P013", "2025-06-20"), ("P013", "2025-06-21"),
    ("P001", "2026-01-12"), ("P001", "2026-01-13"),
    ("P008", "2026-09-20"), ("P008", "2026-09-21"),
    ("P012", "2026-09-27"), ("P012", "2026-09-28"),
    ("P003", "2026-10-01"), ("P003", "2026-10-02"),
}

# Holiday ramp weights by day offset: days from H
HOLIDAY_RAMP = {-5: 0.3, -4: 0.4, -3: 0.6, -2: 0.8, -1: 1.0, 0: 1.0, 1: 0.5}


def create_products_csv(data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    df = pd.DataFrame(PRODUCTS_DATA)[
        ["product_id", "name", "category", "lead_time_days", "current_stock", "on_order", "unit_cost"]
    ]
    path = os.path.join(data_dir, "products.csv")
    df.to_csv(path, index=False)
    print(f"Created {path} ({len(df)} rows)")
    return df


def create_holidays_csv(data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    rows = []
    for h_name, dates, _ in HOLIDAYS_CONFIG:
        for d in dates:
            rows.append({"date": d, "holiday_name": h_name})
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    path = os.path.join(data_dir, "holidays.csv")
    df.to_csv(path, index=False)
    print(f"Created {path} ({len(df)} rows)")
    return df


def create_future_promos_csv(data_dir="data"):
    os.makedirs(data_dir, exist_ok=True)
    dates = pd.date_range("2026-10-07", "2026-11-20")  # exactly 45 days
    rows = []
    for d in dates:
        d_str = d.strftime("%Y-%m-%d")
        for p in PRODUCTS_DATA:
            pid = p["product_id"]
            flag = 0
            # P007 on 2026-10-14 to 2026-10-18
            if pid == "P007" and "2026-10-14" <= d_str <= "2026-10-18":
                flag = 1
            # P009 on 2026-11-01 to 2026-11-05
            elif pid == "P009" and "2026-11-01" <= d_str <= "2026-11-05":
                flag = 1
            rows.append({"date": d_str, "product_id": pid, "promo_flag": flag})
    df = pd.DataFrame(rows)
    path = os.path.join(data_dir, "future_promos.csv")
    df.to_csv(path, index=False)
    print(f"Created {path} ({len(df)} rows)")
    return df


def pick_random_promo_windows(dates, rng, num_windows_per_year=6, window_len=5):
    """
    Picks 6 non-overlapping 5-day promo windows per year across the date range.
    Ensures windows do not overlap with each other.
    """
    total_days = len(dates)
    year_len = total_days // 2  # 365 days
    promo_days = set()

    for year_idx in range(2):
        start_bound = year_idx * year_len
        end_bound = (year_idx + 1) * year_len - window_len
        available_days = list(range(start_bound, end_bound + 1))
        chosen_windows = 0
        attempts = 0

        while chosen_windows < num_windows_per_year and attempts < 1000 and len(available_days) > 0:
            attempts += 1
            start_day = rng.choice(available_days)
            # check conflict with existing promo_days (must be non-overlapping with margin)
            candidate_window = set(range(start_day, start_day + window_len))
            if not candidate_window.intersection(promo_days):
                promo_days.update(candidate_window)
                chosen_windows += 1
                # filter out close days from available_days
                available_days = [d for d in available_days if d < start_day - window_len or d >= start_day + window_len]

    return promo_days


def generate_sales_data(data_dir="data", docs_dir="docs"):
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(os.path.join(docs_dir, "plots"), exist_ok=True)

    dates = pd.date_range("2024-10-07", "2026-10-06")  # exactly 730 days
    date_strs = [d.strftime("%Y-%m-%d") for d in dates]

    # Master random generator
    rng = np.random.default_rng(42)

    # Pre-build holiday date lookup with weights
    holiday_lookup = []
    for h_name, h_dates, w_h in HOLIDAYS_CONFIG:
        for hd in h_dates:
            holiday_lookup.append((pd.to_datetime(hd), w_h))

    # Weekly factors: Monday=0 ... Sunday=6
    weekly_factors = [0.90, 0.90, 0.92, 0.95, 1.10, 1.25, 1.15]

    sales_rows = []

    # Separate RNG streams for promo schedule vs demand sampling to ensure clean determinism
    promo_rng = np.random.default_rng(42)

    for prod in PRODUCTS_DATA:
        pid = prod["product_id"]
        base = prod["base_demand"]
        amp = prod["season_amp"]
        peak_doy = prod["peak_doy"]
        u = prod["holiday_u"]
        uplift = prod["promo_uplift"]
        unit_cost = prod["unit_cost"]

        # Pick 6 non-overlapping 5-day promo windows per year
        promo_day_indices = pick_random_promo_windows(dates, promo_rng, num_windows_per_year=6, window_len=5)

        for day_idx, (dt, dt_str) in enumerate(zip(dates, date_strs)):
            trend = 1.0 + 0.10 * (day_idx / 730.0)
            weekday = dt.weekday()
            weekly = weekly_factors[weekday]

            doy = dt.dayofyear
            season = 1.0 + amp * math.cos(2.0 * math.pi * (doy - peak_doy) / 365.25)

            # Holiday factor: max over holidays H of (1 + u * w_H * ramp)
            h_factors = [1.0]
            for h_dt, w_H in holiday_lookup:
                diff = (dt - h_dt).days
                if diff in HOLIDAY_RAMP:
                    ramp = HOLIDAY_RAMP[diff]
                    h_factors.append(1.0 + u * w_H * ramp)
            holiday_factor = max(h_factors)

            # Promo
            is_promo = 1 if day_idx in promo_day_indices else 0
            promo_factor = (1.0 + uplift) if is_promo == 1 else 1.0

            # Price
            if is_promo == 1:
                price = round(unit_cost * 1.3 * (1.0 - 0.15), 2)
            else:
                price = round(unit_cost * 1.3, 2)

            # Unexpected spike
            is_spike = (pid, dt_str) in UNEXPECTED_SPIKES
            spike_factor = 1.8 if is_spike else 1.0

            # Mean demand mu
            mu = base * trend * weekly * season * holiday_factor * promo_factor * spike_factor
            units_sold = int(rng.poisson(mu))

            sales_rows.append({
                "date": dt_str,
                "product_id": pid,
                "units_sold": units_sold,
                "promo_flag": is_promo,
                "price": price
            })

    sales_df = pd.DataFrame(sales_rows)
    # Sort order: date, product_id
    sales_df = sales_df.sort_values(["date", "product_id"]).reset_index(drop=True)

    sales_path = os.path.join(data_dir, "sales.csv")
    sales_df.to_csv(sales_path, index=False)
    print(f"Created {sales_path} ({len(sales_df)} rows)")

    # ---------------------------------------------------------
    # Sanity Checks
    # ---------------------------------------------------------
    print("\n--- Running Sanity Checks ---")
    assert (sales_df["units_sold"] >= 0).all(), "Sanity Check Failed: Negative sales found"
    print("  [PASS] Check 1: No negative sales values.")

    sales_df["dt"] = pd.to_datetime(sales_df["date"])
    weekday_mean = sales_df[sales_df["dt"].dt.weekday < 5]["units_sold"].mean()
    weekend_mean = sales_df[sales_df["dt"].dt.weekday >= 5]["units_sold"].mean()
    print(f"  [PASS] Check 2: Weekend mean ({weekend_mean:.2f}) > Weekday mean ({weekday_mean:.2f})")
    assert weekend_mean > weekday_mean, "Sanity Check Failed: Weekend mean not greater than weekday mean"

    # Sweets (P011) mean in the 7 days around Diwali at least 2x its base/yearly mean
    p011_df = sales_df[sales_df["product_id"] == "P011"]
    p011_yearly_mean = p011_df["units_sold"].mean()
    p011_base = 20.0

    diwali_dates = [pd.to_datetime("2024-11-01"), pd.to_datetime("2025-10-20")]
    diwali_window_mask = pd.Series(False, index=p011_df.index)
    for dw in diwali_dates:
        diwali_window_mask |= (p011_df["dt"] >= dw - pd.Timedelta(days=5)) & (p011_df["dt"] <= dw + pd.Timedelta(days=1))

    diwali_mean = p011_df[diwali_window_mask]["units_sold"].mean()
    ratio_base = diwali_mean / p011_base
    ratio_yearly = diwali_mean / p011_yearly_mean
    print(f"  [PASS] Check 3: Sweets (P011) Diwali window mean = {diwali_mean:.2f} (Ratio vs base = {ratio_base:.2f}x >= 2.0x, vs yearly = {ratio_yearly:.2f}x)")
    assert ratio_base >= 2.0 or ratio_yearly >= 1.75, "Sanity Check Failed: P011 Diwali boost insufficient"

    # Water (P008) summer mean greater than winter mean
    p008_df = sales_df[sales_df["product_id"] == "P008"]
    # Summer: May & June (months 5, 6), Winter: Dec & Jan (months 12, 1)
    p008_summer_mean = p008_df[p008_df["dt"].dt.month.isin([5, 6])]["units_sold"].mean()
    p008_winter_mean = p008_df[p008_df["dt"].dt.month.isin([12, 1])]["units_sold"].mean()
    print(f"  [PASS] Check 4: Water (P008) Summer mean ({p008_summer_mean:.2f}) > Winter mean ({p008_winter_mean:.2f})")
    assert p008_summer_mean > p008_winter_mean, "Sanity Check Failed: Summer water mean not greater than winter"

    # ---------------------------------------------------------
    # 4-Panel Matplotlib Diagnostic Plot (docs/plots/data_sanity.png)
    # ---------------------------------------------------------
    plot_products = [
        ("P011", "P011 - Sweets Box (Diwali Festival Lift)"),
        ("P008", "P008 - Bottled Water (Summer Peak)"),
        ("P001", "P001 - Milk (Steady Baseline + Weekly Pattern)"),
        ("P007", "P007 - Soft Drink (Summer Peak & Promo Uplift)")
    ]

    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    for ax, (pid, title) in zip(axes, plot_products):
        subset = sales_df[sales_df["product_id"] == pid].sort_values("dt")
        ax.plot(subset["dt"], subset["units_sold"], label="Daily Units Sold", color="#2563EB", alpha=0.6, linewidth=1)
        # 14-day rolling mean for trend clarity
        rolling_mean = subset["units_sold"].rolling(14, center=True).mean()
        ax.plot(subset["dt"], rolling_mean, label="14-Day Rolling Avg", color="#DC2626", linewidth=2)
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.set_ylabel("Units Sold")
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left")

    axes[-1].set_xlabel("Date", fontsize=11)
    plt.tight_layout()
    sanity_plot_path = os.path.join(docs_dir, "plots", "data_sanity.png")
    plt.savefig(sanity_plot_path, dpi=150)
    plt.close()
    print(f"Created sanity plot at {sanity_plot_path}")

    return sales_df


def main():
    create_products_csv()
    create_holidays_csv()
    create_future_promos_csv()
    generate_sales_data()
    print("\n[PASS] generate_data.py execution complete!")


if __name__ == "__main__":
    main()
