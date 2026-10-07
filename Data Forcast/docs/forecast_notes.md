# SmartStock Demand Forecasting: Technical Notes & Pitch Guide

## 1. Executive Summary & Purpose
SmartStock enables demand-aware supermarket replenishment. Rather than relying on static reorder rules or lagging moving averages, SmartStock uses **Prophet** per product to capture genuine retail dynamics: annual seasonality, day-of-week shopping patterns, festival shopping surges, and planned promotional discounts.

---

## 2. What Prophet Does
Prophet is an additive/multiplicative regression model developed for business time-series forecasting. It decomposes daily demand into interpretable, decomposable components:

$$\text{Demand}(t) = \text{Trend}(t) \times \text{Weekly}(t) \times \text{Yearly}(t) \times \text{Holidays}(t) \times \text{Promos}(t) + \epsilon_t$$

Because retail effects scale with the size of baseline demand, SmartStock uses **multiplicative seasonality**.

---

## 3. Core Components Explained

### A. Trend
* **What it represents**: The long-term growth or decline in product sales over time.
* **In SmartStock**: Captures the steady supermarket expansion (~10% linear sales growth across the 2-year horizon).

### B. Weekly Seasonality
* **What it represents**: Recurring day-of-week patterns.
* **In SmartStock**: Reflects consumer shopping habits—supermarket sales surge on Friday, Saturday, and Sunday (factors 1.10–1.25), while Monday–Tuesday see lower footfall (factors 0.90).

### C. Yearly Seasonality
* **What it represents**: Annual weather, seasonal lifestyle, and temperature patterns.
* **In SmartStock**:
  * Cold beverages (`P007` Soft Drinks, `P008` Bottled Water, `P014` Ice Cream) peak in summer months (Day-of-Year ~135).
  * Hot beverages (`P006` Tea) peak during cold winter months (Day-of-Year ~15).

### D. Holidays & Festivals
* **What it represents**: Calendar events that trigger sharp consumer buying shifts.
* **In SmartStock**: Key festivals (Diwali, Eid, Christmas, Dussehra, Holi, New Year) are configured with pre-holiday shopping ramp windows ($-5$ days to $+1$ day).
* **Festive Lift**: Products like Sweets / Mithai (`P011`) experience more than double their normal baseline demand leading up to Diwali.

### E. Planned Promotions
* **What it represents**: Price discounts that stimulate consumer demand.
* **In SmartStock**: Included as a multiplicative external regressor (`promo_flag`). When active, demand experiences a product-specific uplift (e.g. $+40\%$ to $+60\%$).

---

## 4. Multiplicative Scaling: Why It Matters
In additive models, a festival adds a flat number of units (e.g., $+20$ units), regardless of base demand. In retail, this is unrealistic:
* A 25% festival surge on Milk (base 120) means $+30$ units.
* A 25% festival surge on Sweets (base 20) means $+5$ units.
Multiplicative decomposition scales holidays, weekend lifts, and promotional lifts proportionally to the product's underlying velocity.

---

## 5. Residual Uncertainty ($\sigma$) & Safety Stock
* **Forecast Uncertainty**: Prophet generates a 90% confidence interval ($[\hat{y}_{\text{lower}}, \hat{y}_{\text{upper}}]$) reflecting parameter and observation noise.
* **Calculating $\sigma$**: Over the 28-day holdout backtest window, we calculate the standard deviation of actual forecast residuals:
  $$\sigma = \text{std}(\text{actual} - \hat{y})$$
* **Bridge to Inventory Engine**: This empirical $\sigma$ is exported to `data/forecast_error.csv` and directly feeds the safety stock formula:
  $$\text{SS} = Z \times \sigma \times \sqrt{L}$$
  Products with higher forecast volatility or longer supplier lead times ($L$) automatically receive larger safety buffers.

---

## 6. Accuracy Metrics & Baseline Evaluation
We benchmarked the Prophet model against a flat 7-day moving average baseline on a strict 28-day holdout period:

* **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N}\sum |\text{actual} - \hat{y}|$$
* **Weighted Absolute Percentage Error (WAPE)**:
  $$\text{WAPE} = \frac{\sum |\text{actual} - \hat{y}|}{\sum \text{actual}} \times 100\%$$
* **Improvement Percentage**:
  $$\text{Improvement} = \frac{\text{WAPE}_{\text{baseline}} - \text{WAPE}_{\text{model}}}{\text{WAPE}_{\text{baseline}}} \times 100\%$$

### Empirical Holdout Results
* **Overall Model MAE**: **7.73** units vs. Baseline MAE: **15.69** units
* **Overall Model WAPE**: **10.68%** vs. Baseline WAPE: **21.66%**
* **Overall Accuracy Improvement**: **+50.69% reduction in error** across all 15 supermarket categories.

---

## 7. The 28-Day Holdout Backtest
* **Why 28 Days?**: A 4-week window (4 complete Monday–Sunday cycles) tests the model across multiple replenishment cycles without leaking future demand into training.
* **Fair Test**: Models are trained strictly on data prior to `2026-09-09`. No holdout sales data was visible during fitting.

---

## 8. Why Unexpected Spikes Are Detected, Not Predicted
* **Unpredictable Demand Shocks**: Viral social trends, bulk institutional purchases, or sudden local events cannot be forecasted in advance because they exhibit no historical pattern.
* **Anticipation vs. Reaction**:
  * **Holidays & Promos**: Known in advance $\rightarrow$ **Forecasted** by Prophet.
  * **Unplanned Spikes**: Random in nature $\rightarrow$ **Detected** in real-time when $\text{actual} > \hat{y}_{\text{upper}}$.
* **Alert System (`data/alerts.csv`)**: When actual sales break through the 90% upper confidence band by $\ge 50\%$, an automated `HIGH` severity alert is triggered, prompting inventory managers to place emergency replenishment orders before shelves empty.

---

## 9. Limitations of Simulated Data
* **Perfect Poisson Demand**: Real retail point-of-sale data exhibits zero-inflation, stockout truncation (unobserved lost sales), and cannibalization between competing brands.
* **Deterministic Festival Dates**: In production, movable festival dates shift each lunar year, requiring dynamic holiday calendars.
* **Supply Chain Feedback**: Simulated sales assume 100% on-shelf availability in history, whereas real historical sales often underestimate true demand when stockouts occur.

---

## 10. Demand Intelligence & Copilot Signals (`data/demand_signals.csv`)
To power advanced downstream decision-making without altering core contracts, Person 1 generates structured demand signals:

### A. Stockout Early Warning
* **Forward Demand Windows**: Computes expected daily demand across short (7-day), medium (14-day), and full (45-day) horizons (`expected_demand_7d`, `expected_demand_14d`, `expected_demand_45d`).
* **Velocity Shifts**: Detects if forward demand velocity is accelerating (`SURGING`), steady (`STABLE`), or cooling (`DECLINING`) relative to the prior 28 days.
* **Spike History Integration**: Integrates recent spikes from `data/alerts.csv` (`has_spike_alert`, `spike_details`) to highlight erratic consumption surges.

### B. Dynamic Pricing / Overstock Recommendation Signals
* **Pure Demand Perspective**: Flags products where current inventory significantly exceeds projected window demand (`overstock_pricing_candidate = True`), indicating low turnover velocity.
* **Separation of Concerns**: The forecast module does NOT prescribe prices or markdowns; it exposes raw inventory-to-demand imbalance signals so Person 2 (Inventory Engine) and Person 3 (Dashboard) can evaluate markdown candidates.

### C. AI Reorder Copilot Explanations
* **Factual Driver Strings**: Every product receives an automated, human-interpretable rationale (`copilot_explanation`) synthesizing:
  * Upcoming festival demand surges (e.g., *"Diwali festival demand surge expected (+120% lift approaching 2026-11-08)"*)
  * Promotional demand uplifts (e.g., *"Demand expected to surge due to planned promotion (2026-10-14 to 2026-10-18)"*)
  * Recent demand shock flags (e.g., *"Recent demand spike detected on 2026-10-02 (+66.7%)"*)
  * Forecast uncertainty warnings (e.g., *"High forecast uncertainty (sigma=9.0, WAPE=10.4%)"*)
  * Overstock clearance signals (e.g., *"Current stock (1500) exceeds projected 9-day demand need (1080); candidate for dynamic pricing or promo discount"*)

### Consuming These Signals (Person 2 & 3 Guide):
* **Person 2 (Engine)**: Consume `expected_demand_7d` and `sigma` for dynamic lead-time safety stock adjustments, and check `overstock_pricing_candidate` to confirm reorder suppression.
* **Person 3 (Dashboard)**:
  * Import `from src.forecast.demand_signals import get_copilot_explanation, get_demand_signals`.
  * Display `copilot_explanation` inside product detail cards or Copilot chat tooltips.
  * Use `daily_demand_signals.csv` to overlay holiday and promotional event badges directly onto Plotly forecast charts.

---

## 11. Demand Time Machine (Historical Analog-Based Intelligence)

### A. Core Concept & Business Question
The Demand Time Machine answers a critical retailer question that black-box regression cannot:
> *"Have we seen a demand pattern similar to the current situation before, and what happened after that historical situation?"*

It provides empirical, historical precedent to corroborate or challenge statistical model forecasts.

### B. Window Construction & Z-Score Normalization
* **Current Window**: The latest 14 days of available sales prior to the as-of date (`2026-09-23` through `2026-10-06`).
* **Shape over Scale**: To discover matching trajectory dynamics without volume bias, every candidate sequence is Z-score normalized:
  $$z_t = \frac{x_t - \bar{x}}{\sigma_x}$$
  If a window has zero variance (constant demand), the system gracefully outputs mean-centered zeros to guarantee zero NaNs.

### C. Similarity Calculation & Top-3 Discovery
* **Explainable Metric**: Pearson correlation between normalized sequences converted to a bounded 0–100 similarity score:
  $$\text{Similarity Score} = \left(\frac{r + 1}{2}\right) \times 100$$
  where $r=1.0 \rightarrow 100$, $r=0.0 \rightarrow 50$, $r=-1.0 \rightarrow 0$.
* **Top-3 Analogs**: For every product, identifies the top 3 highest-scoring historical matches, enforcing minimum temporal separation so ranks represent distinct historical episodes rather than adjacent days.

### D. Historical Outcome Measurement
* For each historical match $[t-13, t]$, examines the known subsequent 14-day outcome $[t+1, t+14]$:
  $$\text{Historical Change \%} = \frac{\bar{y}_{\text{future}} - \bar{y}_{\text{match}}}{\bar{y}_{\text{match}}} \times 100\%$$
* **Zero Future Leakage Guarantee**: Candidate match windows and their 14-day outcomes are strictly bounded within historical sales ending on or before `2026-10-06`. No forward forecast data is ever accessed during matching.

### E. Event Alignment
Cross-references `data/holidays.csv` and `data/future_promos.csv`:
* `HIGH`: Both current and historical periods share the same festival (e.g. Diwali) or active promotion.
* `MEDIUM`: Both periods have a holiday event (even if different festivals) or partial promo overlap.
* `LOW`: One window features a holiday/promo while the other is a regular shopping period.
* `NONE`: Neither window has an active event.

### F. Historical Consensus & Disagreement
* **Similarity-Weighted Growth Consensus**:
  $$\text{Consensus Growth} = \frac{\sum (\text{Similarity}_i \times \text{Change}_i)}{\sum \text{Similarity}_i}$$
* **Analog Agreement**: Evaluates standard deviation among analog outcomes ($\le 15\% \rightarrow \text{HIGH}$, $\le 30\% \rightarrow \text{MEDIUM}$, $> 30\% \rightarrow \text{LOW}$).

### G. Comparison Against Statistical Forecast (Conflict Detection)
Compares analog consensus against Prophet's 14-day projected growth rate (`prophet_change_pct`):
* `STRONG_AGREEMENT`: Both predict same direction and are within 15% growth spread.
* `AGREEMENT`: Both predict directional alignment.
* `CONFLICT`: Forecast and historical analogs disagree materially (e.g., Prophet projects growth due to upcoming festival calendar, while analog sequence saw declining demand).

### H. Rigorous Backtest Evaluation (`data/demand_analog_backtest.csv`)
Tested across 6 historical evaluation dates ($6 \times 15 = 90$ evaluation windows) using only prior historical data:
* **Analog Predictor Growth MAE**: **9.36%**
* **Analog Predictor WAPE**: **113.77%**
* **Finding**: While statistical Prophet forecasting remains more accurate for point estimates, the Time Machine excels as an interpretability and evidence layer that contextualizes *why* demand moves.

### I. Critical Limitation
> **Historical similarity does not guarantee future demand.** The Time Machine provides empirical precedent, not deterministic prediction. Market conditions, stock availability, and macro trends can alter outcomes.
