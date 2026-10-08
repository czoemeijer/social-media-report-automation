from __future__ import annotations

import hashlib
import hmac
import json
import unittest
import urllib.parse
from pathlib import Path
from tempfile import TemporaryDirectory

from social_report.sources.meta.auth import (
    MetaConfig,
    MetaConfigurationError,
    load_env_file,
)
from social_report.sources.meta.client import HTTPResponse, MetaAPIError, MetaClient, redact_url


class QueueTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.urls = []

    def __call__(self, url, timeout, user_agent):
        self.urls.append(url)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def response(payload, status=200, headers=None):
    return HTTPResponse(status, headers or {}, json.dumps(payload).encode())


class MetaAuthTest(unittest.TestCase):
    def test_env_loading_and_process_precedence(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / ".env.local"
            path.write_text("META_ACCESS_TOKEN=file-token\nMETA_GRAPH_VERSION=v25.0\n")
            env = {"META_ACCESS_TOKEN": "process-token"}
            load_env_file(path, env)
            config = MetaConfig.from_env(env)
        self.assertEqual(config.access_token, "process-token")
        self.assertEqual(config.graph_version, "v25.0")

    def test_missing_token_and_invalid_mode_fail(self):
        with self.assertRaises(MetaConfigurationError):
            MetaConfig.from_env({})
        with self.assertRaises(MetaConfigurationError):
            MetaConfig.from_env({"META_ACCESS_TOKEN": "x", "META_AUTH_MODE": "magic"})

    def test_appsecret_proof_matches_official_hmac_contract(self):
        config = MetaConfig(access_token="sensitive-value-123", app_secret="secret")
        expected = hmac.new(b"secret", b"sensitive-value-123", hashlib.sha256).hexdigest()
        self.assertEqual(config.appsecret_proof, expected)
        self.assertNotIn("sensitive-value-123", json.dumps(config.safe_summary()))

    def test_url_redaction_covers_all_auth_parameters(self):
        raw = "https://graph.test/me?access_token=abc&input_token=def&client_secret=ghi&after=safe"
        safe = redact_url(raw)
        self.assertNotIn("abc", safe)
        self.assertNotIn("def", safe)
        self.assertNotIn("ghi", safe)
        self.assertIn("after=safe", safe)


class MetaClientTest(unittest.TestCase):
    def test_credentials_are_sent_but_paging_urls_are_not_returned(self):
        transport = QueueTransport(
            [
                response(
                    {
                        "data": [{"id": "1"}],
                        "paging": {
                            "next": "https://graph.test/next?access_token=leak",
                            "cursors": {"after": "cursor-1"},
                        },
                    }
                ),
                response({"data": [{"id": "2"}]}),
            ]
        )
        client = MetaClient(MetaConfig(access_token="secret"), transport=transport)
        self.assertEqual([row["id"] for row in client.paginate("items")], ["1", "2"])
        self.assertIn("after=cursor-1", transport.urls[1])
        self.assertNotIn("leak", transport.urls[1])

    def test_retry_after_and_5xx_are_bounded(self):
        sleeps = []
        transport = QueueTransport(
            [
                response({"error": {"message": "slow", "code": 4}}, 429, {"Retry-After": "2"}),
                response({"id": "ok"}),
            ]
        )
        client = MetaClient(
            MetaConfig(access_token="secret", max_retries=1),
            transport=transport,
            sleep=sleeps.append,
        )
        self.assertEqual(client.get("me")["id"], "ok")
        self.assertEqual(sleeps, [2.0])

    def test_auth_error_is_not_retried_or_leaked(self):
        token = "sensitive-token-value"
        transport = QueueTransport(
            [response({"error": {"message": f"bad token {token}", "code": 190}}, 400)]
        )
        client = MetaClient(MetaConfig(access_token=token, max_retries=3), transport=transport)
        with self.assertRaises(MetaAPIError) as caught:
            client.get("me")
        self.assertEqual(len(transport.urls), 1)
        self.assertNotIn(token, str(caught.exception.as_dict()))
        self.assertEqual(caught.exception.code, 190)

    def test_query_encoding_and_user_agent(self):
        transport = QueueTransport([response({"data": []})])
        client = MetaClient(MetaConfig(access_token="token"), transport=transport)
        client.get("act_1/insights", {"time_range": {"since": "2026-01-01"}})
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(transport.urls[0]).query)
        self.assertEqual(json.loads(query["time_range"][0]), {"since": "2026-01-01"})


if __name__ == "__main__":
    unittest.main()
