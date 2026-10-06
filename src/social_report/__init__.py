"""Deterministic core for auditable social-media reporting."""

from .metrics import aggregate_campaign, audit_campaign, calculate_single_item
from .stories import summarize_story_series
from .validation import validate_extraction

__all__ = [
    "aggregate_campaign",
    "audit_campaign",
    "calculate_single_item",
    "summarize_story_series",
    "validate_extraction",
]

__version__ = "2.0.0"
