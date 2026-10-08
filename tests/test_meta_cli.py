from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from social_report.cli import build_parser, doctor
from social_report.sources.meta.auth import MetaConfig, MetaConfigurationError
from social_report.sources.meta.client import HTTPResponse, MetaClient
from social_report.sources.meta.tokens import REQUIRED_REPORTING_SCOPES, exchange_user_token


class TokenTransport:
    def __init__(self):
        self.url = ""

    def __call__(self, url, timeout, user_agent):
        self.url = url
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


class MetaCliTest(unittest.TestCase):
    def test_parser_supports_expected_command_surface(self):
        parser = build_parser()
        for command in ("doctor", "discover", "pull", "pull-instagram", "pull-ads"):
            args = parser.parse_args(["meta", command])
            self.assertEqual(args.command, command)
        report = parser.parse_args(["meta", "report", "--output-dir", "private/report"])
        self.assertEqual(report.command, "report")
        self.assertEqual(report.language, "en")

    def test_exchange_requires_explicit_new_target_and_never_returns_token(self):
        config = MetaConfig(
            access_token="short-lived-secret",
            app_id="app",
            app_secret="app-secret",
        )
        transport = TokenTransport()
        with TemporaryDirectory() as temp:
            target = Path(temp) / "token.secret"
            result = exchange_user_token(config, save_to=target, transport=transport)
            self.assertEqual(target.read_text().strip(), "long-lived-secret")
            self.assertNotIn("long-lived-secret", str(result))
            with self.assertRaises(MetaConfigurationError):
                exchange_user_token(config, save_to=target, transport=transport)

    def test_doctor_reports_sanitized_quota_from_normal_responses(self):
        class DoctorTransport:
            def __call__(self, url, timeout, user_agent):
                return HTTPResponse(
                    200,
                    {"X-App-Usage": '{"call_count":86,"total_cputime":5,"total_time":4}'},
                    b'{"id":"operator"}',
                )

        selected = {
            "page_id": None,
            "ig_user_id": None,
            "ad_account_id": None,
            "validation": {},
        }
        client = MetaClient(
            MetaConfig(access_token="private-token-value"), transport=DoctorTransport()
        )
        with (
            patch("social_report.cli.discover_assets", return_value={}),
            patch("social_report.cli.resolve_assets", return_value=selected),
        ):
            result = doctor(client, client.config)
        self.assertEqual(result["quota"]["status"], "HIGH")
        quota_check = next(row for row in result["checks"] if row["name"] == "quota")
        self.assertEqual(quota_check["status"], "WARNING")
        self.assertNotIn("private-token-value", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
