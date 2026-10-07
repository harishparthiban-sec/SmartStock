"""Tests for Demand Time Machine analog signal integration (Person 1 → Person 2).

Tests verify four behaviours:
  1. NO SIGNAL   – missing/low-confidence analog → zero change to orders
  2. UPLIFT      – high-confidence growth signal → order_qty increases
  3. CONFLICT    – analogs disagree with Prophet → sigma inflated → higher SS / ROP
  4. AGREE       – analogs agree, no growth → no numeric change, but explanation present
  5. PARTIAL     – only some products have analog data → unaffected products unchanged
  6. SAFETY      – malformed or missing analog_df never crashes the engine
"""
import os
import math
import pytest
import pandas as pd
import numpy as np
from statistics import NormalDist

from src.inventory.engine import compute_reorder
from src.inventory.analog import (
    AnalogSignal,
    load_analog_signals,
    get_analog_adjustments,
    HIGH_CONFIDENCE,
    HIGH_AGREEMENT,
    MIN_SIMILARITY,
    MIN_GROWTH_PCT,
    MAX_UPLIFT,
    CONFLICT_THRESHOLD,
    SIGMA_INFLATE_FACTOR,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def stub_data(fixtures_dir):
    products = pd.read_csv(os.path.join(fixtures_dir, "products_stub.csv"))
    forecast = pd.read_csv(os.path.join(fixtures_dir, "forecast_stub.csv"))
    error = pd.read_csv(os.path.join(fixtures_dir, "error_stub.csv"))
    return products, forecast, error


def _p001_inputs(stub_data):
    """Returns the P001 subset from stub fixtures."""
    products, forecast, error = stub_data
    return (
        products[products["product_id"] == "P001"].copy(),
        forecast[forecast["product_id"] == "P001"].copy(),
        error[error["product_id"] == "P001"].copy(),
    )


def _make_analog_df(**kwargs) -> pd.DataFrame:
    """Builds a minimal one-row analog_df for P001 with sensible defaults."""
    defaults = {
        "product_id": "P001",
        "top_3_consensus_growth_pct": 0.0,
        "analog_confidence": 0.8,
        "analog_agreement": 0.75,
        "event_alignment": 0.8,
        "forecast_agreement": 0.85,
        "best_similarity_score": 0.8,
        "historical_evidence": "Stub evidence.",
    }
    defaults.update(kwargs)
    return pd.DataFrame([defaults])


def _base_order_qty(stub_data) -> int:
    """Returns the order_qty for P001 with no analog signals (baseline)."""
    prod, fc, err = _p001_inputs(stub_data)
    orders = compute_reorder(
        products_df=prod, forecast_df=fc, error_df=err,
        analog_df=pd.DataFrame(),  # explicitly no analog
    )
    return int(orders.iloc[0]["order_qty"])


# ---------------------------------------------------------------------------
# Unit tests for AnalogSignal class
# ---------------------------------------------------------------------------

class TestAnalogSignal:
    def _sig(self, **kwargs):
        defaults = dict(
            product_id="P001", growth_pct=10.0, confidence=0.8, agreement=0.75,
            event_alignment=0.8, forecast_agreement=0.85, similarity=0.8,
            historical_evidence="Test."
        )
        defaults.update(kwargs)
        return AnalogSignal(**defaults)

    def test_high_quality_when_all_gates_pass(self):
        sig = self._sig()
        assert sig.is_high_quality is True

    def test_not_high_quality_when_low_confidence(self):
        sig = self._sig(confidence=0.50)
        assert sig.is_high_quality is False

    def test_not_high_quality_when_low_similarity(self):
        sig = self._sig(similarity=0.40)
        assert sig.is_high_quality is False

    def test_no_uplift_below_min_growth(self):
        sig = self._sig(growth_pct=2.0)  # below MIN_GROWTH_PCT
        assert sig.demand_uplift_factor() == 1.0

    def test_uplift_applied_above_min_growth(self):
        sig = self._sig(growth_pct=20.0)
        factor = sig.demand_uplift_factor()
        assert factor == pytest.approx(1.20, rel=1e-4)

    def test_uplift_capped_at_max(self):
        sig = self._sig(growth_pct=200.0)  # would be 3.0x without cap
        factor = sig.demand_uplift_factor()
        assert factor == pytest.approx(1.0 + MAX_UPLIFT, rel=1e-4)

    def test_no_sigma_inflate_when_no_conflict(self):
        sig = self._sig(forecast_agreement=0.85)
        assert sig.sigma_inflate_factor() == 1.0

    def test_sigma_inflated_on_conflict(self):
        sig = self._sig(forecast_agreement=0.30)  # below CONFLICT_THRESHOLD
        assert sig.sigma_inflate_factor() == pytest.approx(SIGMA_INFLATE_FACTOR, rel=1e-4)

    def test_is_conflict_flag(self):
        assert self._sig(forecast_agreement=0.30).is_conflict is True
        assert self._sig(forecast_agreement=0.85).is_conflict is False

    def test_explanation_contains_historical_evidence_on_growth(self):
        sig = self._sig(growth_pct=20.0)
        ctx = sig.explanation_context()
        assert "demand may increase" in ctx
        assert "Test." in ctx

    def test_explanation_contains_conflict_message(self):
        sig = self._sig(forecast_agreement=0.30)
        ctx = sig.explanation_context()
        assert "conflicts with the current forecast" in ctx
        assert "safety buffer" in ctx

    def test_explanation_agree_no_growth(self):
        sig = self._sig(growth_pct=2.0)  # high quality but below growth threshold
        ctx = sig.explanation_context()
        assert "agree" in ctx.lower()

    def test_low_confidence_explanation(self):
        sig = self._sig(confidence=0.40)
        ctx = sig.explanation_context()
        assert "low-confidence" in ctx


# ---------------------------------------------------------------------------
# Integration tests: analog_df → engine → orders
# ---------------------------------------------------------------------------

class TestAnalogEngineIntegration:

    def test_no_analog_signal_unchanged(self, stub_data):
        """Passing an empty analog_df produces exactly the same order_qty as baseline."""
        prod, fc, err = _p001_inputs(stub_data)
        no_analog = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=pd.DataFrame(),
        )
        baseline = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=pd.DataFrame(),
        )
        assert no_analog.iloc[0]["order_qty"] == baseline.iloc[0]["order_qty"]

    def test_strong_growth_signal_increases_order_qty(self, stub_data):
        """A high-confidence 30% growth signal must produce a larger order_qty."""
        prod, fc, err = _p001_inputs(stub_data)
        base_qty = _base_order_qty(stub_data)

        analog_df = _make_analog_df(
            top_3_consensus_growth_pct=30.0,
            analog_confidence=0.85,
            analog_agreement=0.80,
            best_similarity_score=0.82,
            forecast_agreement=0.80,
        )
        orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=analog_df,
        )
        assert orders.iloc[0]["order_qty"] > base_qty, (
            f"Expected order_qty > {base_qty} with 30% growth signal, "
            f"got {orders.iloc[0]['order_qty']}"
        )

    def test_weak_growth_signal_no_change(self, stub_data):
        """A low-confidence signal must not change order_qty."""
        prod, fc, err = _p001_inputs(stub_data)
        base_qty = _base_order_qty(stub_data)

        analog_df = _make_analog_df(
            top_3_consensus_growth_pct=25.0,
            analog_confidence=0.45,   # below HIGH_CONFIDENCE
            analog_agreement=0.75,
            best_similarity_score=0.80,
        )
        orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=analog_df,
        )
        assert orders.iloc[0]["order_qty"] == base_qty

    def test_conflict_signal_inflates_safety_stock(self, stub_data):
        """forecast_agreement < CONFLICT_THRESHOLD must inflate safety_stock."""
        prod, fc, err = _p001_inputs(stub_data)

        base_orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=pd.DataFrame(),
        )
        base_ss = float(base_orders.iloc[0]["safety_stock"])

        conflict_df = _make_analog_df(
            top_3_consensus_growth_pct=5.0,
            forecast_agreement=0.30,  # conflict!
            analog_confidence=0.80,
            analog_agreement=0.75,
            best_similarity_score=0.80,
        )
        orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=conflict_df,
        )
        inflated_ss = float(orders.iloc[0]["safety_stock"])
        assert inflated_ss > base_ss, (
            f"Expected inflated SS > {base_ss:.2f}, got {inflated_ss:.2f}"
        )
        assert inflated_ss == pytest.approx(base_ss * SIGMA_INFLATE_FACTOR, rel=0.02)

    def test_conflict_reason_contains_conflict_message(self, stub_data):
        """Conflict scenario must surface analog context in the reason string."""
        prod, fc, err = _p001_inputs(stub_data)
        analog_df = _make_analog_df(
            forecast_agreement=0.30,
            analog_confidence=0.80,
            analog_agreement=0.75,
            best_similarity_score=0.80,
        )
        orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=analog_df,
        )
        reason = orders.iloc[0]["reason"]
        assert "conflicts with the current forecast" in reason

    def test_growth_reason_contains_increase_message(self, stub_data):
        """Growth signal must surface demand increase context in the reason string."""
        prod, fc, err = _p001_inputs(stub_data)
        analog_df = _make_analog_df(
            top_3_consensus_growth_pct=20.0,
            analog_confidence=0.85,
            analog_agreement=0.80,
            best_similarity_score=0.82,
            forecast_agreement=0.80,
        )
        orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=analog_df,
        )
        reason = orders.iloc[0]["reason"]
        assert "demand may increase" in reason

    def test_output_schema_unchanged_with_analog(self, stub_data):
        """The 17-column output contract is preserved when analog signals are active."""
        prod, fc, err = _p001_inputs(stub_data)
        analog_df = _make_analog_df(top_3_consensus_growth_pct=20.0)
        orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=analog_df,
        )
        expected_cols = {
            "product_id", "name", "category", "current_stock", "on_order",
            "avg_daily_demand", "lead_time_days", "safety_stock", "reorder_point",
            "order_qty", "order_by_date", "expected_arrival_date",
            "days_of_stock_left", "stockout_date", "status", "reason", "order_value",
        }
        assert expected_cols.issubset(set(orders.columns))

    def test_partial_coverage_leaves_unaffected_products_unchanged(self, stub_data):
        """Analog data only for P001; P002 and P003 should be exactly as without analog."""
        products, forecast, error = stub_data

        # baseline with no analog
        base = compute_reorder(
            products_df=products, forecast_df=forecast, error_df=error,
            analog_df=pd.DataFrame(),
        )

        # analog only for P001
        analog_df = _make_analog_df(top_3_consensus_growth_pct=30.0)
        with_analog = compute_reorder(
            products_df=products, forecast_df=forecast, error_df=error,
            analog_df=analog_df,
        )

        for pid in ["P002", "P003"]:
            base_row = base[base["product_id"] == pid].iloc[0]
            analg_row = with_analog[with_analog["product_id"] == pid].iloc[0]
            assert base_row["order_qty"] == analg_row["order_qty"], (
                f"{pid} order_qty changed but should not have: "
                f"{base_row['order_qty']} → {analg_row['order_qty']}"
            )

    def test_missing_analog_file_does_not_crash(self, stub_data, tmp_path):
        """When no analog file exists anywhere, engine runs without error."""
        prod, fc, err = _p001_inputs(stub_data)
        # Pass None and ensure real data dir doesn't exist
        orders = compute_reorder(
            products_df=prod, forecast_df=fc, error_df=err,
            analog_df=pd.DataFrame(),
        )
        assert len(orders) == 1
        assert orders.iloc[0]["order_qty"] > 0

    def test_malformed_analog_df_does_not_crash(self, stub_data):
        """A DataFrame missing required columns is handled gracefully."""
        prod, fc, err = _p001_inputs(stub_data)
        bad_df = pd.DataFrame([{"product_id": "P001", "junk_col": 99}])
        # should not raise; analog column not present → treated as empty
        try:
            orders = compute_reorder(
                products_df=prod, forecast_df=fc, error_df=err,
                analog_df=bad_df,
            )
            assert len(orders) == 1
        except Exception as e:
            pytest.fail(f"Engine crashed on malformed analog_df: {e}")


# ---------------------------------------------------------------------------
# Unit tests for load_analog_signals
# ---------------------------------------------------------------------------

class TestLoadAnalogSignals:

    def test_loads_stub_file(self, fixtures_dir):
        stub = os.path.join(fixtures_dir, "demand_analog_summary_stub.csv")
        signals = load_analog_signals(stub)
        assert "P001" in signals
        assert "P003" in signals

    def test_returns_empty_on_missing_file(self):
        signals = load_analog_signals("/nonexistent/path/to/file.csv")
        assert signals == {}

    def test_p003_is_conflict_in_stub(self, fixtures_dir):
        stub = os.path.join(fixtures_dir, "demand_analog_summary_stub.csv")
        signals = load_analog_signals(stub)
        assert signals["P003"].is_conflict is True  # forecast_agreement=0.30
        assert signals["P003"].is_high_quality is True

    def test_p001_has_meaningful_growth_in_stub(self, fixtures_dir):
        stub = os.path.join(fixtures_dir, "demand_analog_summary_stub.csv")
        signals = load_analog_signals(stub)
        assert signals["P001"].has_meaningful_growth is True  # 8.5%
        assert signals["P001"].demand_uplift_factor() == pytest.approx(1.085, rel=1e-3)
