"""Environment-driven Meta credentials without secret persistence."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, MutableMapping, Optional

_VERSION = re.compile(r"^v\d+\.\d+$")
AUTH_MODES = ("user_token", "system_user_token")


class MetaConfigurationError(ValueError):
    """Raised when local Meta configuration is incomplete or unsafe."""


def load_env_file(
    path: Path, environ: Optional[MutableMapping[str, str]] = None
) -> MutableMapping[str, str]:
    """Load simple KEY=VALUE entries without overriding process variables."""

    target = environ if environ is not None else os.environ
    if not path.exists():
        return target
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] == value[-1:] and value.startswith(("'", '"')):
            value = value[1:-1]
        if key and key not in target:
            target[key] = value
    return target


@dataclass(frozen=True)
class MetaConfig:
    """Meta API settings shared by user-token and system-user-token modes."""

    access_token: str
    graph_version: str = "v26.0"
    auth_mode: str = "user_token"
    app_id: Optional[str] = None
    app_secret: Optional[str] = None
    business_id: Optional[str] = None
    page_id: Optional[str] = None
    ig_user_id: Optional[str] = None
    ad_account_id: Optional[str] = None
    timeout_seconds: float = 20.0
    max_retries: int = 3

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> MetaConfig:
        values = environ if environ is not None else os.environ
        token = values.get("META_ACCESS_TOKEN", "").strip()
        if not token:
            raise MetaConfigurationError("META_ACCESS_TOKEN is required")
        version = values.get("META_GRAPH_VERSION", "v26.0").strip()
        if not _VERSION.fullmatch(version):
            raise MetaConfigurationError("META_GRAPH_VERSION must look like v26.0")
        mode = values.get("META_AUTH_MODE", "user_token").strip()
        if mode not in AUTH_MODES:
            raise MetaConfigurationError(f"META_AUTH_MODE must be one of: {', '.join(AUTH_MODES)}")
        try:
            timeout = float(values.get("META_TIMEOUT_SECONDS", "20"))
            retries = int(values.get("META_MAX_RETRIES", "3"))
        except ValueError as exc:
            raise MetaConfigurationError("Meta timeout/retry settings must be numeric") from exc
        if timeout <= 0 or retries < 0 or retries > 10:
            raise MetaConfigurationError("Meta timeout/retry settings are outside safe bounds")

        def optional(name: str) -> Optional[str]:
            return values.get(name, "").strip() or None

        return cls(
            access_token=token,
            graph_version=version,
            auth_mode=mode,
            app_id=optional("META_APP_ID"),
            app_secret=optional("META_APP_SECRET"),
            business_id=optional("META_BUSINESS_ID"),
            page_id=optional("META_PAGE_ID"),
            ig_user_id=optional("META_IG_USER_ID"),
            ad_account_id=optional("META_AD_ACCOUNT_ID"),
            timeout_seconds=timeout,
            max_retries=retries,
        )

    @property
    def appsecret_proof(self) -> Optional[str]:
        if not self.app_secret:
            return None
        return hmac.new(
            self.app_secret.encode("utf-8"),
            self.access_token.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def safe_summary(self) -> Mapping[str, object]:
        """Return configuration metadata suitable for diagnostics."""

        return {
            "graph_version": self.graph_version,
            "auth_mode": self.auth_mode,
            "app_id_configured": self.app_id is not None,
            "appsecret_proof_enabled": self.app_secret is not None,
            "business_id_configured": self.business_id is not None,
            "page_id_configured": self.page_id is not None,
            "ig_user_id_configured": self.ig_user_id is not None,
            "ad_account_id_configured": self.ad_account_id is not None,
        }
