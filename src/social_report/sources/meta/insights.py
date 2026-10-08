"""Shared parsing for Meta Insights metric response rows."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .models import number_or_none


def insight_values(payload: Mapping[str, Any]) -> Dict[str, object]:
    result: Dict[str, object] = {}
    data = payload.get("data", [])
    if not isinstance(data, list):
        return result
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        values = item.get("values")
        raw_value: object = None
        if isinstance(values, list) and values and isinstance(values[0], dict):
            raw_value = values[0].get("value")
        elif "value" in item:
            raw_value = item.get("value")
        value = number_or_none(raw_value)
        if value is not None:
            result[str(item["name"])] = value
    return result
