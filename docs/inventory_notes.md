# SmartStock: Inventory Engine Documentation & Pitch Notes

## 1. Executive Summary
SmartStock transforms raw demand forecasts into high-confidence, actionable replenishment decisions for supermarket store managers. Instead of relying on static rules of thumb or gut feel, SmartStock dynamically adjusts safety buffers and reorder thresholds according to forecast volatility, lead times, and upcoming demand spikes (such as festivals and promotions).

---

## 2. Core Mathematical Formulations

### A. Safety Stock ($SS$)
$$\text{Safety Stock} (SS) = Z \times \sigma \times \sqrt{L}$$

* **$Z$ (Service Level Factor):** Derived from the standard normal inverse CDF ($\Phi^{-1}(\text{service\_level})$). At the default $95\%$ service level, $Z \approx 1.645$. This ensures a $95\%$ probability that demand during replenishment will not exceed available stock.
* **$\sigma$ (Forecast Standard Error):** Represents forecast uncertainty, measured as the standard deviation of residuals $(\text{actual} - \hat{y})$ from the 28-day holdout validation. If error metrics are unavailable, a conservative default of $25\%$ of daily demand ($0.25 \times d$) is used.
* **$\sqrt{L}$ (Lead Time Factor):** Captures risk accumulation over the supplier lead time $L = \text{lead\_time\_days} + \text{lead\_time\_extra\_days}$. Because daily forecast errors are assumed independent, variance accumulates linearly ($L \cdot \sigma^2$), meaning the standard deviation grows with $\sqrt{L}$.

---

### B. Reorder Point ($ROP$)
$$\text{Reorder Point} (ROP) = \text{demand}_{LT} + SS$$

* **$\text{demand}_{LT}$:** Expected cumulative forecast demand over the next $L$ days ($\sum_{t=1}^{L} \hat{y}_t$).
* **Role:** When the **Inventory Position ($IP = \text{current\_stock} + \text{on\_order}$)** drops to or below the Reorder Point, an order must be placed immediately to prevent a stockout before the new delivery arrives.

---

### C. Recommended Order Quantity ($\text{order\_qty}$)
$$\text{Raw Order Quantity} = \text{need} + SS - IP$$
$$\text{order\_qty} = \left\lceil \max(0, \text{Raw Order Quantity}) \right\rceil \quad \text{(only for ORDER NOW or ORDER SOON)}$$

* **$\text{need}$:** Total cumulative forecast demand over the combined Lead Time plus Review Period ($L + R$ days, where $R = 7$ days by default).
* **Target Stock:** A newly placed order restores inventory to cover expected demand through the next review cycle plus the safety buffer ($(\text{need} + SS)$).

---

## 3. Decision Rules & Status Triggers
SmartStock classifies each product into one of four intuitive statuses evaluated in strict order:

| Status | Condition | Meaning & Action |
| :--- | :--- | :--- |
| **ORDER NOW** | $IP \le ROP$ | Stock will deplete before or right as delivery arrives. **Place order immediately.** |
| **ORDER SOON** | $IP \le ROP + 3 \times d$ | Inventory is within 3 days of hitting the reorder threshold. Prepare purchase order. |
| **OVERSTOCK** | $IP > 2 \times \text{need}$ | Inventory position covers more than double the $(L + R)$ horizon. Delay orders and consider promotions. |
| **OK** | Otherwise | Inventory is in a healthy operating window. No immediate action required. |

---

## 4. What-If Simulation Engine
The interactive scenario engine (`simulate_scenario` & `run_scenario`) enables supermarket planners to simulate demand surges and supplier disruptions:
1. **Demand Uplifts:** Scale forecast values ($\hat{y}, \hat{y}_{lower}, \hat{y}_{upper}$) by a percentage (e.g., $+60\%$ for Diwali rush, $+40\%$ for summer heatwaves) across specific calendar windows and product selections.
2. **Supplier Lead Time Delays:** Adds extra lead time days ($\text{lead\_time\_extra\_days}$) to evaluate supply-chain fragility.
3. **Pure Function Architecture:** Input forecast tables are never mutated in-place, allowing instantaneous comparative analysis between baseline and scenario states.

---

## 5. Holdout Backtesting Methodology & Value Proof
To validate performance, SmartStock simulates daily inventory operations over the 28-day holdout period (2026-09-09 to 2026-10-06):

* **NAIVE Baseline Policy:** 
  * Calculates historical 30-day moving average daily sales ($m$).
  * Reorder Point = $5 \times m$.
  * Orders up to $12 \times m$ whenever $IP \le 5m$.
* **SMART Policy:**
  * Uses forward-looking daily forecasts ($\hat{y}$) and dynamic safety buffers ($Z \cdot \sigma \sqrt{L}$).
  * Day-by-day simulated arrival pipeline without using future actual demand to cheat ordering decisions.
* **Evaluation Metrics:**
  1. **Stockout Days:** Total days where customers experienced unfulfilled demand.
  2. **Units Short:** Total lost sales volume due to stockouts.
  3. **Fill Rate ($\%$):** Percentage of total customer demand successfully satisfied from stock.
  4. **Average On-Hand Units:** Working capital locked in warehouse/shelf inventory.

### Known Limitations
* **Simulated POS Data:** The dataset is generated through synthetic demand models incorporating seasonality, trend, and Poisson noise.
* **Holdout Residual Reuse:** The forecast error $\sigma$ is computed from the same 28-day holdout evaluation window (mild leakage). In a production environment, $\sigma$ would be calibrated on a preceding validation slice.

---

## 6. Stockout Early Warning System
To provide proactive alerts before shelves go empty, SmartStock evaluates each product's remaining coverage against its replenishment lead time:

* **Urgency Levels:**
  * **CRITICAL:** `days_of_stock_left <= lead_time_days` OR `days_of_stock_left <= 3.0` under `ORDER NOW`. Delivery cannot arrive before stock reaches zero. Immediate action required.
  * **HIGH:** `status == 'ORDER NOW'` (stock will run out soon if replenishment is delayed).
  * **MEDIUM:** `status == 'ORDER SOON'` (inventory is approaching the reorder threshold within 3 days of daily demand).
  * **LOW:** `status` is `OK` or `OVERSTOCK` (coverage exceeds lead time with healthy buffer).
* **Early Warning Fields:**
  * `stockout_in_7_days`: Flag indicating whether a stockout is projected within 7 days of the as-of date (directly aligns with Person 3's 7-day risk KPI).
  * `early_warning_message`: Plain-English alert message detailing days remaining vs lead time.

---

## 7. Dynamic Pricing & Overstock Markdown Recommendations
When inventory significantly exceeds expected demand, SmartStock generates an advisory markdown signal to protect supermarket cash flow:

* **Trigger:** $IP > 2 \times \text{need}$ (evaluated against $(L + R)$ forecast demand).
* **Advisory Rules (Advisory Only - Never modifies base catalog prices):**
  * **Severe Overstock ($IP \ge 3 \times \text{need}$):** `Consider 20% promotional discount` (Aggressive clearance to free working capital).
  * **Standard Overstock ($2 \times \text{need} < IP < 3 \times \text{need}$):** `Consider 10% promotional discount` (5-day promotional discount to accelerate sell-through).
  * **Normal Inventory ($IP \le 2 \times \text{need}$):** `Maintain regular price`.
* **Excess Units:** Quantified as $\max(0, IP - 2 \times \text{need})$.

---

## 8. AI Reorder Copilot Integration Guide (For Person 3)
Person 3 can consume the structured Copilot data either directly from Python or via CSV:

### A. Python Function Consumption
```python
from src.inventory.engine import compute_reorder, get_copilot_recommendations

# Option 1: Compute orders with copilot data included directly
copilot_df = compute_reorder(products_df, forecast_df, include_copilot=True)

# Option 2: Enrich an existing orders DataFrame
copilot_df = get_copilot_recommendations(orders_df, forecast_df=forecast_df)
```

### B. CSV Consumption
SmartStock produces two synchronized CSV outputs in `output/`:
1. `output/orders.csv`: Contains the exact 17 columns defined in Table A4 (100% backward compatible with existing spec).
2. `output/copilot_recommendations.csv`: Contains the 17 base columns plus the following extended Copilot fields:

| Field Name | Type | Description & UI Usage |
| :--- | :--- | :--- |
| `urgency` | string | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` (Use for badge colors / sorting). |
| `stockout_in_7_days` | bool | `True` if stockout date is within 7 days (Use for Overview KPI card). |
| `early_warning_message` | string | Actionable warning banner string. |
| `copilot_action` | string | `ORDER NOW`, `PREPARE ORDER`, `MARKDOWN / PROMOTE`, `MONITOR`. |
| `copilot_reason` | string | Short executive summary (e.g. *"Low inventory + upcoming demand rush"*). |
| `excess_units` | int | Quantity of surplus stock above normal cycle requirement. |
| `pricing_recommendation` | string | E.g., *"Consider 10% promotional discount"* (Use in Overstock tab/callout). |
| `pricing_reason` | string | Detailed explanation of the markdown recommendation. |

