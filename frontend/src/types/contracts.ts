// SmartStock Frontend TypeScript Contracts
// Sourced strictly from the provided specifications

export interface Product {
  product_id: string;
  name: string;
  category: string;
  lead_time_days: number;
  current_stock: number;
  on_order: number;
  unit_cost: number;
}

export interface Forecast {
  date: string; // YYYY-MM-DD
  product_id: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
}

export interface HistoricalSale {
  date: string; // YYYY-MM-DD
  product_id: string;
  units_sold: number;
  promo_flag: number; // 0 or 1
  price: number;
}

export interface Holiday {
  date: string; // YYYY-MM-DD
  holiday_name: string;
}

export interface FuturePromo {
  date: string; // YYYY-MM-DD
  product_id: string;
  promo_flag: number; // 0 or 1
}

export interface ForecastError {
  product_id: string;
  sigma: number;
  mae: number;
  wape_pct: number;
}

export interface BacktestForecast {
  date: string; // YYYY-MM-DD
  product_id: string;
  yhat: number;
  yhat_lower: number;
  yhat_upper: number;
  actual_units: number;
}

export interface Alert {
  date: string; // YYYY-MM-DD
  product_id: string;
  actual_units: number;
  yhat_upper: number;
  excess_pct: number;
  severity: "HIGH" | "MEDIUM" | "LOW";
}

export interface Accuracy {
  product_id: string;
  mae_model: number;
  wape_model: number;
  mae_baseline: number;
  wape_baseline: number;
  improvement_pct: number;
}

export interface InventoryBacktest {
  product_id: string;
  policy: "NAIVE" | "SMART";
  stockout_days: number;
  units_short: number;
  fill_rate_pct: number;
  avg_on_hand_units: number;
}

export interface InventoryResult {
  product_id: string;
  name: string;
  category: string;
  current_stock: number;
  on_order: number;
  avg_daily_demand: number;
  lead_time_days: number;
  safety_stock: number;
  reorder_point: number;
  order_qty: number;
  order_by_date: string; // YYYY-MM-DD
  expected_arrival_date: string; // YYYY-MM-DD
  days_of_stock_left: number;
  stockout_date: string; // YYYY-MM-DD
  status: "CRITICAL" | "WARNING" | "HEALTHY" | "OVERSTOCKED";
  reason: string;
  order_value: number;
}

export interface DemandAnalogSummary {
  product_id: string;
  as_of_date: string;
  best_match_date: string;
  best_similarity_score: number;
  top_3_consensus_growth_pct: number;
  analog_agreement: "HIGH" | "MEDIUM" | "LOW";
  analog_confidence: "HIGH" | "MEDIUM" | "LOW";
  event_alignment: "STRONG_AGREEMENT" | "AGREEMENT" | "CONFLICT" | "NONE";
  prophet_change_pct: number;
  forecast_agreement: "STRONG_AGREEMENT" | "AGREEMENT" | "CONFLICT" | "NONE";
  historical_evidence: string;
}

export interface DemandAnalog {
  product_id: string;
  as_of_date: string;
  window_days: number;
  analog_rank: number;
  historical_match_date: string;
  similarity_score: number;
  current_avg_demand: number;
  historical_match_avg_demand: number;
  historical_future_avg_demand: number;
  historical_change_pct: number;
  historical_holiday: string | null;
  historical_promo: number;
  current_holiday: string | null;
  current_promo: number;
  event_alignment: "STRONG_AGREEMENT" | "AGREEMENT" | "CONFLICT" | "NONE";
  analog_agreement: "HIGH" | "MEDIUM" | "LOW";
  analog_confidence: "HIGH" | "MEDIUM" | "LOW";
  prophet_change_pct: number;
  forecast_agreement: "STRONG_AGREEMENT" | "AGREEMENT" | "CONFLICT" | "NONE";
  explanation: string;
}

export interface CopilotResponse {
  question: string;
  answer: string;
  related_product_ids?: string[];
  evidence_points?: string[];
}

export interface WhatIfScenario {
  id: string;
  name: string;
  uplift_pct: number;
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
  product_ids: string[];
  lead_time_extra_days: number;
  service_level?: number;
  review_period_days?: number;
}

export interface ScenarioComparison {
  product_id: string;
  name: string;
  order_qty_before: number;
  order_qty_after: number;
  delta: number;
  status_before: string;
  status_after: string;
}
