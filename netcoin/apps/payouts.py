"""Payout helper boundary for app-layer plans.

The payout implementation still lives on AppStore for compatibility; this module
exists as a stable import location for future extraction and tests documenting the
new package split.
"""

from __future__ import annotations

PAYOUT_STATUS_REVIEW = "operator_review_required"
PAYOUT_KIND_MARKET = "prediction_market"
