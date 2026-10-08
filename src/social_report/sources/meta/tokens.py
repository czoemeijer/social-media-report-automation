"""Optional official token debugging and User Token exchange helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from .auth import MetaConfig, MetaConfigurationError
from .client import MetaClient, Transport

REQUIRED_REPORTING_SCOPES = (
    "ads_read",
    "instagram_basic",
    "instagram_manage_insights",
    "pages_read_engagement",
    "pages_show_list",
)


def debug_token(config: MetaConfig, *, transport: Optional[Transport] = None) -> Mapping[str, Any]:
    if not config.app_id or not config.app_secret:
        raise MetaConfigurationError("META_APP_ID and META_APP_SECRET are required for token debug")
    client = MetaClient(config, transport=transport)
    payload = client.get_without_auth(
        "debug_token",
        {
            "input_token": config.access_token,
            "access_token": f"{config.app_id}|{config.app_secret}",
        },
    )
    data = payload.get("data")
    if not isinstance(data, dict):
        return {}
    allowed = {
        "app_id",
        "type",
        "application",
        "data_access_expires_at",
        "expires_at",
        "is_valid",
        "scopes",
        "granular_scopes",
        "user_id",
    }
    return {key: value for key, value in data.items() if key in allowed}


def token_lifecycle_status(
    debug: Mapping[str, Any],
    *,
    now: Optional[datetime] = None,
    required_scopes: Sequence[str] = REQUIRED_REPORTING_SCOPES,
) -> Mapping[str, object]:
    """Classify official token-debug metadata without exposing credentials."""

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    raw_scopes = debug.get("scopes")
    scopes = {str(scope) for scope in raw_scopes} if isinstance(raw_scopes, list) else set()
    missing_scopes = sorted(set(required_scopes) - scopes)
    if debug.get("is_valid") is False:
        return {
            "status": "FAIL",
            "renewal": "INVALID",
            "deadline_type": None,
            "deadline": None,
            "days_remaining": None,
            "missing_scopes": missing_scopes,
        }

    deadlines = []
    for key in ("expires_at", "data_access_expires_at"):
        value = debug.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
            deadlines.append((key, datetime.fromtimestamp(value, timezone.utc)))
    deadline_type: Optional[str] = None
    deadline: Optional[datetime] = None
    if deadlines:
        deadline_type, deadline = min(deadlines, key=lambda item: item[1])

    status = "PASS"
    renewal = "OK"
    days_remaining: Optional[int] = None
    if debug.get("is_valid") is not True:
        status = "WARNING"
        renewal = "VALIDITY_UNCONFIRMED"
    if deadline is not None:
        remaining_seconds = (deadline - current).total_seconds()
        days_remaining = max(0, int(remaining_seconds // 86400))
        if remaining_seconds <= 0:
            status = "FAIL"
            renewal = "EXPIRED"
        elif remaining_seconds <= 3 * 86400:
            status = "CRITICAL"
            renewal = "RENEW_NOW"
        elif remaining_seconds <= 7 * 86400:
            status = "WARNING"
            renewal = "RENEW_SOON"
        elif remaining_seconds <= 14 * 86400:
            status = "WARNING"
            renewal = "RENEW"
    if missing_scopes and status == "PASS":
        status = "WARNING"
    return {
        "status": status,
        "renewal": renewal,
        "deadline_type": deadline_type,
        "deadline": deadline.isoformat() if deadline else None,
        "days_remaining": days_remaining,
        "missing_scopes": missing_scopes,
    }


def exchange_user_token(
    config: MetaConfig,
    *,
    save_to: Path,
    transport: Optional[Transport] = None,
) -> Mapping[str, object]:
    """Exchange and save a long-lived User Token without printing it."""

    if config.auth_mode != "user_token":
        raise MetaConfigurationError("Token exchange applies only to user_token mode")
    if not config.app_id or not config.app_secret:
        raise MetaConfigurationError("META_APP_ID and META_APP_SECRET are required for exchange")
    if save_to.exists():
        raise MetaConfigurationError("Refusing to overwrite an existing token target")
    client = MetaClient(config, transport=transport)
    payload = client.get_without_auth(
        "oauth/access_token",
        {
            "client_id": config.app_id,
            "client_secret": config.app_secret,
            "grant_type": "fb_exchange_token",
            "fb_exchange_token": config.access_token,
        },
    )
    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise MetaConfigurationError("Meta did not return a long-lived token")
    save_to.parent.mkdir(parents=True, exist_ok=True)
    save_to.write_text(token + "\n", encoding="utf-8")
    save_to.chmod(0o600)
    expires_in = payload.get("expires_in")
    return {
        "status": "saved",
        "path": str(save_to),
        "expires_in": expires_in if isinstance(expires_in, int) else None,
    }
