"""
SmartStock - Demand Time Machine (Person 1)
Historical Analog-Based Demand Intelligence Engine

Answers:
"Have we seen a demand pattern similar to the current situation before,
 and what happened after that historical situation?"

Key guarantees:
- Zero future leakage: only uses historical data available before the as-of date.
- Shape-based normalization (Z-score).
- Pearson correlation similarity (0-100 scale).
- Top-3 analog discovery with consensus & disagreement metrics.
- Event context alignment (Diwali, Christmas, promotions).
- Comparison against statistical Prophet forecast (Agreement vs Conflict).
- Deterministic backtest evaluation.
"""

import os
import sys
import numpy as np  # type: ignore
import pandas as pd  # type: ignore
import matplotlib  # type: ignore
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # type: ignore

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DEFAULT_AS_OF_DATE = "2026-10-07"
DEFAULT_WINDOW_DAYS = 14
DEFAULT_OUTCOME_DAYS = 14


def normalize_window(series):
    """
    Normalizes a demand sequence to isolate shape from scale.
    z = (x - mean(x)) / std(x).
    Safely handles constant demand by returning zeros without producing NaN.
    """
    arr = np.asarray(series, dtype=float)
    std_val = np.std(arr)
    if std_val < 1e-9:
        # Constant demand: fallback to mean-centered zeros to prevent division by zero / NaN
        return np.zeros_like(arr)
    return (arr - np.mean(arr)) / std_val


def calculate_similarity(window_a, window_b):
    """
    Calculates explainable Pearson correlation similarity between two normalized windows.
    Returns similarity score scaled to 0-100:
    correlation 1.0  -> 100
    correlation 0.0  -> 50
    correlation -1.0 -> 0
    """
    norm_a = normalize_window(window_a)
    norm_b = normalize_window(window_b)

    # If either sequence is flat, correlation is undefined; return neutral 50.0
    if np.all(norm_a == 0) or np.all(norm_b == 0):
        return 50.0

    corr = np.corrcoef(norm_a, norm_b)[0, 1]
    if np.isnan(corr):
        return 50.0

    # Clip to [-1.0, 1.0] to guard against floating-point jitter
    corr = float(np.clip(corr, -1.0, 1.0))
    similarity = ((corr + 1.0) / 2.0) * 100.0
    return round(similarity, 2)


def get_holiday_for_window(start_dt, end_dt, holidays_df, buffer_days=5):
    """
    Identifies if a holiday occurred within or adjacent to the specified window.
    """
    if holidays_df.empty:
        return "No Holiday"
    matches = []
    for _, h_row in holidays_df.iterrows():
        h_dt = h_row["dt"]
        diff_start = (h_dt - start_dt).days
        diff_end = (end_dt - h_dt).days
        if (start_dt - pd.Timedelta(days=buffer_days)) <= h_dt <= (end_dt + pd.Timedelta(days=buffer_days)):
            matches.append(h_row["holiday_name"])
    return ", ".join(sorted(set(matches))) if matches else "No Holiday"


def get_promo_for_window(product_id, start_dt, end_dt, sales_df, future_promos_df, as_of_dt):
    """
    Identifies whether an active promotion was present during the window.
    """
    # Check historical sales
    p_sales = sales_df[(sales_df["product_id"] == product_id) & (sales_df["dt"] >= start_dt) & (sales_df["dt"] <= end_dt)]
    if not p_sales.empty and (p_sales["promo_flag"] == 1).any():
        return "Active Promo"

    # Check future promos if window touches forward period
    if end_dt >= as_of_dt and not future_promos_df.empty:
        p_fut = future_promos_df[(future_promos_df["product_id"] == product_id) & (future_promos_df["dt"] >= start_dt) & (future_promos_df["dt"] <= end_dt)]
        if not p_fut.empty and (p_fut["promo_flag"] == 1).any():
            return "Active Promo"

    return "No Promo"


def evaluate_event_alignment(cur_holiday, cur_promo, hist_holiday, hist_promo):
    """
    Evaluates whether the historical analog occurred in a comparable event context.
    Returns: HIGH, MEDIUM, LOW, NONE
    """
    has_cur_h = cur_holiday != "No Holiday"
    has_hist_h = hist_holiday != "No Holiday"
    has_cur_p = cur_promo == "Active Promo"
    has_hist_p = hist_promo == "Active Promo"

    # Same named holiday in both (e.g., Diwali in both)
    if has_cur_h and has_hist_h:
        cur_set = set(cur_holiday.split(", "))
        hist_set = set(hist_holiday.split(", "))
        if cur_set.intersection(hist_set):
            return "HIGH"
        return "MEDIUM"

    # Both are active promotional periods
    if has_cur_p and has_hist_p:
        return "HIGH"

    # One has a major event while the other has none
    if (has_cur_h or has_cur_p) and not (has_hist_h or has_hist_p):
        return "LOW"
    if (has_hist_h or has_hist_p) and not (has_cur_h or has_cur_p):
        return "LOW"

    # Neither has an event
    if not (has_cur_h or has_cur_p) and not (has_hist_h or has_hist_p):
        return "NONE"

    return "MEDIUM"


def find_top_analogs(cur_window_vals, product_sales_df, as_of_dt, window_days=14, outcome_days=14, top_k=3, min_sep_days=4):
    """
    Searches strictly historical windows ending before the current as-of date.
    
    NO FUTURE LEAKAGE GUARANTEE:
    Candidate match window: [t - window_days + 1, t]
    Historical outcome window: [t + 1, t + outcome_days]
    Both candidate window and outcome window must complete on or before as_of_dt - 1 day.
    Therefore, candidate end date t <= as_of_dt - outcome_days - 1 day.
    """
    max_candidate_end = as_of_dt - pd.Timedelta(days=outcome_days + 1)
    eligible_sales = product_sales_df[product_sales_df["dt"] <= as_of_dt - pd.Timedelta(days=1)].sort_values("dt").reset_index(drop=True)

    if len(eligible_sales) < (window_days + outcome_days):
        return []

    candidates = []
    # Search all valid candidate endpoints
    for i in range(window_days - 1, len(eligible_sales)):
        match_end_dt = eligible_sales.iloc[i]["dt"]
        if match_end_dt > max_candidate_end:
            continue

        match_start_dt = eligible_sales.iloc[i - window_days + 1]["dt"]
        match_vals = eligible_sales.iloc[i - window_days + 1 : i + 1]["units_sold"].values

        # Historical outcome window strictly follows the candidate match
        outcome_vals = eligible_sales.iloc[i + 1 : i + 1 + outcome_days]["units_sold"].values
        if len(match_vals) != window_days or len(outcome_vals) != outcome_days:
            continue

        similarity = calculate_similarity(cur_window_vals, match_vals)
        match_avg = float(np.mean(match_vals))
        outcome_avg = float(np.mean(outcome_vals))
        change_pct = ((outcome_avg - match_avg) / match_avg * 100.0) if match_avg > 0 else 0.0

        candidates.append({
            "end_dt": match_end_dt,
            "start_dt": match_start_dt,
            "outcome_start_dt": eligible_sales.iloc[i + 1]["dt"],
            "outcome_end_dt": eligible_sales.iloc[i + outcome_days]["dt"],
            "similarity": similarity,
            "match_avg": match_avg,
            "outcome_avg": outcome_avg,
            "change_pct": change_pct,
            "match_vals": match_vals,
            "outcome_vals": outcome_vals
        })

    # Sort descending by similarity, tie-break by end_dt descending
    candidates.sort(key=lambda c: (c["similarity"], c["end_dt"]), reverse=True)

    # Pick top_k with minimum separation to ensure distinct historical analog episodes
    selected = []
    for cand in candidates:
        if len(selected) >= top_k:
            break
        # Check separation against already selected candidates
        if all(abs((cand["end_dt"] - s["end_dt"]).days) >= min_sep_days for s in selected):
            selected.append(cand)

    # If min_sep_days was too strict to find top_k, fill remaining from sorted list
    if len(selected) < top_k:
        for cand in candidates:
            if cand not in selected:
                selected.append(cand)
            if len(selected) >= top_k:
                break

    return selected


def calculate_analog_consensus(analogs):
    """
    Calculates similarity-weighted future change % and agreement level among analogs.
    """
    if not analogs:
        return 0.0, "LOW", 0.0

    sim_weights = np.array([max(a["similarity"], 1.0) for a in analogs])
    changes = np.array([a["change_pct"] for a in analogs])

    weighted_change = float(np.sum(sim_weights * changes) / np.sum(sim_weights))
    change_std = float(np.std(changes)) if len(changes) > 1 else 0.0

    if change_std <= 15.0:
        agreement = "HIGH"
    elif change_std <= 30.0:
        agreement = "MEDIUM"
    else:
        agreement = "LOW"

    return round(weighted_change, 2), agreement, round(change_std, 2)


def determine_analog_confidence(best_similarity, agreement, event_alignment, num_analogs):
    """
    Classifies analog evidence confidence: HIGH, MEDIUM, LOW, INSUFFICIENT.
    """
    if num_analogs < 2 or best_similarity < 55.0:
        return "INSUFFICIENT"

    score = 0
    if best_similarity >= 85.0:
        score += 2
    elif best_similarity >= 70.0:
        score += 1

    if agreement == "HIGH":
        score += 2
    elif agreement == "MEDIUM":
        score += 1

    if event_alignment == "HIGH":
        score += 2
    elif event_alignment == "MEDIUM":
        score += 1
    elif event_alignment == "LOW":
        score -= 1

    if score >= 4 and best_similarity >= 75.0:
        return "HIGH"
    elif score >= 2 and best_similarity >= 65.0:
        return "MEDIUM"
    else:
        return "LOW"


def compare_with_forecast(prophet_change_pct, analog_consensus_pct, confidence):
    """
    Compares historical analog consensus against Prophet forecast.
    Returns: STRONG_AGREEMENT, AGREEMENT, CONFLICT, INSUFFICIENT_EVIDENCE
    """
    if confidence == "INSUFFICIENT":
        return "INSUFFICIENT_EVIDENCE"

    same_sign = (prophet_change_pct >= 0 and analog_consensus_pct >= 0) or (prophet_change_pct < 0 and analog_consensus_pct < 0)
    diff = abs(prophet_change_pct - analog_consensus_pct)

    if same_sign and diff <= 15.0:
        return "STRONG_AGREEMENT"
    elif same_sign or (abs(prophet_change_pct) < 5.0 and abs(analog_consensus_pct) < 5.0):
        return "AGREEMENT"
    elif not same_sign and (abs(prophet_change_pct) >= 8.0 or abs(analog_consensus_pct) >= 8.0):
        return "CONFLICT"
    else:
        return "AGREEMENT"


def generate_explanation(product_id, rank, sim_score, event_alignment, hist_holiday, cur_holiday, hist_promo, cur_promo, hist_change, forecast_agreement, consensus_pct, prophet_change_pct):
    """
    Deterministically crafts factual explanation strings.
    """
    reasons = []

    # 1. Pattern & Event Context
    if event_alignment == "HIGH" and hist_holiday != "No Holiday":
        reasons.append(f"Current demand pattern closely resembles a previous {hist_holiday} period (similarity={sim_score:.1f})")
    elif event_alignment == "HIGH" and hist_promo == "Active Promo":
        reasons.append(f"Current demand pattern closely resembles a previous promotion period (similarity={sim_score:.1f})")
    elif event_alignment == "LOW":
        reasons.append(f"Current demand pattern resembles a historical period (similarity={sim_score:.1f}), but event context differs")
    else:
        reasons.append(f"Demand pattern matches historical period ending {sim_score:.1f}% similarity")

    # 2. Historical Outcome
    reasons.append(f"historically followed by {hist_change:+.1f}% demand change")

    # 3. Forecast Agreement / Conflict
    if forecast_agreement == "CONFLICT":
        p_dir = "increasing" if prophet_change_pct >= 0 else "declining"
        h_dir = "increasing" if consensus_pct >= 0 else "declining"
        reasons.append(f"statistical forecast indicates {p_dir} demand ({prophet_change_pct:+.1f}%), while analog consensus suggests {h_dir} demand ({consensus_pct:+.1f}%); historical evidence is conflicting")
    elif forecast_agreement in ["STRONG_AGREEMENT", "AGREEMENT"]:
        p_dir = "increasing" if prophet_change_pct >= 0 else "steady/declining"
        reasons.append(f"statistical forecast and analog evidence agree on {p_dir} demand ({prophet_change_pct:+.1f}% vs {consensus_pct:+.1f}%)")

    return "; ".join(reasons)


def run_time_machine(data_dir="data", docs_dir="docs", as_of_date_str=DEFAULT_AS_OF_DATE, window_days=DEFAULT_WINDOW_DAYS, outcome_days=DEFAULT_OUTCOME_DAYS):
    """
    Main driver for the Demand Time Machine engine.
    Generates:
    - data/demand_analogs.csv
    - data/demand_analog_summary.csv
    - docs/plots/demand_time_machine.png
    """
    sales_df = pd.read_csv(os.path.join(data_dir, "sales.csv"))
    products_df = pd.read_csv(os.path.join(data_dir, "products.csv"))
    holidays_df = pd.read_csv(os.path.join(data_dir, "holidays.csv"))
    future_promos_df = pd.read_csv(os.path.join(data_dir, "future_promos.csv"))
    forecast_df = pd.read_csv(os.path.join(data_dir, "forecast.csv"))

    sales_df["dt"] = pd.to_datetime(sales_df["date"])
    holidays_df["dt"] = pd.to_datetime(holidays_df["date"])
    future_promos_df["dt"] = pd.to_datetime(future_promos_df["date"])
    forecast_df["dt"] = pd.to_datetime(forecast_df["date"])

    as_of_dt = pd.to_datetime(as_of_date_str)
    cur_end_dt = as_of_dt - pd.Timedelta(days=1)
    cur_start_dt = cur_end_dt - pd.Timedelta(days=window_days - 1)

    cur_holiday = get_holiday_for_window(cur_start_dt, as_of_dt + pd.Timedelta(days=outcome_days), holidays_df)

    analogs_rows = []
    summary_rows = []

    # Store sample matches for plotting
    plot_samples = {}

    for _, prod in products_df.iterrows():
        pid = prod["product_id"]
        p_sales = sales_df[sales_df["product_id"] == pid].sort_values("dt").reset_index(drop=True)

        # 1. Current Window
        cur_mask = (p_sales["dt"] >= cur_start_dt) & (p_sales["dt"] <= cur_end_dt)
        cur_slice = p_sales[cur_mask]
        if len(cur_slice) != window_days:
            continue

        cur_vals = cur_slice["units_sold"].values
        cur_avg_demand = float(np.mean(cur_vals))
        cur_promo = get_promo_for_window(pid, cur_start_dt, as_of_dt + pd.Timedelta(days=outcome_days), sales_df, future_promos_df, as_of_dt)

        # 2. Existing Prophet Forecast Comparison (next 14 days)
        p_fcst = forecast_df[forecast_df["product_id"] == pid].sort_values("dt").head(outcome_days)
        prophet_avg_14d = float(p_fcst["yhat"].mean()) if not p_fcst.empty else cur_avg_demand
        prophet_change_pct = round(((prophet_avg_14d - cur_avg_demand) / cur_avg_demand * 100.0), 2) if cur_avg_demand > 0 else 0.0

        # 3. Search Historical Analogs
        analogs = find_top_analogs(cur_vals, p_sales, as_of_dt, window_days=window_days, outcome_days=outcome_days, top_k=3)

        consensus_pct, agreement, _ = calculate_analog_consensus(analogs)

        best_sim = analogs[0]["similarity"] if analogs else 0.0
        best_hist_date = analogs[0]["end_dt"].strftime("%Y-%m-%d") if analogs else "No Match Found"

        # Determine primary event alignment from Rank 1 analog
        if analogs:
            rank1 = analogs[0]
            r1_holiday = get_holiday_for_window(rank1["start_dt"], rank1["outcome_end_dt"], holidays_df)
            r1_promo = get_promo_for_window(pid, rank1["start_dt"], rank1["outcome_end_dt"], sales_df, future_promos_df, as_of_dt)
            primary_event_align = evaluate_event_alignment(cur_holiday, cur_promo, r1_holiday, r1_promo)
        else:
            primary_event_align = "NONE"

        confidence = determine_analog_confidence(best_sim, agreement, primary_event_align, len(analogs))
        fcst_agree = compare_with_forecast(prophet_change_pct, consensus_pct, confidence)

        # Store for visualization
        if pid in ["P011", "P007", "P001"] and analogs:
            plot_samples[pid] = {
                "cur_vals": cur_vals,
                "cur_dates": cur_slice["date"].values,
                "match": analogs[0],
                "confidence": confidence,
                "agreement": fcst_agree
            }

        # Build Rank rows
        for rank_idx, analog in enumerate(analogs, start=1):
            h_holiday = get_holiday_for_window(analog["start_dt"], analog["outcome_end_dt"], holidays_df)
            h_promo = get_promo_for_window(pid, analog["start_dt"], analog["outcome_end_dt"], sales_df, future_promos_df, as_of_dt)
            ev_align = evaluate_event_alignment(cur_holiday, cur_promo, h_holiday, h_promo)

            explanation = generate_explanation(
                product_id=pid,
                rank=rank_idx,
                sim_score=analog["similarity"],
                event_alignment=ev_align,
                hist_holiday=h_holiday,
                cur_holiday=cur_holiday,
                hist_promo=h_promo,
                cur_promo=cur_promo,
                hist_change=analog["change_pct"],
                forecast_agreement=fcst_agree,
                consensus_pct=consensus_pct,
                prophet_change_pct=prophet_change_pct
            )

            analogs_rows.append({
                "product_id": pid,
                "as_of_date": as_of_date_str,
                "window_days": window_days,
                "analog_rank": rank_idx,
                "historical_match_date": analog["end_dt"].strftime("%Y-%m-%d"),
                "similarity_score": round(analog["similarity"], 2),
                "current_avg_demand": round(cur_avg_demand, 2),
                "historical_match_avg_demand": round(analog["match_avg"], 2),
                "historical_future_avg_demand": round(analog["outcome_avg"], 2),
                "historical_change_pct": round(analog["change_pct"], 2),
                "historical_holiday": h_holiday,
                "historical_promo": h_promo,
                "current_holiday": cur_holiday,
                "current_promo": cur_promo,
                "event_alignment": ev_align,
                "analog_agreement": agreement,
                "analog_confidence": confidence,
                "prophet_change_pct": round(prophet_change_pct, 2),
                "forecast_agreement": fcst_agree,
                "explanation": explanation
            })

        # Summary row
        hist_evidence_text = f"Top-3 consensus {consensus_pct:+.1f}% demand growth ({agreement} agreement); best match on {best_hist_date} ({best_sim:.1f}% sim)"
        summary_rows.append({
            "product_id": pid,
            "as_of_date": as_of_date_str,
            "best_match_date": best_hist_date,
            "best_similarity_score": round(best_sim, 2),
            "top_3_consensus_growth_pct": round(consensus_pct, 2),
            "analog_agreement": agreement,
            "analog_confidence": confidence,
            "event_alignment": primary_event_align,
            "prophet_change_pct": round(prophet_change_pct, 2),
            "forecast_agreement": fcst_agree,
            "historical_evidence": hist_evidence_text
        })

    # Save CSVs
    analogs_df = pd.DataFrame(analogs_rows)
    analogs_path = os.path.join(data_dir, "demand_analogs.csv")
    analogs_df.to_csv(analogs_path, index=False)
    print(f"Created {analogs_path} ({len(analogs_df)} rows across {len(summary_rows)} products)")

    summary_df = pd.DataFrame(summary_rows)
    summary_path = os.path.join(data_dir, "demand_analog_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"Created {summary_path} ({len(summary_df)} products)")

    # Generate Visualization
    plot_demand_time_machine(plot_samples, docs_dir=docs_dir)

    return analogs_df, summary_df


def plot_demand_time_machine(samples, docs_dir="docs"):
    """
    Creates docs/plots/demand_time_machine.png illustrating:
    1. CURRENT 14-day pattern
    2. HISTORICAL ANALOG pattern
    3. HISTORICAL OUTCOME pattern
    """
    plots_dir = os.path.join(docs_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    if not samples:
        print("  Warning: no sample data available for Time Machine plot.")
        return

    fig, axes = plt.subplots(len(samples), 1, figsize=(12, 4 * len(samples)), sharex=False)
    if len(samples) == 1:
        axes = [axes]

    day_indices_cur = np.arange(-13, 1)  # Days -13 to 0
    day_indices_outcome = np.arange(1, 15)  # Days +1 to +14

    for ax, (pid, info) in zip(axes, samples.items()):
        cur_v = info["cur_vals"]
        match_info = info["match"]
        m_vals = match_info["match_vals"]
        o_vals = match_info["outcome_vals"]
        match_date = match_info["end_dt"].strftime("%Y-%m-%d")

        # Normalize shapes for intuitive visual comparison
        cur_norm = normalize_window(cur_v)
        m_norm = normalize_window(m_vals)
        o_norm = (o_vals - np.mean(m_vals)) / (np.std(m_vals) if np.std(m_vals) > 0 else 1)

        # Plot CURRENT (Days -13 to 0)
        ax.plot(day_indices_cur, cur_norm, marker='o', linewidth=2.5, color='#2563EB', label=f'CURRENT Window (Ending 2026-10-06)')

        # Plot HISTORICAL ANALOG (Days -13 to 0)
        ax.plot(day_indices_cur, m_norm, marker='s', linestyle='--', linewidth=2.0, color='#16A34A', label=f'HISTORICAL ANALOG (Ending {match_date}, Sim: {match_info["similarity"]:.1f}%)')

        # Plot HISTORICAL OUTCOME (Days +1 to +14)
        ax.plot(day_indices_outcome, o_norm, marker='^', linestyle='-', linewidth=2.5, color='#DC2626', label=f'HISTORICAL OUTCOME (Outcome Change: {match_info["change_pct"]:+.1f}%)')

        # Add vertical dividing line at t=0
        ax.axvline(x=0, color='#6B7280', linestyle=':', linewidth=1.5, label='As-Of Boundary (t=0)')
        ax.set_title(f"Demand Time Machine: {pid} Analog Match ({match_date}) | Consensus: {info['agreement']} | Confidence: {info['confidence']}", fontsize=11, fontweight='bold')
        ax.set_xlabel("Relative Timeline (Days from As-Of Boundary)", fontsize=9)
        ax.set_ylabel("Normalized Demand Shape (Z-Score)", fontsize=9)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.legend(loc="upper left", fontsize=8.5)

    plt.tight_layout()
    plot_path = os.path.join(plots_dir, "demand_time_machine.png")
    plt.savefig(plot_path, dpi=150)
    plt.close()
    print(f"Created visualization at {plot_path}")


def backtest_time_machine(data_dir="data"):
    """
    Lightweight deterministic backtest over historical cutoff dates.
    Uses only earlier historical data (strictly <= eval_date - 1 day) to predict next 14-day change %.
    Compares against actual subsequent 14-day change %.
    Calculates MAE and WAPE.
    Outputs: data/demand_analog_backtest.csv
    """
    sales_df = pd.read_csv(os.path.join(data_dir, "sales.csv"))
    products_df = pd.read_csv(os.path.join(data_dir, "products.csv"))
    sales_df["dt"] = pd.to_datetime(sales_df["date"])

    # Evaluation dates chosen with ample history before and after
    eval_dates = [
        "2025-06-01",
        "2025-09-01",
        "2025-12-01",
        "2026-03-01",
        "2026-06-01",
        "2026-08-15"
    ]

    window_days = 14
    outcome_days = 14
    backtest_rows = []

    for eval_str in eval_dates:
        eval_dt = pd.to_datetime(eval_str)
        cur_end = eval_dt - pd.Timedelta(days=1)
        cur_start = cur_end - pd.Timedelta(days=window_days - 1)

        for _, prod in products_df.iterrows():
            pid = prod["product_id"]
            p_sales = sales_df[sales_df["product_id"] == pid].sort_values("dt").reset_index(drop=True)

            cur_slice = p_sales[(p_sales["dt"] >= cur_start) & (p_sales["dt"] <= cur_end)]
            actual_future_slice = p_sales[(p_sales["dt"] >= eval_dt) & (p_sales["dt"] < eval_dt + pd.Timedelta(days=outcome_days))]

            if len(cur_slice) != window_days or len(actual_future_slice) != outcome_days:
                continue

            cur_vals = cur_slice["units_sold"].values
            actual_fut_vals = actual_future_slice["units_sold"].values

            cur_mean = float(np.mean(cur_vals))
            actual_fut_mean = float(np.mean(actual_fut_vals))
            actual_change_pct = ((actual_fut_mean - cur_mean) / cur_mean * 100.0) if cur_mean > 0 else 0.0

            # Find top analogs strictly prior to eval_dt
            analogs = find_top_analogs(cur_vals, p_sales, eval_dt, window_days=window_days, outcome_days=outcome_days, top_k=3)
            if not analogs:
                continue

            pred_change_pct, agreement, _ = calculate_analog_consensus(analogs)
            abs_err = abs(pred_change_pct - actual_change_pct)
            best_sim = analogs[0]["similarity"]
            conf = determine_analog_confidence(best_sim, agreement, "MEDIUM", len(analogs))

            backtest_rows.append({
                "as_of_date": eval_str,
                "product_id": pid,
                "predicted_change_pct": round(pred_change_pct, 2),
                "actual_change_pct": round(actual_change_pct, 2),
                "absolute_error": round(abs_err, 2),
                "best_similarity": round(best_sim, 2),
                "analog_confidence": conf
            })

    bt_df = pd.DataFrame(backtest_rows)
    bt_path = os.path.join(data_dir, "demand_analog_backtest.csv")
    bt_df.to_csv(bt_path, index=False)

    # Compute overall backtest metrics
    mae = float(bt_df["absolute_error"].mean())
    actual_denom = float(np.sum(np.abs(bt_df["actual_change_pct"])))
    wape = float(np.sum(bt_df["absolute_error"]) / actual_denom * 100.0) if actual_denom > 0 else 0.0

    print(f"Created {bt_path} ({len(bt_df)} evaluation windows)")
    print(f"  Backtest Windows evaluated: {len(bt_df)}")
    print(f"  Analog Predictor MAE:       {mae:.2f}% growth error")
    print(f"  Analog Predictor WAPE:      {wape:.2f}%")

    return bt_df, mae, wape


def main():
    print("\n--- Running Demand Time Machine Engine ---")
    run_time_machine()
    print("\n--- Running Demand Time Machine Backtest ---")
    backtest_time_machine()
    print("\n[PASS] demand_time_machine.py execution complete!")


if __name__ == "__main__":
    main()
