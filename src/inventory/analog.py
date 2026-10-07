"""Demand Time Machine (DTM) analog signal integration for SmartStock Inventory Engine.

Reads Person 1's `data/demand_analog_summary.csv` and translates the historical
analog evidence into three actionable inventory adjustments:

1. DEMAND UPLIFT: When analogs strongly agree on future growth, we increase the
   effective `need` used for order quantity calculation by a confidence-weighted factor.
   The forecast CSV (yhat) is NEVER modified.

2. SIGMA INFLATION (CONFLICT RISK): When analog evidence conflicts with the Prophet
   forecast, we increase sigma to widen the safety stock buffer.

3. EXPLANATION CONTEXT: Adds plain-English analog context to every reorder reason.

Column definitions from demand_analog_summary.csv:
  product_id             – product identifier
  top_3_consensus_growth_pct – mean growth pct across the top-3 best analog windows
  analog_confidence      – 0-1, how reliable the analog match is overall
  analog_agreement       – 0-1, how much the top-3 analogs agree with each other
  event_alignment        – 0-1, how well historical events map to upcoming period
  forecast_agreement     – 0-1, how much analogs agree WITH the Prophet forecast
  best_similarity_score  – 0-1, quality of the single best analog window
  historical_evidence    – free-text summary from Person 1

Tuning thresholds (adjust without changing any output contracts):
  HIGH_CONFIDENCE   = 0.70   analog_confidence threshold to trust growth signal
  HIGH_AGREEMENT    = 0.65   analog_agreement threshold to apply uplift
  MIN_SIMILARITY    = 0.65   minimum best_similarity_score to use
  MIN_GROWTH        = 5.0    minimum growth_pct to bother applying uplift
  MAX_UPLIFT        = 0.40   cap demand uplift at 40% (prevents runaway order sizes)
  CONFLICT_THRESHOLD= 0.45   forecast_agreement below this → conflict flag
  SIGMA_INFLATE     = 1.50   multiply sigma by this factor on conflict
"""

from typing import Dict, Optional, Tuple
import pandas as pd

# ---------------------------------------------------------------------------
# Thresholds – clearly named so they can be explained in a presentation
# ---------------------------------------------------------------------------
HIGH_CONFIDENCE = 0.70
HIGH_AGREEMENT = 0.65
MIN_SIMILARITY = 0.65
MIN_GROWTH_PCT = 5.0
MAX_UPLIFT = 0.40
CONFLICT_THRESHOLD = 0.45
SIGMA_INFLATE_FACTOR = 1.50


class AnalogSignal:
    """Parsed and interpreted signal for one product from the DTM output."""

    def __init__(
        self,
        product_id: str,
        growth_pct: float,
        confidence: float,
        agreement: float,
        event_alignment: float,
        forecast_agreement: float,
        similarity: float,
        historical_evidence: str,
    ):
        self.product_id = product_id
        self.growth_pct = growth_pct
        self.confidence = confidence
        self.agreement = agreement
        self.event_alignment = event_alignment
        self.forecast_agreement = forecast_agreement
        self.similarity = similarity
        self.historical_evidence = str(historical_evidence).strip()

    # ---- Core derived properties ------------------------------------------

    @property
    def is_high_quality(self) -> bool:
        """True when all three quality gates pass (confidence, agreement, similarity)."""
        return (
            self.confidence >= HIGH_CONFIDENCE
            and self.agreement >= HIGH_AGREEMENT
            and self.similarity >= MIN_SIMILARITY
        )

    @property
    def has_meaningful_growth(self) -> bool:
        return self.growth_pct >= MIN_GROWTH_PCT

    @property
    def is_conflict(self) -> bool:
        """True when analogs disagree with the Prophet forecast."""
        return self.forecast_agreement < CONFLICT_THRESHOLD

    # ---- Demand uplift -------------------------------------------------------

    def demand_uplift_factor(self) -> float:
        """Returns a multiplier for `need` in the order quantity calculation.

        Logic (easy to explain in a presentation):
          - Only applied if the signal is high-quality AND growth is meaningful.
          - The uplift is the growth_pct capped at MAX_UPLIFT.
          - The cap prevents a single outlier analog from making an outsized order.

        Returns 1.0 (no change) when evidence is weak or absent.
        """
        if not (self.is_high_quality and self.has_meaningful_growth):
            return 1.0
        raw_uplift = self.growth_pct / 100.0
        capped_uplift = min(raw_uplift, MAX_UPLIFT)
        return 1.0 + capped_uplift

    # ---- Sigma inflation on conflict -----------------------------------------

    def sigma_inflate_factor(self) -> float:
        """Returns a multiplier for sigma when analogs conflict with Prophet.

        When analogs strongly disagree with the forecast, we don't blindly
        override the forecast. Instead we widen the safety buffer by inflating
        sigma so the ROP accounts for extra uncertainty.

        Returns 1.0 when there is no conflict.
        """
        if self.is_conflict and self.is_high_quality:
            return SIGMA_INFLATE_FACTOR
        return 1.0

    # ---- Plain-English context -----------------------------------------------

    def explanation_context(self) -> str:
        """One-line analog context appended to the reorder reason."""
        if not self.is_high_quality:
            if self.similarity < MIN_SIMILARITY or self.confidence < HIGH_CONFIDENCE:
                return "Analog evidence is low-confidence; no adjustment applied."
            return ""

        if self.is_conflict:
            return (
                f"Historical evidence conflicts with the current forecast "
                f"(forecast_agreement={self.forecast_agreement:.2f}). "
                f"Additional safety buffer applied due to uncertainty. "
                f"Analog context: {self.historical_evidence}"
            )

        if self.has_meaningful_growth:
            return (
                f"Similar historical demand patterns indicate demand may increase "
                f"(+{self.growth_pct:.1f}% consensus, confidence={self.confidence:.2f}). "
                f"Order quantity raised to cover elevated demand. "
                f"Analog context: {self.historical_evidence}"
            )

        # High quality but no meaningful growth
        return (
            f"Historical analogs agree with the forecast "
            f"(agreement={self.agreement:.2f}). No adjustment needed. "
            f"Analog context: {self.historical_evidence}"
        )


# ---------------------------------------------------------------------------
# Public loader
# ---------------------------------------------------------------------------

def load_analog_signals(
    analog_path: Optional[str] = None,
) -> Dict[str, AnalogSignal]:
    """Loads demand_analog_summary.csv and returns a product_id → AnalogSignal map.

    Args:
        analog_path: Path to the CSV. If None, tries data/demand_analog_summary.csv
                     then tests/fixtures/demand_analog_summary_stub.csv.

    Returns:
        Dict mapping product_id strings to AnalogSignal objects.
        Returns an empty dict safely if the file is missing or malformed.
    """
    import os

    if analog_path is None:
        real = os.path.join("data", "demand_analog_summary.csv")
        stub = os.path.join("tests", "fixtures", "demand_analog_summary_stub.csv")
        analog_path = real if os.path.exists(real) else (stub if os.path.exists(stub) else None)

    if analog_path is None or not os.path.exists(analog_path):
        return {}

    try:
        df = pd.read_csv(analog_path)
    except Exception:
        return {}

    required_cols = {
        "product_id",
        "top_3_consensus_growth_pct",
        "analog_confidence",
        "analog_agreement",
        "event_alignment",
        "forecast_agreement",
        "best_similarity_score",
    }
    if not required_cols.issubset(set(df.columns)):
        return {}

    signals: Dict[str, AnalogSignal] = {}
    for _, row in df.iterrows():
        try:
            pid = str(row["product_id"])
            signals[pid] = AnalogSignal(
                product_id=pid,
                growth_pct=float(row.get("top_3_consensus_growth_pct", 0.0) or 0.0),
                confidence=float(row.get("analog_confidence", 0.0) or 0.0),
                agreement=float(row.get("analog_agreement", 0.0) or 0.0),
                event_alignment=float(row.get("event_alignment", 0.0) or 0.0),
                forecast_agreement=float(row.get("forecast_agreement", 1.0) or 1.0),
                similarity=float(row.get("best_similarity_score", 0.0) or 0.0),
                historical_evidence=str(row.get("historical_evidence", "") or ""),
            )
        except (ValueError, TypeError):
            continue  # skip malformed rows silently

    return signals


# ---------------------------------------------------------------------------
# Helpers used by engine.py
# ---------------------------------------------------------------------------

def get_analog_adjustments(
    pid: str,
    signals: Dict[str, AnalogSignal],
    base_sigma: float,
    base_need: float,
) -> Tuple[float, float, str, bool]:
    """Computes all analog-driven adjustments for a single product.

    Args:
        pid: Product ID string.
        signals: Loaded signal dict from load_analog_signals().
        base_sigma: Sigma before analog adjustment.
        base_need: Need (L+R demand) before analog adjustment.

    Returns:
        Tuple of:
          adjusted_sigma  – sigma after conflict inflation (same as base if no conflict)
          adjusted_need   – need after demand uplift (same as base if no signal)
          analog_context  – plain-English explanation string (may be empty)
          is_conflict     – True if analog evidence conflicts with Prophet forecast
    """
    if pid not in signals:
        return base_sigma, base_need, "", False

    sig = signals[pid]
    adjusted_sigma = base_sigma * sig.sigma_inflate_factor()
    adjusted_need = base_need * sig.demand_uplift_factor()
    context = sig.explanation_context()
    return adjusted_sigma, adjusted_need, context, sig.is_conflict
