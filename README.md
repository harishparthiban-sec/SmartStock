# SmartStock: Demand-Aware Reorder Assistant for Supermarkets

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-14%2F14%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

SmartStock is an intelligent replenishment and inventory decision engine designed for supermarkets. It tackles stockouts during high-demand periods (festivals like Diwali, promotional campaigns, unexpected demand spikes) while preventing overstocking and cash-flow lockup.

---

## Architecture Overview

SmartStock consists of three modular layers:

```
┌────────────────────────────────────────────────────────┐
│  1. Demand Forecasting Layer (Prophet / Scikit-Learn)   │
│     - 45-day daily forecast with uncertainty intervals  │
│     - Holiday and promotion regressors                  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  2. Inventory Reorder Engine & AI Copilot (Core Layer) │
│     - Dynamic Safety Stock: SS = Z * sigma * sqrt(L)   │
│     - Dynamic Reorder Point: ROP = demand_LT + SS      │
│     - Day-by-Day Stockout Simulation & Early Warning   │
│     - Dynamic Pricing / Overstock Advisory (10%-20%)   │
│     - AI Reorder Copilot structured decision data      │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  3. Interactive Decision Dashboard (Streamlit UI)       │
│     - Overview KPI cards, urgency table, Plotly charts │
│     - Interactive What-If Scenarios (uplift & delays)  │
│     - Backtest proof of value (SMART vs. NAIVE)        │
└────────────────────────────────────────────────────────┘
```

---

## Core Inventory Formulations & Decision Rules

### Mathematical Engine
* **Supplier Lead Time ($L$):** $L = \text{lead\_time\_days} + \text{lead\_time\_extra\_days}$
* **Review Period ($R$):** Default $7$ days.
* **Service Level Factor ($Z$):** Standard normal inverse CDF $\Phi^{-1}(\text{service\_level})$. At $95\%$ service level, $Z \approx 1.645$.
* **Safety Stock ($SS$):** 
  $$SS = Z \times \sigma \times \sqrt{L}$$
  * $\sigma$: Forecast standard error from holdout residuals.
  * $\sqrt{L}$: Accounts for independent risk accumulation over supplier delivery window.
* **Reorder Point ($ROP$):**
  $$ROP = \text{demand}_{LT} + SS \quad \left(\text{where } \text{demand}_{LT} = \sum_{t=1}^{L} \hat{y}_t\right)$$
* **Order Quantity ($\text{order\_qty}$):**
  $$\text{Raw} = \text{need} + SS - IP \quad \left(\text{where } \text{need} = \sum_{t=1}^{L+R} \hat{y}_t, \; IP = \text{current\_stock} + \text{on\_order}\right)$$
  $$\text{order\_qty} = \lceil \max(0, \text{Raw}) \rceil \quad \text{for ORDER NOW / ORDER SOON, else } 0$$

### Decision Priority & Urgency Levels
1. **ORDER NOW:** $IP \le ROP$
   * `CRITICAL`: Days of stock left $\le L$ days (stock will deplete before truck arrives).
   * `HIGH`: Stockout projected within 7 days.
2. **ORDER SOON:** $IP \le ROP + 3 \times d$
   * `MEDIUM`: Reorder point will be reached within 3 days.
3. **OVERSTOCK:** $IP > 2 \times \text{need}$
   * Advisory Dynamic Pricing:
     * $IP \ge 3 \times \text{need} \rightarrow$ *"Consider 20% promotional discount"*.
     * $2 \times \text{need} < IP < 3 \times \text{need} \rightarrow$ *"Consider 10% promotional discount"*.
4. **OK:** Healthy operating window.

---

## AI Reorder Copilot Data Contract

The engine outputs structured decision and copilot recommendations available in `output/copilot_recommendations.csv` and via Python function calls:

| Column | Type | Example | Purpose |
| :--- | :--- | :--- | :--- |
| `product_id` | str | `P001` | Unique SKU identifier |
| `name` | str | `Milk 1L` | Product title |
| `status` | str | `ORDER NOW` | High-level replenishment status |
| `urgency` | str | `CRITICAL` | `CRITICAL`, `HIGH`, `MEDIUM`, `LOW` |
| `stockout_in_7_days` | bool | `True` | Feeds Overview 7-day risk KPI |
| `early_warning_message`| str | `"CRITICAL: Stockout in 1.3 days..."` | Banner / alert message |
| `copilot_action` | str | `ORDER NOW` | Action button label |
| `copilot_reason` | str | `"Low inventory (1.3 days) vs 4-day lead time..."` | Plain-English executive rationale |
| `excess_units` | int | `250` | Surplus units above cycle threshold |
| `pricing_recommendation`| str| `"Consider 10% promotional discount"` | Advisory clearance signal |

---

## Repository Structure

```
SmartStock/
├── README.md                      # Project documentation and pitch guide
├── requirements.txt               # Dependencies
├── .gitignore                     # Git ignore rules
├── docs/
│   └── inventory_notes.md         # Detailed mathematical notes and API reference
├── src/
│   ├── __init__.py
│   └── inventory/
│       ├── __init__.py
│       ├── config.py              # Tunable hyperparameters (service level, review days)
│       ├── copilot.py             # Early warning & dynamic pricing logic
│       ├── engine.py              # Core reorder engine and scenario runner
│       ├── explain.py             # Human-readable sentence generator
│       └── backtest.py            # 28-day holdout policy benchmark simulator
├── tests/
│   ├── fixtures/                  # Self-contained stub data
│   │   ├── products_stub.csv
│   │   ├── forecast_stub.csv
│   │   ├── error_stub.csv
│   │   ├── backtest_forecast_stub.csv
│   │   └── sales_stub.csv
│   ├── test_engine.py             # Engine unit tests & hand-calculated proof
│   ├── test_copilot.py            # Early warning & dynamic pricing unit tests
│   └── test_backtest.py           # Holdout policy simulation unit tests
└── output/
    ├── orders.csv                 # 17-column standard replenishment output (Table A4)
    ├── copilot_recommendations.csv# Enriched AI Copilot dataset
    └── backtest_results.csv       # SMART vs NAIVE policy performance results
```

---

## Quickstart & How to Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Automated Test Suite (14 Tests)
```bash
python -m pytest tests/ -v
```

### 3. Generate Replenishment Orders & AI Copilot Data
```bash
python -m src.inventory.engine
```
* Generates `output/orders.csv` and `output/copilot_recommendations.csv`.

### 4. Run the 28-Day Holdout Simulation
```bash
python -m src.inventory.backtest
```
* Compares `NAIVE` heuristic policy ($ROP = 5m$, order up to $12m$) against `SMART` dynamic forecast policy ($ROP_t = \sum \hat{y}_L + SS$).
* Generates `output/backtest_results.csv`.

---

## Verification & Proof of Value

* **Zero Breakage Guarantee:** The base `output/orders.csv` preserves all 17 exact columns required by the shared project specification.
* **Hand-Calculated Proof:** P001 verified against manual calculation:
  * Flat 100 units/day, $L=4$, current stock $300$, $\sigma=20$, $Z=1.64485$ $\rightarrow$ $SS = 65.79$, $ROP = 466$, $\text{order\_qty} = \mathbf{866}$ units (`ORDER NOW`).
* **Capital Efficiency:** In 28-day backtesting, `SMART` safely reduced average warehouse holding inventory by **38%** (from 499.4 to 308.2 units) with zero stockouts.
