"""
SmartStock - Forecast Service API (Person 1)
Reads data/forecast.csv only (never trains) and provides get_forecast().
"""

import os
import pandas as pd  # type: ignore


def get_forecast(product_id=None, horizon_days=45, forecast_path="data/forecast.csv"):
    """
    Reads data/forecast.csv only (never trains) and returns forecast dataframe.

    Parameters
    ----------
    product_id : str or None
        Specific product ID (e.g. 'P001') or None for all products.
    horizon_days : int
        Number of days into the future to return per product (default 45).
    forecast_path : str
        Path to forecast.csv.

    Returns
    -------
    pd.DataFrame
        Columns: date, product_id, yhat, yhat_lower, yhat_upper
        Date parsed as datetime.
    """
    if not os.path.exists(forecast_path):
        raise FileNotFoundError(f"Forecast file not found at: {forecast_path}")

    df = pd.read_csv(forecast_path)
    df["date"] = pd.to_datetime(df["date"])

    if product_id is not None:
        if isinstance(product_id, str):
            df = df[df["product_id"] == product_id]
        elif isinstance(product_id, (list, set, tuple)):
            df = df[df["product_id"].isin(product_id)]

    # Limit to the first horizon_days per product (ordered by date)
    df = df.sort_values(["product_id", "date"]).groupby("product_id").head(horizon_days).reset_index(drop=True)

    expected_cols = ["date", "product_id", "yhat", "yhat_lower", "yhat_upper"]
    return df[expected_cols]


if __name__ == "__main__":
    df_sample = get_forecast("P001", horizon_days=7)
    print("Sample forecast for P001 (7 days):")
    print(df_sample)
