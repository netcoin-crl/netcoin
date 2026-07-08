"""Competitive-feature scaffolds for NetCoin.

This package tracks professional crypto-product capabilities as code-visible
roadmap structures. The modules are scaffolds, not claims of production
readiness or legal/security approval.
"""

from .level5 import (
    LEVEL5_SCORE,
    LEVEL5_STATUS,
    all_area_smokes,
    build_level5_report,
    level5_area_controls,
    level5_features,
    validate_level5,
)
from .registry import (
    COMPETITIVE_AREAS,
    COMPETITIVE_FEATURES,
    FeatureArea,
    FeatureSkeleton,
    area_slugs,
    build_competitive_gap_report,
    feature_count,
    get_area,
)

__all__ = [
    "COMPETITIVE_AREAS",
    "COMPETITIVE_FEATURES",
    "LEVEL5_SCORE",
    "LEVEL5_STATUS",
    "FeatureArea",
    "FeatureSkeleton",
    "all_area_smokes",
    "area_slugs",
    "build_competitive_gap_report",
    "build_level5_report",
    "feature_count",
    "get_area",
    "level5_area_controls",
    "level5_features",
    "validate_level5",
]
