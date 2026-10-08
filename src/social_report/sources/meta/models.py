"""Small shared model helpers for Meta-native payload normalization."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Dict, Mapping, Optional


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def decimal_or_none(value: object) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def number_or_none(value: object) -> Optional[object]:
    """Convert Graph numeric strings without converting money to binary floats."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    try:
        decimal = Decimal(value)
    except InvalidOperation:
        return None
    if decimal == decimal.to_integral_value():
        return int(decimal)
    return str(decimal)


def provenance(
    *,
    platform: str,
    object_type: str,
    object_id: Optional[str],
    metric_name: Optional[str],
    api_version: str,
    scope: str,
    retrieved_at: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    return {
        "source_type": "api",
        "provider": "meta",
        "platform": platform,
        "object_type": object_type,
        "object_id": object_id,
        "metric_name": metric_name,
        "retrieved_at": retrieved_at or utc_now(),
        "api_version": api_version,
        "scope": scope,
    }


def action_mapping(values: object) -> Mapping[str, object]:
    result: Dict[str, object] = {}
    if not isinstance(values, list):
        return result
    for row in values:
        if not isinstance(row, dict):
            continue
        key = row.get("action_type")
        value = number_or_none(row.get("value"))
        if isinstance(key, str) and value is not None:
            result[key] = value
    return result
