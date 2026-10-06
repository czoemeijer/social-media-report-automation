"""Validation and normalization for model-produced structured extraction."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Tuple

from .schemas import PRECISIONS, REVIEW_STATUSES, SCOPES

KNOWN_METRICS = {
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saves",
    "platform_reported_interactions",
    "profile_visits",
    "external_link_taps",
    "business_address_taps",
    "follows",
    "feed_shares",
    "feed_reposts",
}


REVIEW_STATUS_ORDER: Dict[str, int] = {
    "verified": 0,
    "verified_with_warning": 1,
    "needs_review": 2,
    "rejected": 3,
}


def merge_review_status(*statuses: str | None) -> str:
    """Return the most severe review status across candidates.

    Severity lattice:
    verified < verified_with_warning < needs_review < rejected
    """
    valid = [s for s in statuses if s in REVIEW_STATUS_ORDER]
    if not valid:
        return "needs_review"
    return max(valid, key=lambda s: REVIEW_STATUS_ORDER[s])


def _normalize_measurement(name: str, raw: Any) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    if raw is None:
        return {"value": None, "precision": "missing"}, warnings
    if isinstance(raw, bool):
        raise ValueError(f"metric {name!r} must be numeric, not boolean")
    if isinstance(raw, (int, float)):
        if raw < 0:
            raise ValueError(f"metric {name!r} cannot be negative")
        return {"value": raw, "precision": "exact"}, warnings
    if not isinstance(raw, Mapping):
        raise ValueError(f"metric {name!r} must be a measurement object")

    measurement = dict(raw)
    precision = measurement.get("precision")
    value = measurement.get("value")
    if precision not in PRECISIONS:
        raise ValueError(f"metric {name!r} has unsupported precision {precision!r}")
    if isinstance(value, bool) or (value is not None and not isinstance(value, (int, float))):
        raise ValueError(f"metric {name!r} value must be numeric or null")
    if value is not None and value < 0:
        raise ValueError(f"metric {name!r} cannot be negative")
    if precision in {"missing", "unreadable"} and value is not None:
        raise ValueError(f"metric {name!r} must be null when precision is {precision}")
    if precision in {"exact", "approximate"} and value is None:
        raise ValueError(f"metric {name!r} needs a value when precision is {precision}")
    confidence = measurement.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise ValueError(f"metric {name!r} confidence must be between 0 and 1")
    if precision == "approximate" and not measurement.get("evidence_text"):
        warnings.append(f"metric {name!r} is approximate but has no evidence_text")
    return measurement, warnings


def validate_extraction(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate one asset or a payload containing an ``assets`` list.

    The function intentionally performs deterministic validation without invoking a
    model. It accepts legacy numeric metric values and normalizes them into the
    canonical measurement form.
    """

    assets_raw = payload.get("assets") if isinstance(payload, Mapping) else None
    assets = assets_raw if isinstance(assets_raw, list) else [payload]
    normalized_assets: List[Dict[str, Any]] = []
    all_warnings: List[str] = []

    for index, raw_asset in enumerate(assets):
        if not isinstance(raw_asset, Mapping):
            raise ValueError(f"asset at index {index} must be an object")
        asset = deepcopy(dict(raw_asset))
        asset_id = asset.get("asset_group_id") or asset.get("id")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise ValueError(f"asset at index {index} is missing asset_group_id")
        asset["asset_group_id"] = asset_id

        scope = asset.get("scope", "unknown")
        if scope not in SCOPES:
            raise ValueError(f"asset {asset_id!r} has unsupported scope {scope!r}")
        if asset.get("has_ad_disclaimer"):
            scope = "mixed_or_unknown"
        asset["scope"] = scope

        metrics_raw = asset.get("metrics", {})
        if not isinstance(metrics_raw, Mapping):
            raise ValueError(f"asset {asset_id!r} metrics must be an object")
        normalized_metrics: Dict[str, Dict[str, Any]] = {}
        warnings = list(asset.get("warnings") or [])
        for name, raw_metric in metrics_raw.items():
            if name not in KNOWN_METRICS:
                warnings.append(f"unknown metric {name!r} preserved for review")
            metric, metric_warnings = _normalize_measurement(name, raw_metric)
            normalized_metrics[name] = metric
            warnings.extend(metric_warnings)
        asset["metrics"] = normalized_metrics

        status = asset.get("review_status", "verified")
        if status not in REVIEW_STATUSES:
            raise ValueError(f"asset {asset_id!r} has unsupported review_status {status!r}")
        low_confidence = [
            name
            for name, metric in normalized_metrics.items()
            if metric.get("confidence") is not None and metric["confidence"] < 0.75
        ]
        if low_confidence:
            warnings.append(
                "low-confidence metrics require targeted review: " + ", ".join(low_confidence)
            )
            status = merge_review_status(status, "needs_review")
        if warnings:
            status = merge_review_status(status, "verified_with_warning")
        asset["review_status"] = status
        asset["warnings"] = warnings
        normalized_assets.append(asset)
        all_warnings.extend(f"{asset_id}: {warning}" for warning in warnings)

    overall_status = merge_review_status(*(a["review_status"] for a in normalized_assets))
    if all_warnings:
        overall_status = merge_review_status(overall_status, "verified_with_warning")

    return {
        "assets": normalized_assets,
        "review_status": overall_status,
        "warnings": all_warnings,
    }


def flatten_asset_metrics(asset: Mapping[str, Any]) -> Dict[str, Any]:
    """Convert canonical measurements into the flat deterministic-core input."""

    flattened = {key: value for key, value in asset.items() if key != "metrics"}
    metrics = asset.get("metrics", {})
    if isinstance(metrics, Mapping):
        for name, measurement in metrics.items():
            if isinstance(measurement, Mapping):
                flattened[name] = measurement.get("value")
                if measurement.get("precision") == "approximate":
                    flattened[f"{name}_is_approximate"] = True
            else:
                flattened[name] = measurement
    return flattened
