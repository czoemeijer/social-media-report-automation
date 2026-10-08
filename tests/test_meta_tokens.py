from __future__ import annotations

import json
import stat
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from social_report.sources.meta.auth import MetaConfig, MetaConfigurationError
from social_report.sources.meta.client import HTTPResponse, MetaAPIError, MetaClient
from social_report.sources.meta.tokens import (
    REQUIRED_REPORTING_SCOPES,
    debug_token,
    exchange_user_token,
    token_lifecycle_status,
)

NOW = datetime(2026, 10, 8, tzinfo=timezone.utc)


def _debug(*, days: float | None = 30, valid: bool = True) -> dict[str, object]:
    result: dict[str, object] = {
        "is_valid": valid,
        "scopes": list(REQUIRED_REPORTING_SCOPES),
    }
    if days is not None:
        result["expires_at"] = int((NOW + timedelta(days=days)).timestamp())
    return result


class ExchangeTransport:
    def __call__(self, url, timeout, user_agent):
        if "debug_token" in url:
            payload = {
                "data": {
                    "app_id": "app",
                    "is_valid": True,
                    "scopes": list(REQUIRED_REPORTING_SCOPES),
                }
            }
            return HTTPResponse(200, {}, json.dumps(payload).encode())
        return HTTPResponse(200, {}, b'{"access_token":"long-lived-secret","expires_in":3600}')


class TokenLifecycleTest(unittest.TestCase):
    def test_expiry_thresholds(self):
        self.assertEqual(token_lifecycle_status(_debug(days=15), now=NOW)["status"], "PASS")
        fourteen = token_lifecycle_status(_debug(days=14), now=NOW)
        self.assertEqual((fourteen["status"], fourteen["renewal"]), ("WARNING", "RENEW"))
        seven = token_lifecycle_status(_debug(days=7), now=NOW)
        self.assertEqual((seven["status"], seven["renewal"]), ("WARNING", "RENEW_SOON"))
        three = token_lifecycle_status(_debug(days=3), now=NOW)
        self.assertEqual((three["status"], three["renewal"]), ("CRITICAL", "RENEW_NOW"))

    def test_expired_and_invalid_tokens_fail(self):
        self.assertEqual(token_lifecycle_status(_debug(days=-1), now=NOW)["renewal"], "EXPIRED")
        invalid = token_lifecycle_status(_debug(days=30, valid=False), now=NOW)
        self.assertEqual((invalid["status"], invalid["renewal"]), ("FAIL", "INVALID"))

    def test_zero_or_missing_expiry_means_no_finite_deadline(self):
        zero = _debug(days=None)
        zero["expires_at"] = 0
        self.assertEqual(token_lifecycle_status(zero, now=NOW)["status"], "PASS")
        self.assertIsNone(token_lifecycle_status(zero, now=NOW)["deadline"])
        self.assertEqual(token_lifecycle_status(_debug(days=None), now=NOW)["status"], "PASS")

    def test_earlier_data_access_expiry_wins(self):
        debug = _debug(days=30)
        debug["data_access_expires_at"] = int((NOW + timedelta(days=6)).timestamp())
        result = token_lifecycle_status(debug, now=NOW)
        self.assertEqual(result["deadline_type"], "data_access_expires_at")
        self.assertEqual(result["renewal"], "RENEW_SOON")

    def test_missing_required_scope_warns(self):
        debug = _debug(days=30)
        debug["scopes"] = [scope for scope in REQUIRED_REPORTING_SCOPES if scope != "ads_read"]
        result = token_lifecycle_status(debug, now=NOW)
        self.assertEqual(result["status"], "WARNING")
        self.assertEqual(result["missing_scopes"], ["ads_read"])

    def test_debug_without_app_credentials_is_unavailable(self):
        with self.assertRaisesRegex(MetaConfigurationError, "required for token debug"):
            debug_token(MetaConfig(access_token="token"))

    def test_exchange_permissions_refusal_and_secret_redaction(self):
        config = MetaConfig(access_token="short-secret", app_id="app", app_secret="app-secret")
        with TemporaryDirectory() as temp:
            target = Path(temp) / "token.secret"
            result = exchange_user_token(config, save_to=target, transport=ExchangeTransport())
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            self.assertNotIn("long-lived-secret", str(result))
            with self.assertRaisesRegex(MetaConfigurationError, "Refusing to overwrite"):
                exchange_user_token(config, save_to=target, transport=ExchangeTransport())

        def failing_transport(url, timeout, user_agent):
            body = b'{"error":{"message":"short-secret app-secret","code":190}}'
            return HTTPResponse(400, {}, body)

        with self.assertRaises(MetaAPIError) as raised:
            MetaClient(config, transport=failing_transport).get("me")
        self.assertNotIn("short-secret", str(raised.exception))
        self.assertNotIn("app-secret", str(raised.exception))
        self.assertNotIn("short-secret", str(raised.exception.request_url))

    def test_invalid_exchanged_candidate_is_never_written(self):
        class InvalidCandidateTransport:
            def __call__(self, url, timeout, user_agent):
                if "debug_token" in url:
                    return HTTPResponse(200, {}, b'{"data":{"app_id":"app","is_valid":false}}')
                return HTTPResponse(200, {}, b'{"access_token":"candidate-secret"}')

        config = MetaConfig(access_token="short-secret", app_id="app", app_secret="app-secret")
        with TemporaryDirectory() as temp:
            target = Path(temp) / "token.secret"
            with self.assertRaisesRegex(MetaConfigurationError, "invalid exchanged token"):
                exchange_user_token(config, save_to=target, transport=InvalidCandidateTransport())
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
