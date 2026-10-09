"""Validation and normalization for model-produced structured extraction."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Tuple

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


def _parse_numeric_string(raw_str: str) -> Tuple[Optional[float], str, Optional[str]]:
    """Parse numeric strings such as '1,100', '1.2k', '10M', '50', 'N/A', etc.

    Returns:
        (value, precision, evidence_text)
    """
    s = raw_str.strip()
    if not s or s.lower() in {"null", "none", "n/a", "missing", "-", "nil"}:
        return None, "missing", None

    cleaned = s.replace(",", "").replace(" ", "")
    multiplier = 1.0
    is_approx = False
    lowered = cleaned.lower()

    if lowered.endswith("k"):
        multiplier = 1_000.0
        cleaned = cleaned[:-1]
        is_approx = True
    elif lowered.endswith("m"):
        multiplier = 1_000_000.0
        cleaned = cleaned[:-1]
        is_approx = True
    elif lowered.endswith("b"):
        multiplier = 1_000_000_000.0
        cleaned = cleaned[:-1]
        is_approx = True

    try:
        val = float(cleaned) * multiplier
        if val.is_integer():
            val = int(val)
        prec = "approximate" if is_approx else "exact"
        evid = s if is_approx else None
        return val, prec, evid
    except (ValueError, TypeError):
        return None, "unreadable", s


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
    if isinstance(raw, str):
        val, prec, evid = _parse_numeric_string(raw)
        measurement: Dict[str, Any] = {"value": val, "precision": prec}
        if evid:
            measurement["evidence_text"] = evid
        if prec == "approximate":
            warnings.append(f"metric {name!r} is approximate with evidence {evid!r}")
        elif prec == "unreadable":
            warnings.append(f"metric {name!r} could not be parsed from string {raw!r}")
        if val is not None and val < 0:
            raise ValueError(f"metric {name!r} cannot be negative")
        return measurement, warnings
    if not isinstance(raw, Mapping):
        raise ValueError(f"metric {name!r} must be a measurement object")

    measurement = dict(raw)
    precision = measurement.get("precision")
    value = measurement.get("value")

    if isinstance(value, str):
        v_num, v_prec, v_evid = _parse_numeric_string(value)
        value = v_num
        measurement["value"] = value
        if not precision or precision not in PRECISIONS:
            precision = v_prec
            measurement["precision"] = precision
        if v_evid and not measurement.get("evidence_text"):
            measurement["evidence_text"] = v_evid

    if precision not in PRECISIONS:
        precision = "missing" if value is None else "exact"
        measurement["precision"] = precision

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

    if (
        isinstance(payload, Mapping)
        and "properties" in payload
        and isinstance(payload["properties"], Mapping)
    ):
        payload = payload["properties"]
    assets_raw = payload.get("assets") if isinstance(payload, Mapping) else None
    if (
        assets_raw is None
        and isinstance(payload, Mapping)
        and isinstance(payload.get("campaign"), Mapping)
    ):
        campaign_map = payload["campaign"]
        if "properties" in campaign_map and isinstance(campaign_map["properties"], Mapping):
            campaign_map = campaign_map["properties"]
        assets_raw = campaign_map.get("assets")
    assets = assets_raw if isinstance(assets_raw, list) else [payload]
    normalized_assets: List[Dict[str, Any]] = []
    all_warnings: List[str] = []

    for index, raw_asset in enumerate(assets):
        if not isinstance(raw_asset, Mapping):
            raise ValueError(f"asset at index {index} must be an object")
        asset = deepcopy(dict(raw_asset))
        props = asset.get("properties")
        if isinstance(props, Mapping) and ("asset_group_id" in props or "id" in props):
            asset = deepcopy(dict(props))
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
            if not isinstance(name, str):
                continue
            canonical_name = name.strip().lower().replace(" ", "_").replace("-", "_")
            target_name = canonical_name if canonical_name in KNOWN_METRICS else name
            if target_name not in KNOWN_METRICS:
                warnings.append(f"unknown metric {target_name!r} preserved for review")
            metric, metric_warnings = _normalize_measurement(target_name, raw_metric)
            normalized_metrics[target_name] = metric
            warnings.extend(metric_warnings)
        asset["metrics"] = normalized_metrics

        status = asset.get("review_status", "verified")
        if not isinstance(status, str) or status not in REVIEW_STATUSES:
            warnings.append(f"unsupported review_status {status!r} normalized to 'needs_review'")
            status = "needs_review"
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
