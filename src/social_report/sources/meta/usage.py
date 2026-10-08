"""Sanitized, opportunistic Meta usage-header telemetry.

Meta returns these headers on normal API responses.  Reading them here does not
issue any additional requests and deliberately discards business object IDs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

USAGE_FIELDS = ("call_count", "total_cputime", "total_time")


def _number(value: object) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(0.0, float(value))
    return None


def _json_header(headers: Mapping[str, str], name: str) -> object:
    raw = next((value for key, value in headers.items() if key.lower() == name.lower()), None)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return None


def _usage_values(value: object) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    result: Dict[str, float] = {}
    for field_name in USAGE_FIELDS:
        parsed = _number(value.get(field_name))
        if parsed is not None:
            result[field_name] = parsed
    return result


def parse_usage_headers(headers: Mapping[str, str]) -> Mapping[str, object]:
    """Return only documented usage values, with account/business IDs removed."""

    result: Dict[str, object] = {}
    app = _usage_values(_json_header(headers, "X-App-Usage"))
    if app:
        result["app"] = app

    raw_ad_account = _json_header(headers, "X-Ad-Account-Usage")
    if isinstance(raw_ad_account, dict):
        ad_account: Dict[str, object] = {}
        utilization = _number(raw_ad_account.get("acc_id_util_pct"))
        regain = _number(raw_ad_account.get("reset_time_duration"))
        tier = raw_ad_account.get("ads_api_access_tier")
        if utilization is not None:
            ad_account["acc_id_util_pct"] = utilization
        if regain is not None:
            ad_account["reset_time_duration_seconds"] = regain
        if isinstance(tier, str):
            ad_account["ads_api_access_tier"] = tier
        if ad_account:
            result["ad_account"] = ad_account

    raw_business = _json_header(headers, "X-Business-Use-Case-Usage")
    business: List[Mapping[str, object]] = []
    if isinstance(raw_business, dict):
        for entries in raw_business.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                safe: Dict[str, object] = dict(_usage_values(entry))
                usage_type = entry.get("type")
                regain = _number(entry.get("estimated_time_to_regain_access"))
                tier = entry.get("ads_api_access_tier")
                if isinstance(usage_type, str):
                    safe["type"] = usage_type
                if regain is not None:
                    safe["estimated_time_to_regain_access_minutes"] = regain
                if isinstance(tier, str):
                    safe["ads_api_access_tier"] = tier
                if safe:
                    business.append(safe)
    if business:
        result["business_use_case"] = business
    return result


def _max_utilization(values: Mapping[str, object]) -> Optional[float]:
    candidates: List[float] = []
    app = values.get("app")
    if isinstance(app, dict):
        candidates.extend(
            value
            for field_name in USAGE_FIELDS
            if (value := _number(app.get(field_name))) is not None
        )
    account = values.get("ad_account")
    if isinstance(account, dict):
        value = _number(account.get("acc_id_util_pct"))
        if value is not None:
            candidates.append(value)
    business = values.get("business_use_case")
    if isinstance(business, list):
        for entry in business:
            if isinstance(entry, dict):
                candidates.extend(
                    value
                    for field_name in USAGE_FIELDS
                    if (value := _number(entry.get(field_name))) is not None
                )
    return max(candidates) if candidates else None


def _estimated_regain_seconds(values: Mapping[str, object]) -> Optional[int]:
    candidates: List[float] = []
    account = values.get("ad_account")
    if isinstance(account, dict):
        value = _number(account.get("reset_time_duration_seconds"))
        if value is not None:
            candidates.append(value)
    business = values.get("business_use_case")
    if isinstance(business, list):
        for entry in business:
            if isinstance(entry, dict):
                value = _number(entry.get("estimated_time_to_regain_access_minutes"))
                if value is not None:
                    candidates.append(value * 60)
    return int(max(candidates)) if candidates else None


def quota_health(max_utilization: Optional[float], *, blocked: bool = False) -> str:
    """Apply project policy thresholds to official utilization percentages."""

    if blocked:
        return "BLOCKED"
    if max_utilization is None:
        return "UNKNOWN"
    if max_utilization >= 95:
        return "CRITICAL"
    if max_utilization >= 85:
        return "HIGH"
    if max_utilization >= 70:
        return "ELEVATED"
    return "HEALTHY"


@dataclass
class UsageTracker:
    """Retain the latest sanitized observations for one client lifetime."""

    observations: Dict[str, object] = field(default_factory=dict)
    blocked: bool = False

    def observe(self, headers: Mapping[str, str]) -> None:
        parsed = parse_usage_headers(headers)
        for key, value in parsed.items():
            self.observations[key] = value

    def mark_blocked(self) -> None:
        self.blocked = True

    def summary(self) -> Mapping[str, object]:
        utilization = _max_utilization(self.observations)
        return {
            "status": quota_health(utilization, blocked=self.blocked),
            "max_utilization_pct": utilization,
            "estimated_regain_seconds": _estimated_regain_seconds(self.observations),
            "observations": dict(self.observations),
        }
