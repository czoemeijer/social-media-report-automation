"""Optional official token debugging and User Token exchange helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Optional

from .auth import MetaConfig, MetaConfigurationError
from .client import MetaClient, Transport


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
