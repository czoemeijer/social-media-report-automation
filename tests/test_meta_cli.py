from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from social_report.cli import build_parser
from social_report.sources.meta.auth import MetaConfig, MetaConfigurationError
from social_report.sources.meta.client import HTTPResponse
from social_report.sources.meta.tokens import exchange_user_token


class TokenTransport:
    def __init__(self):
        self.url = ""

    def __call__(self, url, timeout, user_agent):
        self.url = url
        return HTTPResponse(200, {}, b'{"access_token":"long-lived-secret","expires_in":3600}')


class MetaCliTest(unittest.TestCase):
    def test_parser_supports_expected_command_surface(self):
        parser = build_parser()
        for command in ("doctor", "discover", "pull", "pull-instagram", "pull-ads"):
            args = parser.parse_args(["meta", command])
            self.assertEqual(args.command, command)

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


if __name__ == "__main__":
    unittest.main()
