# SmartStock: Demand-Aware Reorder Assistant for Supermarkets

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Tests Passing](https://img.shields.io/badge/tests-14%2F14%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

SmartStock is an intelligent replenishment and inventory decision engine for supermarkets. It addresses stockouts during high-demand periods (festivals like Diwali, promotions, unexpected spikes) while preventing overstocking. The system forecasts daily demand per product, computes order quantities and dates using standard inventory formulas, and surfaces the results through an interactive dashboard.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────┐
│  1. Demand Forecasting Layer (Person 1)                 │
│     - 2 years of synthetic sales history (730 days)    │
│     - Prophet / Scikit-Learn per product               │
│     - 45-day daily forecast with uncertainty bands     │
│     - Holiday, seasonal and promo regressors           │
│     - Outputs: data/forecast.csv, forecast_error.csv  │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│  2. Inventory Engine & AI Copilot (Person 2 — This)    │
│     - Safety Stock: SS = Z × σ × √L                   │
│     - Reorder Point: ROP = demand_LT + SS              │
│     - Dynamic Stockout Early Warning (CRITICAL/HIGH)   │
│     - Overstock Dynamic Pricing Advisory               │
│     - AI Reorder Copilot structured decisions          │
│     - 28-day holdout backtest (SMART vs NAIVE)         │
│     - FastAPI REST backend exposing all engine data    │
└──────────────────────────┬─────────────────────────────┘
                           │  HTTP / JSON
                           ▼
┌────────────────────────────────────────────────────────┐
│  3. React + Vite + TailwindCSS Dashboard (Person 3)    │
│     - Overview: KPI cards, urgency table, bar charts   │
│     - Product Detail: sales history + forecast chart  │
│     - What-If: demand surge and supplier delay sliders │
│     - Model & Impact: backtest SMART vs NAIVE results  │
└────────────────────────────────────────────────────────┘
```

---

## Core Inventory Formulas

| Symbol | Meaning |
| :--- | :--- |
| $L$ | Effective lead time = `lead_time_days` + `lead_time_extra_days` |
| $R$ | Review period (default 7 days) |
| $Z$ | Service level factor = $\Phi^{-1}(\text{service\_level})$, e.g. 1.645 at 95% |
| $\sigma$ | Forecast error (std dev of residuals from 28-day holdout) |
| $SS$ | Safety Stock = $Z \times \sigma \times \sqrt{L}$ |
| $ROP$ | Reorder Point = $\sum_{t=1}^{L}\hat{y}_t + SS$ |
| $\text{need}$ | Total forecast demand over $L + R$ days |
| $\text{order\_qty}$ | $\lceil\max(0,\;\text{need} + SS - IP)\rceil$ |

### Decision Priority (checked in order)

| Status | Condition | Urgency |
| :--- | :--- | :--- |
| `ORDER NOW` | $IP \le ROP$ and days left $\le L$ | `CRITICAL` |
| `ORDER NOW` | $IP \le ROP$ | `HIGH` |
| `ORDER SOON` | $IP \le ROP + 3d$ | `MEDIUM` |
| `OVERSTOCK` | $IP > 2 \times \text{need}$ | `LOW` |
| `OK` | Otherwise | `LOW` |

### Dynamic Pricing Advisory (advisory only — never alters prices)
| Condition | Recommendation |
| :--- | :--- |
| $IP \ge 3 \times \text{need}$ | Consider **20%** promotional discount |
| $2 \times \text{need} < IP < 3 \times \text{need}$ | Consider **10%** promotional discount |
| Otherwise | Maintain regular price |

---

## Repository Structure

```
SmartStock/
├── README.md
├── requirements.txt           # Python backend dependencies
├── .gitignore
├── docs/
│   └── inventory_notes.md     # Full mathematical reference + API guide for Person 3
├── src/
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── server.py          # FastAPI REST backend (serves React dashboard)
│   └── inventory/
│       ├── __init__.py
│       ├── config.py          # Hyperparameters (service level, review period)
│       ├── engine.py          # compute_reorder, simulate_scenario, run_scenario
│       ├── copilot.py         # Early warning + dynamic pricing logic
│       ├── explain.py         # Plain-English reason sentence generator
│       └── backtest.py        # 28-day holdout SMART vs NAIVE simulator
├── tests/
│   ├── fixtures/              # Self-contained stub CSVs (no Person 1 needed)
│   ├── test_engine.py         # Engine unit tests incl. hand-calculated proof
│   ├── test_copilot.py        # Early warning & dynamic pricing tests
│   └── test_backtest.py       # Holdout simulation tests
└── output/                    # Generated files (CSV + JSON)
    ├── orders.csv / .json
    ├── copilot_recommendations.csv / .json
    └── backtest_results.csv / .json
```

---

## Quickstart

### Step 1 — Install Python Dependencies
```bash
pip install -r requirements.txt
```

### Step 2 — Generate Data (Person 1's scripts)
```bash
python src/forecast/generate_data.py
python src/forecast/build_forecast.py
```

### Step 3 — Generate Orders & Copilot Output
```bash
python -m src.inventory.engine
```
Produces `output/orders.csv`, `output/orders.json`, `output/copilot_recommendations.csv`, `output/copilot_recommendations.json`.

### Step 4 — Run Holdout Backtest
```bash
python -m src.inventory.backtest
```
Produces `output/backtest_results.csv` and `output/backtest_results.json`.

### Step 5 — Run the FastAPI Backend
```bash
uvicorn src.api.server:app --reload --port 8000
```
Open `http://localhost:8000/docs` for the interactive Swagger API explorer.

### Step 6 — Run the React Dashboard (Person 3)
```bash
cd app
npm install
npm run dev
```
The Vite dev server starts at `http://localhost:5173` and calls the FastAPI backend at `http://localhost:8000`.

### Step 7 — Run All Tests
```bash
python -m pytest tests/ -v
```
Expected: **14/14 passed**.

---

## FastAPI Endpoint Reference (for Person 3)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/products` | Full product catalog |
| `GET` | `/api/forecast?product_id=P001` | 45-day demand forecast (filter by product) |
| `GET` | `/api/orders?service_level=0.95&review_period_days=7&category=Dairy` | Computed replenishment orders |
| `GET` | `/api/copilot?service_level=0.95` | AI Copilot enriched data (urgency, early warnings, pricing) |
| `POST` | `/api/scenario` | What-if demand surge / supplier delay simulation |
| `GET` | `/api/backtest` | 28-day holdout SMART vs NAIVE results |
| `GET` | `/api/alerts` | Unexpected demand spike alerts |
| `GET` | `/api/accuracy` | Model vs baseline accuracy metrics |
| `GET` | `/api/categories` | Distinct product categories for filter dropdowns |

**Scenario POST body example:**
```json
{
  "uplift_pct": 60,
  "start_date": "2026-11-03",
  "end_date": "2026-11-08",
  "product_ids": ["P011"],
  "lead_time_extra_days": 0,
  "service_level": 0.95,
  "review_period_days": 7
}
```

---

## AI Copilot Fields (for Person 3's Components)

| Field | Type | Example | Suggested Usage |
| :--- | :--- | :--- | :--- |
| `urgency` | `string` | `"CRITICAL"` | Badge color / sort key |
| `stockout_in_7_days` | `boolean` | `true` | 7-day risk KPI card |
| `early_warning_message` | `string` | `"CRITICAL: Stockout in 1.3 days..."` | Alert banner |
| `copilot_action` | `string` | `"ORDER NOW"` | Action button label |
| `copilot_reason` | `string` | `"Low inventory + upcoming Diwali rush"` | Copilot chat bubble |
| `excess_units` | `integer` | `250` | Overstock metric |
| `pricing_recommendation` | `string` | `"Consider 10% promotional discount"` | Markdown advisory card |
| `pricing_reason` | `string` | `"Overstock (2.3x cycle need)..."` | Tooltip / detail row |

---

## Proof of Value (Hand-Calculated)

Given: flat 100 units/day, $L=4$, current stock $300$, $\sigma=20$, service level 95%.
- $Z = 1.64485$
- $SS = 1.64485 \times 20 \times \sqrt{4} = 65.79$ units
- $ROP = 400 + 65.79 = 466$ units (rounded up)
- $\text{order\_qty} = \lceil 1100 + 65.79 - 300 \rceil = \mathbf{866}$ units → status `ORDER NOW`, urgency `CRITICAL`

In 28-day holdout backtesting, `SMART` safely reduced average warehouse inventory from **499.4 → 308.2 units (−38%)** with zero stockouts, vs. the `NAIVE` heuristic policy.

---

## Team Roles
| Person | Role | Branch |
| :--- | :--- | :--- |
| Person 1 | Data + Forecast Engineer | `p1-forecast` |
| Person 2 | Inventory Engine Engineer | `p2-inventory` |
| Person 3 | Dashboard (React + Vite + TailwindCSS) | `p3-dashboard` |

> **Data note:** All sales data is synthetically generated using Poisson demand models with trend, seasonality, holiday and promotional effects.
