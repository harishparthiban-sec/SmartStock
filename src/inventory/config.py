"""Configuration parameters for the inventory reorder engine.

These default parameters follow the SmartStock specification (Section A6 & Part C).
"""

SERVICE_LEVEL = 0.95
REVIEW_PERIOD_DAYS = 7
ORDER_SOON_BUFFER_DAYS = 3
OVERSTOCK_FACTOR = 2.0
DEFAULT_SIGMA_PCT = 0.25  # used when error_df is missing for a product
