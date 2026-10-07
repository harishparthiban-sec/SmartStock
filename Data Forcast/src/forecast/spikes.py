"""
SmartStock - Demand Spike Detector (Person 1)
Reads data/backtest_forecast.csv, flags unexpectedly high demand exceeding yhat_upper,
and writes data/alerts.csv.
"""

import os
import pandas as pd


def detect_spikes(backtest_path="data/backtest_forecast.csv", alerts_path="data/alerts.csv"):
    """
    Scans holdout backtest forecast for unexpected demand spikes:
    - Flags rows where actual_units > yhat_upper
    - excess_pct = (actual_units - yhat_upper) / yhat_upper * 100
    - severity = 'HIGH' if excess_pct >= 50 else 'MEDIUM'
    - Saves data/alerts.csv
    Returns: DataFrame of alerts
    """
    if not os.path.exists(backtest_path):
        raise FileNotFoundError(f"Backtest file not found at: {backtest_path}")

    df = pd.read_csv(backtest_path)
    required_cols = {"date", "product_id", "yhat_upper", "actual_units"}
    if not required_cols.issubset(df.columns):
        raise ValueError(f"Missing required columns in {backtest_path}: {required_cols - set(df.columns)}")

    spikes = df[df["actual_units"] > df["yhat_upper"]].copy()

    if spikes.empty:
        alerts_df = pd.DataFrame(columns=["date", "product_id", "actual_units", "yhat_upper", "excess_pct", "severity"])
    else:
        # Avoid division by zero if yhat_upper is 0
        excess = (spikes["actual_units"] - spikes["yhat_upper"]) / spikes["yhat_upper"].replace(0, 0.01) * 100.0
        spikes["excess_pct"] = excess.round(2)
        spikes["severity"] = spikes["excess_pct"].apply(lambda x: "HIGH" if x >= 50.0 else "MEDIUM")
        alerts_df = spikes[["date", "product_id", "actual_units", "yhat_upper", "excess_pct", "severity"]].copy()
        alerts_df = alerts_df.sort_values(["date", "product_id"]).reset_index(drop=True)

    os.makedirs(os.path.dirname(alerts_path) or ".", exist_ok=True)
    alerts_df.to_csv(alerts_path, index=False)
    print(f"Created {alerts_path} ({len(alerts_df)} spike alerts detected)")
    return alerts_df


if __name__ == "__main__":
    detect_spikes()
