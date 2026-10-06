from __future__ import annotations

import json
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from scripts.dify_deploy import (
    EXPECTED_TOOLS,
    DifyClient,
    _mask_token,
    cmd_discover,
    cmd_import_workflow,
    cmd_plugin_status,
    cmd_smoke_test,
    sanitize_dsl_content,
)


class TestDifyDeployHelper(unittest.TestCase):
    def test_mask_token(self) -> None:
        self.assertEqual(_mask_token(""), "<none>")
        self.assertEqual(_mask_token("short"), "***")
        self.assertEqual(_mask_token("app-1234567890abcdef"), "app-...cdef")

    def test_client_headers(self) -> None:
        client = DifyClient(
            base_url="http://test-dify:5001/",
            access_token="test-token-12345",
            workspace_id="ws-999",
        )
        self.assertEqual(client.base_url, "http://test-dify:5001")
        self.assertEqual(client.workspace_id, "ws-999")

    @patch("urllib.request.urlopen")
    def test_client_request_json(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"status": "ok"}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = DifyClient(base_url="http://test-dify:5001", access_token="token")
        status, data = client.get("/api/version")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"status": "ok"})

    @patch("urllib.request.urlopen")
    def test_cmd_discover(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(
            {
                "version": "1.14.2",
                "current_workspace": {"id": "ws-1", "name": "Default", "role": "admin"},
            }
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = DifyClient(base_url="http://test-dify:5001", access_token="token")
        code = cmd_discover(client)
        self.assertEqual(code, 0)

    @patch("urllib.request.urlopen")
    def test_cmd_plugin_status_found(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(
            {
                "data": [
                    {
                        "name": "czoemeijer/dify-social-report",
                        "tools": [{"name": t} for t in EXPECTED_TOOLS],
                    }
                ]
            }
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = DifyClient(base_url="http://test-dify:5001", access_token="token")
        code = cmd_plugin_status(client)
        self.assertEqual(code, 0)

    @patch("urllib.request.urlopen")
    def test_cmd_plugin_status_missing(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"data": []}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = DifyClient(base_url="http://test-dify:5001", access_token="token")
        code = cmd_plugin_status(client)
        self.assertEqual(code, 1)

    @patch("urllib.request.urlopen")
    def test_cmd_import_workflow_openapi(self, mock_urlopen: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(
            {
                "id": "app-12345",
                "app": {"id": "app-12345", "name": "Social Report"},
            }
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = DifyClient(
            base_url="http://test-dify:5001", access_token="token", workspace_id="ws-1"
        )
        dsl_file = (
            Path(__file__).resolve().parents[1] / "deploy" / "dify" / "social-media-report.yml"
        )
        code = cmd_import_workflow(client, dsl_file, app_id="app-12345")
        self.assertEqual(code, 0)

    @patch("urllib.request.urlopen")
    def test_cmd_smoke_test_success(self, mock_urlopen: MagicMock) -> None:
        def side_effect(req: urllib.request.Request, timeout: int = 30) -> MagicMock:
            resp = MagicMock()
            resp.status = 200
            resp.__enter__.return_value = resp
            if "upload" in req.full_url:
                resp.read.return_value = json.dumps({"id": "file-123"}).encode("utf-8")
            else:
                resp.read.return_value = json.dumps(
                    {
                        "data": {
                            "status": "succeeded",
                            "outputs": {
                                "report_markdown": "# Test Report",
                                "report_json": "{}",
                                "report_csv": "header\nval",
                            },
                        }
                    }
                ).encode("utf-8")
            return resp

        mock_urlopen.side_effect = side_effect
        client = DifyClient(base_url="http://test-dify:5001", access_token="token")
        code = cmd_smoke_test(client, "app-12345", use_synthetic=True)
        self.assertEqual(code, 0)

    def test_sanitize_dsl_content(self) -> None:
        dsl_with_creds = """
        provider: 'openai'
        name: 'gpt-4o'
        """
        sanitized = sanitize_dsl_content(dsl_with_creds)
        self.assertIn("provider: ''", sanitized)
        self.assertIn("name: ''", sanitized)
        self.assertNotIn("'openai'", sanitized)


if __name__ == "__main__":
    unittest.main()
