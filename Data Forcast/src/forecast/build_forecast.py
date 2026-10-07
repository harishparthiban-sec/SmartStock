"""
SmartStock - Forecast Engine (Person 1)
Trains Prophet models (with scikit-learn RandomForest fallback), runs 28-day holdout backtest,
evaluates against 7-day flat moving-average baseline, generates final 45-day forecast,
and exports all required deliverables.
"""

import os
import sys
import warnings
import logging

# Suppress all library warnings (including Prophet yearly seasonality notices)
warnings.filterwarnings('ignore')

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Silence noisy third-party loggers
logging.getLogger('cmdstanpy').disabled = True
logging.getLogger('cmdstanpy').setLevel(logging.ERROR)
logging.getLogger('prophet').disabled = True
logging.getLogger('prophet').setLevel(logging.ERROR)

import numpy as np  # type: ignore
import pandas as pd  # type: ignore
import matplotlib  # type: ignore
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # type: ignore

try:
    from src.forecast.spikes import detect_spikes  # type: ignore
except ImportError:
    try:
        from .spikes import detect_spikes  # type: ignore
    except ImportError:
        from spikes import detect_spikes  # type: ignore


def load_inputs(data_dir="data"):
    products_df = pd.read_csv(os.path.join(data_dir, "products.csv"))
    sales_df = pd.read_csv(os.path.join(data_dir, "sales.csv"))
    holidays_df = pd.read_csv(os.path.join(data_dir, "holidays.csv"))
    future_promos_df = pd.read_csv(os.path.join(data_dir, "future_promos.csv"))

    sales_df["date"] = pd.to_datetime(sales_df["date"])
    holidays_df["date"] = pd.to_datetime(holidays_df["date"])
    future_promos_df["date"] = pd.to_datetime(future_promos_df["date"])

    return products_df, sales_df, holidays_df, future_promos_df


def format_holidays_for_prophet(holidays_df):
    h_df = holidays_df.rename(columns={"holiday_name": "holiday", "date": "ds"}).copy()
    h_df["lower_window"] = -5
    h_df["upper_window"] = 1
    return h_df


def train_and_predict_prophet(train_df, test_df, holidays_prophet):
    """
    Trains Prophet per specification:
    linear growth, yearly & weekly seasonality, multiplicative mode,
    holidays [-5, 1], interval_width=0.90, changepoint_prior_scale=0.05,
    multiplicative promo_flag regressor.
    """
    from prophet import Prophet  # type: ignore

    m = Prophet(
        growth='linear',
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        seasonality_mode='multiplicative',
        holidays=holidays_prophet,
        interval_width=0.90,
        changepoint_prior_scale=0.05
    )
    m.add_regressor('promo_flag', mode='multiplicative')

    # Fit model
    m.fit(train_df[['ds', 'y', 'promo_flag']])

    # Predict
    forecast = m.predict(test_df[['ds', 'promo_flag']])
    return m, forecast


def train_and_predict_fallback(train_df, test_df, holidays_df):
    """
    Fallback using sklearn RandomForestRegressor if Prophet is unavailable.
    """
    from sklearn.ensemble import RandomForestRegressor  # type: ignore

    def extract_features(df):
        dates = pd.to_datetime(df['ds'])
        doy = dates.dt.dayofyear
        # Holiday window flag (-5 to +1 days)
        h_dates = set(holidays_df['date'])
        h_window = []
        for d in dates:
            in_win = any((d - hd).days in range(-5, 2) for hd in h_dates)
            h_window.append(1 if in_win else 0)

        min_date = pd.to_datetime('2024-10-07')
        day_idx = (dates - min_date).dt.days

        feats = pd.DataFrame({
            'day_of_week': dates.dt.dayofweek,
            'month': dates.dt.month,
            'sin_doy': np.sin(2 * np.pi * doy / 365.25),
            'cos_doy': np.cos(2 * np.pi * doy / 365.25),
            'holiday_window': h_window,
            'promo_flag': df['promo_flag'].values,
            'day_index': day_idx.values
        })
        return feats

    X_train = extract_features(train_df)
    y_train = train_df['y'].values
    X_test = extract_features(test_df)

    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)

    train_preds = rf.predict(X_train)
    resids = y_train - train_preds
    sigma = float(np.std(resids))

    yhat = rf.predict(X_test)
    yhat_lower = yhat - 1.645 * sigma
    yhat_upper = yhat + 1.645 * sigma

    forecast = pd.DataFrame({
        'ds': test_df['ds'],
        'yhat': yhat,
        'yhat_lower': yhat_lower,
        'yhat_upper': yhat_upper
    })
    return rf, forecast


def plot_diagnostics(model, final_forecast, product_id, docs_dir="docs"):
    """
    Saves Prophet component plot and forecast plot with interval band.
    """
    plots_dir = os.path.join(docs_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    try:
        # Component plot
        fig_comp = model.plot_components(final_forecast)
        comp_path = os.path.join(plots_dir, f"{product_id}_components.png")
        fig_comp.savefig(comp_path, dpi=150, bbox_inches="tight")
        plt.close(fig_comp)

        # Forecast plot with interval band
        fig_fcst = model.plot(final_forecast)
        fcst_path = os.path.join(plots_dir, f"{product_id}_forecast.png")
        fig_fcst.savefig(fcst_path, dpi=150, bbox_inches="tight")
        plt.close(fig_fcst)
        print(f"  Saved diagnostic plots for {product_id}")
    except Exception as e:
        print(f"  Warning: could not save plots for {product_id}: {e}")


def build_forecasts(data_dir="data", docs_dir="docs"):
    products_df, sales_df, holidays_df, future_promos_df = load_inputs(data_dir)
    holidays_prophet = format_holidays_for_prophet(holidays_df)

    # Dates
    holdout_start = pd.to_datetime("2026-09-09")
    holdout_end = pd.to_datetime("2026-10-06")
    forecast_start = pd.to_datetime("2026-10-07")
    forecast_end = pd.to_datetime("2026-11-20")

    backtest_rows = []
    forecast_rows = []
    error_rows = []
    accuracy_rows = []

    product_ids = products_df["product_id"].unique()
    target_plot_products = {"P011", "P007", "P001"}

    use_prophet = True

    print("\nStarting model training and evaluation across 15 products...")

    for pid in product_ids:
        print(f"Processing product: {pid}...")
        p_sales = sales_df[sales_df["product_id"] == pid].sort_values("date").copy()

        # Holdout split
        p_train = p_sales[p_sales["date"] < holdout_start].copy()
        p_holdout = p_sales[(p_sales["date"] >= holdout_start) & (p_sales["date"] <= holdout_end)].copy()

        # Rename for Prophet: ds, y, promo_flag
        train_df = p_train.rename(columns={"date": "ds", "units_sold": "y"})[["ds", "y", "promo_flag"]]
        holdout_test_df = p_holdout.rename(columns={"date": "ds", "units_sold": "y"})[["ds", "promo_flag", "y"]]

        # ---------------------------------------------------------
        # 1. Holdout Fit (28 days)
        # ---------------------------------------------------------
        try:
            if use_prophet:
                _, holdout_fcst = train_and_predict_prophet(train_df, holdout_test_df, holidays_prophet)
            else:
                _, holdout_fcst = train_and_predict_fallback(train_df, holdout_test_df, holidays_df)
        except Exception as e:
            print(f"Prophet failed for {pid}: {e}. Switching to RandomForest fallback.")
            use_prophet = False
            _, holdout_fcst = train_and_predict_fallback(train_df, holdout_test_df, holidays_df)

        # Merge holdout predictions with actuals
        holdout_fcst = holdout_fcst[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
        holdout_fcst["ds"] = pd.to_datetime(holdout_fcst["ds"])
        merged_holdout = pd.merge(holdout_test_df, holdout_fcst, on="ds")

        # Clip predictions at 0 and round to 1 decimal per spec
        merged_holdout["yhat"] = merged_holdout["yhat"].clip(lower=0.0).round(1)
        merged_holdout["yhat_lower"] = merged_holdout["yhat_lower"].clip(lower=0.0).round(1)
        merged_holdout["yhat_upper"] = merged_holdout["yhat_upper"].clip(lower=0.0).round(1)

        # Ensure bounds logical consistency: yhat_lower <= yhat <= yhat_upper
        merged_holdout["yhat_lower"] = merged_holdout[["yhat_lower", "yhat"]].min(axis=1)
        merged_holdout["yhat_upper"] = merged_holdout[["yhat_upper", "yhat"]].max(axis=1)

        actual = merged_holdout["y"].values
        yhat = merged_holdout["yhat"].values
        residuals = actual - yhat

        sigma = float(np.std(residuals))
        mae_model = float(np.mean(np.abs(residuals)))
        total_actual = float(np.sum(actual))
        wape_model = float(np.sum(np.abs(residuals)) / total_actual * 100.0) if total_actual > 0 else 0.0

        for _, row in merged_holdout.iterrows():
            backtest_rows.append({
                "date": row["ds"].strftime("%Y-%m-%d"),
                "product_id": pid,
                "yhat": round(float(row["yhat"]), 1),
                "yhat_lower": round(float(row["yhat_lower"]), 1),
                "yhat_upper": round(float(row["yhat_upper"]), 1),
                "actual_units": int(row["y"])
            })

        # Baseline: 7-day flat moving average prior to holdout (2026-09-02 to 2026-09-08)
        base_7d_window = p_sales[(p_sales["date"] >= pd.to_datetime("2026-09-02")) & (p_sales["date"] <= pd.to_datetime("2026-09-08"))]
        baseline_val = float(base_7d_window["units_sold"].mean())
        baseline_preds = np.full(len(actual), baseline_val)
        mae_baseline = float(np.mean(np.abs(actual - baseline_preds)))
        wape_baseline = float(np.sum(np.abs(actual - baseline_preds)) / total_actual * 100.0) if total_actual > 0 else 0.0
        improvement_pct = float((wape_baseline - wape_model) / wape_baseline * 100.0) if wape_baseline > 0 else 0.0

        error_rows.append({
            "product_id": pid,
            "sigma": round(sigma, 2),
            "mae": round(mae_model, 2),
            "wape_pct": round(wape_model, 2)
        })

        accuracy_rows.append({
            "product_id": pid,
            "mae_model": round(mae_model, 2),
            "wape_model": round(wape_model, 2),
            "mae_baseline": round(mae_baseline, 2),
            "wape_baseline": round(wape_baseline, 2),
            "improvement_pct": round(improvement_pct, 2)
        })

        # ---------------------------------------------------------
        # 2. Final Run (45 days)
        # ---------------------------------------------------------
        # Full training on all history up to 2026-10-06
        full_train_df = p_sales.rename(columns={"date": "ds", "units_sold": "y"})[["ds", "y", "promo_flag"]]

        # Future promo dataframe for this product
        p_future = future_promos_df[future_promos_df["product_id"] == pid].sort_values("date").copy()
        future_test_df = p_future.rename(columns={"date": "ds"})[["ds", "promo_flag"]]

        # Extended frame (history + future) for full component and forecast plotting
        extended_df = pd.concat([full_train_df[["ds", "promo_flag"]], future_test_df[["ds", "promo_flag"]]]).reset_index(drop=True)

        if use_prophet:
            from prophet import Prophet  # type: ignore
            model_final = Prophet(
                growth='linear',
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False,
                seasonality_mode='multiplicative',
                holidays=holidays_prophet,
                interval_width=0.90,
                changepoint_prior_scale=0.05
            )
            model_final.add_regressor('promo_flag', mode='multiplicative')
            model_final.fit(full_train_df[['ds', 'y', 'promo_flag']])
            full_fcst = model_final.predict(extended_df[['ds', 'promo_flag']])
        else:
            model_final, full_fcst = train_and_predict_fallback(full_train_df, extended_df, holidays_df)

        # Diagnostic plots for required products
        if pid in target_plot_products and use_prophet:
            plot_diagnostics(model_final, full_fcst, pid, docs_dir=docs_dir)

        # Filter strictly for the 45-day forecast horizon (2026-10-07 to 2026-11-20)
        full_fcst["ds"] = pd.to_datetime(full_fcst["ds"])
        final_fcst = full_fcst[(full_fcst["ds"] >= forecast_start) & (full_fcst["ds"] <= forecast_end)][["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()

        final_fcst["yhat"] = final_fcst["yhat"].clip(lower=0.0).round(1)
        final_fcst["yhat_lower"] = final_fcst["yhat_lower"].clip(lower=0.0).round(1)
        final_fcst["yhat_upper"] = final_fcst["yhat_upper"].clip(lower=0.0).round(1)

        final_fcst["yhat_lower"] = final_fcst[["yhat_lower", "yhat"]].min(axis=1)
        final_fcst["yhat_upper"] = final_fcst[["yhat_upper", "yhat"]].max(axis=1)

        for _, row in final_fcst.iterrows():
            forecast_rows.append({
                "date": row["ds"].strftime("%Y-%m-%d"),
                "product_id": pid,
                "yhat": round(float(row["yhat"]), 1),
                "yhat_lower": round(float(row["yhat_lower"]), 1),
                "yhat_upper": round(float(row["yhat_upper"]), 1)
            })


    # ---------------------------------------------------------
    # Save CSV Deliverables
    # ---------------------------------------------------------
    backtest_df = pd.DataFrame(backtest_rows).sort_values(["date", "product_id"]).reset_index(drop=True)
    backtest_path = os.path.join(data_dir, "backtest_forecast.csv")
    backtest_df.to_csv(backtest_path, index=False)
    print(f"\nSaved {backtest_path} ({len(backtest_df)} rows)")

    error_df = pd.DataFrame(error_rows).sort_values("product_id").reset_index(drop=True)
    error_path = os.path.join(data_dir, "forecast_error.csv")
    error_df.to_csv(error_path, index=False)
    print(f"Saved {error_path} ({len(error_df)} rows)")

    forecast_df = pd.DataFrame(forecast_rows).sort_values(["date", "product_id"]).reset_index(drop=True)
    forecast_path = os.path.join(data_dir, "forecast.csv")
    forecast_df.to_csv(forecast_path, index=False)
    print(f"Saved {forecast_path} ({len(forecast_df)} rows)")

    accuracy_df = pd.DataFrame(accuracy_rows).sort_values("product_id").reset_index(drop=True)
    accuracy_path = os.path.join(docs_dir, "accuracy.csv")
    os.makedirs(docs_dir, exist_ok=True)
    accuracy_df.to_csv(accuracy_path, index=False)
    print(f"Saved {accuracy_path} ({len(accuracy_df)} rows)")

    # ---------------------------------------------------------
    # Overall Accuracy Summary
    # ---------------------------------------------------------
    all_actual = backtest_df["actual_units"].values
    all_yhat = backtest_df["yhat"].values
    all_resids = np.abs(all_actual - all_yhat)
    overall_mae_model = float(np.mean(all_resids))
    overall_wape_model = float(np.sum(all_resids) / np.sum(all_actual) * 100.0)

    # Calculate overall baseline across all holdout records
    all_baseline_resids = []
    for pid in product_ids:
        p_actual = backtest_df[backtest_df["product_id"] == pid]["actual_units"].values
        b_val = float(accuracy_df[accuracy_df["product_id"] == pid]["mae_baseline"].values[0])
        # Or calculate from baseline predictions
        p_base_mean = sales_df[(sales_df["product_id"] == pid) & (sales_df["date"] >= pd.to_datetime("2026-09-02")) & (sales_df["date"] <= pd.to_datetime("2026-09-08"))]["units_sold"].mean()
        all_baseline_resids.extend(np.abs(p_actual - p_base_mean))

    overall_mae_baseline = float(np.mean(all_baseline_resids))
    overall_wape_baseline = float(np.sum(all_baseline_resids) / np.sum(all_actual) * 100.0)
    overall_imp_pct = float((overall_wape_baseline - overall_wape_model) / overall_wape_baseline * 100.0)

    print("\n========================================================")
    print("ACCURACY SUMMARY TABLE (Prophet vs 7-day Moving Average)")
    print("========================================================")
    print(accuracy_df.to_string(index=False))
    print("--------------------------------------------------------")
    print(f"OVERALL SUMMARY:")
    print(f"  Model MAE:       {overall_mae_model:.2f}")
    print(f"  Model WAPE:      {overall_wape_model:.2f}%")
    print(f"  Baseline MAE:    {overall_mae_baseline:.2f}")
    print(f"  Baseline WAPE:   {overall_wape_baseline:.2f}%")
    print(f"  Improvement:     {overall_imp_pct:.2f}%")
    print("========================================================\n")

    # ---------------------------------------------------------
    # 3. Trigger Spike Detection
    # ---------------------------------------------------------
    detect_spikes(backtest_path=backtest_path, alerts_path=os.path.join(data_dir, "alerts.csv"))

    # ---------------------------------------------------------
    # 4. Generate Demand Intelligence & Copilot Signals
    # ---------------------------------------------------------
    try:
        from src.forecast.demand_signals import compute_demand_signals
    except ImportError:
        try:
            from .demand_signals import compute_demand_signals
        except ImportError:
            from demand_signals import compute_demand_signals
    compute_demand_signals(data_dir=data_dir)

    # ---------------------------------------------------------
    # 5. Demand Time Machine (Historical Analog Engine & Backtest)
    # ---------------------------------------------------------
    try:
        from src.forecast.demand_time_machine import run_time_machine, backtest_time_machine
    except ImportError:
        try:
            from .demand_time_machine import run_time_machine, backtest_time_machine
        except ImportError:
            from demand_time_machine import run_time_machine, backtest_time_machine
    run_time_machine(data_dir=data_dir, docs_dir=docs_dir)
    backtest_time_machine(data_dir=data_dir)


def main():
    build_forecasts()
    print("\n[PASS] build_forecast.py execution complete!")


if __name__ == "__main__":
    main()
