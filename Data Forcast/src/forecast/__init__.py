"""
SmartStock Forecast Package
"""

try:
    from .forecast import get_forecast
    from .spikes import detect_spikes
    from .demand_signals import compute_demand_signals, get_demand_signals, get_copilot_explanation
    from .demand_time_machine import run_time_machine, backtest_time_machine
except ImportError:
    from forecast import get_forecast
    from spikes import detect_spikes
    from demand_signals import compute_demand_signals, get_demand_signals, get_copilot_explanation
    from demand_time_machine import run_time_machine, backtest_time_machine

__all__ = [
    "get_forecast",
    "detect_spikes",
    "compute_demand_signals",
    "get_demand_signals",
    "get_copilot_explanation",
    "run_time_machine",
    "backtest_time_machine",
]
