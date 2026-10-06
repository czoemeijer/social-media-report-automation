from __future__ import annotations

import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import yaml

from scripts.dify_deploy import (
    DEFAULT_DSL,
    DeploymentError,
    DifyClient,
    DifySettings,
    assert_workflow_outputs,
    bind_models,
    discover_server,
    discover_vision_models,
    expected_plugin_identifier,
    expected_tool_names,
    export_workflow,
    find_existing_app,
    import_workflow,
    install_plugin,
    parse_env_file,
    parse_sse_workflow_result,
    poll_plugin_task,
    resolve_settings,
    sanitize_model_bindings,
    smoke_test,
    verify_model_binding,
    verify_plugin,
)


class FakeClient:
    def __init__(self, settings: Optional[DifySettings] = None) -> None:
        self.settings = settings or DifySettings(
            base_url="https://dify.example.com",
            workspace_id="ws-1",
            openapi_token="openapi-secret",
            console_access_token="console-secret",
            csrf_token="csrf-secret",
        )
        self.base_url = self.settings.base_url
        self.responses: Dict[Tuple[str, str], List[Tuple[int, Any]]] = {}
        self.calls: List[Dict[str, Any]] = []

    @property
    def secrets(self) -> Tuple[str, ...]:
        return (
            self.settings.openapi_token,
            self.settings.console_access_token,
            self.settings.csrf_token,
        )

    def queue(self, method: str, path: str, *responses: Tuple[int, Any]) -> None:
        self.responses.setdefault((method, path), []).extend(responses)

    def _response(self, method: str, path: str) -> Tuple[int, Any]:
        try:
            return self.responses[(method, path)].pop(0)
        except (KeyError, IndexError) as exc:
            raise AssertionError(f"No fake response for {method} {path}") from exc

    def get(self, path: str, *, auth: str) -> Tuple[int, Any]:
        self.calls.append({"method": "GET", "path": path, "auth": auth})
        return self._response("GET", path)

    def post(self, path: str, payload: Any, *, auth: str) -> Tuple[int, Any]:
        self.calls.append({"method": "POST", "path": path, "auth": auth, "payload": payload})
        return self._response("POST", path)

    def upload_file(
        self, path: str, file_path: Path, *, form_field: str, auth: str
    ) -> Tuple[int, Any]:
        self.calls.append(
            {
                "method": "UPLOAD",
                "path": path,
                "auth": auth,
                "form_field": form_field,
                "file": file_path,
            }
        )
        return self._response("UPLOAD", path)


def _plugin_list_item(identifier: str) -> Dict[str, Any]:
    version_checksum = identifier.split(":", 1)[1]
    version, checksum = version_checksum.split("@", 1)
    return {
        "plugin_id": "czoemeijer/dify-social-report",
        "plugin_unique_identifier": identifier,
        "name": "dify-social-report",
        "version": version,
        "checksum": checksum,
    }


def _provider(identifier: str, tools: Optional[List[str]]) -> Dict[str, Any]:
    return {
        "id": "czoemeijer/dify-social-report/social_report",
        "plugin_unique_identifier": identifier,
        "tools": [] if tools is None else [{"name": name} for name in tools],
    }


def _successful_outputs() -> Dict[str, Any]:
    return {
        "status": "succeeded",
        "outputs": {
            "report_markdown": "# Synthetic report",
            "audit_json": {
                "items": [],
                "campaign_summary": {
                    "scope_buckets": {
                        "organic": {},
                        "paid": {},
                        "mixed_or_unknown": {},
                        "unknown": {},
                    }
                },
                "review_status": "needs_review",
                "warnings": ["synthetic warning"],
            },
            "json_files": [{"name": "report.json"}],
            "csv_files": [{"name": "report.csv"}],
        },
    }


class TestEnvironmentLoading(unittest.TestCase):
    def test_comments_and_quoted_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dify.env"
            path.write_text(
                "# comment\n"
                "DIFY_BASE_URL='https://dify.example.com'\n"
                'DIFY_OPENAPI_TOKEN="placeholder\\nmultiline" # trailing comment\n'
                "DIFY_CSRF_TOKEN=placeholder#literal\n",
                encoding="utf-8",
            )
            values = parse_env_file(path)
        self.assertEqual(values["DIFY_BASE_URL"], "https://dify.example.com")
        self.assertEqual(values["DIFY_OPENAPI_TOKEN"], "placeholder\nmultiline")
        self.assertEqual(values["DIFY_CSRF_TOKEN"], "placeholder#literal")

    def test_missing_explicit_file_fails(self) -> None:
        with self.assertRaises(DeploymentError):
            parse_env_file(Path("/definitely/missing/dify.env"))

    def test_process_and_cli_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dify.env"
            path.write_text(
                "DIFY_BASE_URL=https://file.example\nDIFY_WORKSPACE_ID=file-ws\n",
                encoding="utf-8",
            )
            with (
                patch("scripts.dify_deploy.DEFAULT_ENV_FILE", Path(tmp) / "missing-repo"),
                patch("scripts.dify_deploy.USER_ENV_FILE", Path(tmp) / "missing-user"),
            ):
                settings = resolve_settings(
                    environ={"DIFY_BASE_URL": "https://process.example"},
                    env_file=path,
                    cli_values={"DIFY_WORKSPACE_ID": "cli-ws"},
                )
        self.assertEqual(settings.base_url, "https://process.example")
        self.assertEqual(settings.workspace_id, "cli-ws")


class TestAuthentication(unittest.TestCase):
    def test_openapi_and_console_headers_are_separate(self) -> None:
        settings = DifySettings(
            base_url="https://dify.example.com",
            openapi_token="openapi-token",
            console_access_token="console-token",
            csrf_token="csrf-token",
        )
        client = DifyClient(settings)
        openapi = client._auth_headers("openapi")
        console = client._auth_headers("console")
        self.assertEqual(openapi, {"Authorization": "Bearer openapi-token"})
        self.assertEqual(console["Authorization"], "Bearer console-token")
        self.assertEqual(console["X-CSRF-Token"], "csrf-token")
        self.assertIn("csrf_token=csrf-token", console["Cookie"])
        self.assertNotIn("openapi-token", json.dumps(console))

    def test_ambiguous_app_api_key_is_not_read(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("scripts.dify_deploy.DEFAULT_ENV_FILE", Path(tmp) / "missing-repo"),
            patch("scripts.dify_deploy.USER_ENV_FILE", Path(tmp) / "missing-user"),
        ):
            settings = resolve_settings(
                environ={
                    "DIFY_BASE_URL": "https://dify.example.com",
                    "DIFY_API_KEY": "app-service-key",
                }
            )
        self.assertEqual(settings.openapi_token, "")
        self.assertEqual(settings.console_access_token, "")

    @patch("urllib.request.urlopen")
    def test_request_never_prints_or_reuses_wrong_token(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"ok":true}'
        response.__enter__.return_value = response
        urlopen.return_value = response
        client = DifyClient(
            DifySettings(
                base_url="https://dify.example.com",
                openapi_token="openapi-token",
                console_access_token="console-token",
                csrf_token="csrf-token",
            )
        )
        client.get("/openapi/v1/workspaces", auth="openapi")
        request: urllib.request.Request = urlopen.call_args.args[0]
        self.assertEqual(request.headers["Authorization"], "Bearer openapi-token")
        self.assertNotIn("console-token", str(request.headers))


class TestDiscovery(unittest.TestCase):
    def test_modern_discovery_reports_capabilities_without_secrets(self) -> None:
        client = FakeClient()
        client.queue(
            "GET", "/openapi/v1/_version", (200, {"version": "1.17.1", "edition": "SELF_HOSTED"})
        )
        client.queue("GET", "/openapi/v1/_health", (200, {"ok": True}))
        client.queue("GET", "/openapi/v1/workspaces", (200, {"data": []}))
        client.queue("GET", "/console/api/account/profile", (200, {"id": "account"}))
        client.queue(
            "GET",
            "/console/api/workspaces/current/models/model-types/llm",
            (
                200,
                {
                    "data": [
                        {
                            "provider": "provider-id",
                            "status": "active",
                            "models": [
                                {
                                    "model": "vision-model",
                                    "features": ["vision"],
                                    "status": "active",
                                }
                            ],
                        }
                    ]
                },
            ),
        )
        report = discover_server(client)  # type: ignore[arg-type]
        rendered = json.dumps(report)
        self.assertEqual(report["version"], "1.17.1")
        self.assertEqual(report["capabilities"]["openapi_account"], "VERIFIED")
        self.assertEqual(report["capabilities"]["console_admin"], "VERIFIED")
        self.assertEqual(report["vision_models"]["models"][0]["model"], "vision-model")
        self.assertNotIn("openapi-secret", rendered)
        self.assertNotIn("console-secret", rendered)
        self.assertNotIn("csrf-secret", rendered)

    def test_legacy_discovery_uses_released_console_version_route(self) -> None:
        settings = DifySettings(base_url="https://dify.example.com")
        client = FakeClient(settings)
        client.queue("GET", "/openapi/v1/_version", (404, {}))
        client.queue(
            "GET",
            "/console/api/version?current_version=0.0.0",
            (200, {"version": "1.14.2"}),
        )
        report = discover_server(client)  # type: ignore[arg-type]
        self.assertEqual(report["contract"], "console-1.14.2")
        self.assertEqual(report["capabilities"]["openapi_account"], "UNSUPPORTED_VERSION")

    def test_vision_discovery_filters_non_vision_models(self) -> None:
        client = FakeClient()
        client.queue(
            "GET",
            "/console/api/workspaces/current/models/model-types/llm",
            (
                200,
                {
                    "data": [
                        {
                            "provider": "provider-id",
                            "status": "active",
                            "models": [
                                {"model": "text-only", "features": []},
                                {"model": "vision", "features": ["vision"]},
                            ],
                        }
                    ]
                },
            ),
        )
        result = discover_vision_models(client)  # type: ignore[arg-type]
        self.assertEqual([item["model"] for item in result["models"]], ["vision"])


class TestPluginContracts(unittest.TestCase):
    def test_six_tool_names_are_derived_from_provider(self) -> None:
        self.assertEqual(
            expected_tool_names(),
            [
                "prepare_campaign_input",
                "unpack_campaign_archive",
                "select_asset_files",
                "validate_extraction",
                "audit_campaign",
                "export_campaign",
            ],
        )

    def test_empty_tool_response_is_partial_not_pass(self) -> None:
        identifier = expected_plugin_identifier()
        client = FakeClient()
        client.queue(
            "GET",
            "/console/api/workspaces/current/plugin/list?page=1&page_size=256",
            (200, {"plugins": [_plugin_list_item(identifier)]}),
        )
        client.queue(
            "GET",
            "/console/api/workspaces/current/tool-providers",
            (200, [_provider(identifier, None)]),
        )
        result = verify_plugin(client)  # type: ignore[arg-type]
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["tools_state"], "NOT_VERIFIED")

    def test_missing_tool_fails(self) -> None:
        identifier = expected_plugin_identifier()
        tools = expected_tool_names()[:-1]
        client = FakeClient()
        client.queue(
            "GET",
            "/console/api/workspaces/current/plugin/list?page=1&page_size=256",
            (200, {"plugins": [_plugin_list_item(identifier)]}),
        )
        client.queue(
            "GET",
            "/console/api/workspaces/current/tool-providers",
            (200, [_provider(identifier, tools)]),
        )
        result = verify_plugin(client)  # type: ignore[arg-type]
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["missing_tools"], ["export_campaign"])

    @patch("scripts.dify_deploy.require_supported_contract", return_value=("1.17.1", {}))
    @patch("scripts.dify_deploy.verify_plugin", return_value={"status": "PASS"})
    def test_upload_and_install_exact_contract(
        self, _verify: MagicMock, _contract: MagicMock
    ) -> None:
        identifier = expected_plugin_identifier()
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "plugin.difypkg"
            package.write_bytes(b"package")
            client.queue(
                "UPLOAD",
                "/console/api/workspaces/current/plugin/upload/pkg",
                (200, {"unique_identifier": identifier, "manifest": {}}),
            )
            client.queue(
                "POST",
                "/console/api/workspaces/current/plugin/install/pkg",
                (200, {"all_installed": True, "task_id": "task-1"}),
            )
            install_plugin(client, package)  # type: ignore[arg-type]
        upload_call, install_call = client.calls
        self.assertEqual(upload_call["form_field"], "pkg")
        self.assertEqual(install_call["payload"], {"plugin_unique_identifiers": [identifier]})

    @patch("scripts.dify_deploy.time.sleep")
    def test_task_polling_wrapper_pending_running_success(self, _sleep: MagicMock) -> None:
        path = "/console/api/workspaces/current/plugin/tasks/task-1"
        client = FakeClient()
        client.queue(
            "GET",
            path,
            (200, {"task": {"status": "pending"}}),
            (200, {"task": {"status": "running"}}),
            (200, {"task": {"status": "success"}}),
        )
        task = poll_plugin_task(client, "task-1")  # type: ignore[arg-type]
        self.assertEqual(task["status"], "success")

    def test_task_failure_message_is_redacted(self) -> None:
        path = "/console/api/workspaces/current/plugin/tasks/task-1"
        client = FakeClient()
        client.queue(
            "GET",
            path,
            (
                200,
                {
                    "task": {
                        "status": "failed",
                        "plugins": [{"message": "bad console-secret"}],
                    }
                },
            ),
        )
        with self.assertRaisesRegex(DeploymentError, "<redacted>") as caught:
            poll_plugin_task(client, "task-1")  # type: ignore[arg-type]
        self.assertNotIn("console-secret", str(caught.exception))


class TestImportContracts(unittest.TestCase):
    def test_model_binding_requires_an_active_configured_vision_model(self) -> None:
        client = FakeClient()
        client.queue(
            "GET",
            "/console/api/workspaces/current/models/model-types/llm",
            (
                200,
                {
                    "data": [
                        {
                            "provider": "provider-id",
                            "status": "active",
                            "models": [
                                {
                                    "model": "vision-model",
                                    "features": ["vision"],
                                    "status": "active",
                                }
                            ],
                        }
                    ]
                },
            ),
        )
        self.assertTrue(
            verify_model_binding(client, "provider-id", "vision-model")  # type: ignore[arg-type]
        )

    @patch("scripts.dify_deploy.require_supported_contract", return_value=("1.17.1", {}))
    def test_openapi_completed_and_dependency_check(self, _contract: MagicMock) -> None:
        client = FakeClient()
        import_path = "/openapi/v1/workspaces/ws-1/apps/imports"
        client.queue(
            "POST",
            import_path,
            (200, {"id": "import-1", "status": "completed", "app_id": "app-1"}),
        )
        client.queue(
            "GET",
            "/openapi/v1/apps/app-1/dependencies:check",
            (200, {"leaked_dependencies": []}),
        )
        result = import_workflow(client, DEFAULT_DSL, app_id="app-1")  # type: ignore[arg-type]
        self.assertEqual(result["import_status"], "completed")
        call = client.calls[0]
        self.assertEqual(call["path"], import_path)
        self.assertEqual(call["auth"], "openapi")
        self.assertEqual(call["payload"]["mode"], "yaml-content")
        self.assertEqual(call["payload"]["app_id"], "app-1")

    @patch("scripts.dify_deploy.require_supported_contract", return_value=("1.17.1", {}))
    def test_openapi_completed_with_warnings_is_accepted(self, _contract: MagicMock) -> None:
        client = FakeClient()
        client.queue(
            "POST",
            "/openapi/v1/workspaces/ws-1/apps/imports",
            (
                200,
                {
                    "id": "import-1",
                    "status": "completed-with-warnings",
                    "app_id": "app-1",
                    "warnings": [{"message": "warning"}],
                },
            ),
        )
        client.queue(
            "GET",
            "/openapi/v1/apps/app-1/dependencies:check",
            (200, {"leaked_dependencies": []}),
        )
        result = import_workflow(client, DEFAULT_DSL, app_id="app-1")  # type: ignore[arg-type]
        self.assertEqual(result["import_status"], "completed-with-warnings")

    @patch("scripts.dify_deploy.require_supported_contract", return_value=("1.17.1", {}))
    def test_openapi_pending_uses_colon_confirm(self, _contract: MagicMock) -> None:
        client = FakeClient()
        client.queue(
            "POST",
            "/openapi/v1/workspaces/ws-1/apps/imports",
            (202, {"id": "import-1", "status": "pending", "app_id": None}),
        )
        client.queue(
            "POST",
            "/openapi/v1/workspaces/ws-1/apps/imports/import-1:confirm",
            (200, {"id": "import-1", "status": "completed", "app_id": "app-1"}),
        )
        client.queue(
            "GET",
            "/openapi/v1/apps/app-1/dependencies:check",
            (200, {"leaked_dependencies": []}),
        )
        import_workflow(client, DEFAULT_DSL, app_id="app-1")  # type: ignore[arg-type]
        self.assertEqual(
            client.calls[1]["path"].split("?")[0],
            "/openapi/v1/workspaces/ws-1/apps/imports/import-1:confirm",
        )

    @patch("scripts.dify_deploy.require_supported_contract", return_value=("1.14.2", {}))
    def test_legacy_console_import_route_and_confirm(self, _contract: MagicMock) -> None:
        client = FakeClient()
        client.queue(
            "POST",
            "/console/api/apps/imports",
            (202, {"id": "import-1", "status": "pending", "app_id": None}),
        )
        client.queue(
            "POST",
            "/console/api/apps/imports/import-1/confirm",
            (200, {"id": "import-1", "status": "completed", "app_id": "app-1"}),
        )
        client.queue(
            "GET",
            "/console/api/apps/imports/app-1/check-dependencies",
            (200, {"leaked_dependencies": []}),
        )
        import_workflow(client, DEFAULT_DSL, app_id="app-1")  # type: ignore[arg-type]
        self.assertEqual(client.calls[0]["path"], "/console/api/apps/imports")
        self.assertEqual(client.calls[1]["path"], "/console/api/apps/imports/import-1/confirm")

    def test_idempotent_app_discovery(self) -> None:
        client = FakeClient()
        path = (
            "/openapi/v1/apps?workspace_id=ws-1&page=1&limit=100&name=Social+Media+Campaign+Report"
        )
        client.queue(
            "GET",
            path,
            (200, {"data": [{"id": "app-1", "name": "Social Media Campaign Report"}]}),
        )
        app_id = find_existing_app(
            client,
            "1.17.1",
            "Social Media Campaign Report",  # type: ignore[arg-type]
        )
        self.assertEqual(app_id, "app-1")


class TestYamlSafetyAndRuntime(unittest.TestCase):
    def test_model_binding_and_sanitization_are_structural(self) -> None:
        canonical = DEFAULT_DSL.read_text(encoding="utf-8")
        bound = bind_models(canonical, "provider-id", "vision-model")
        bound_data = yaml.safe_load(bound)
        self.assertEqual(bound_data["app"]["name"], "Social Media Campaign Report")
        sanitized = sanitize_model_bindings(bound)
        data = yaml.safe_load(sanitized)
        llm_nodes = [
            node for node in data["workflow"]["graph"]["nodes"] if node["data"]["type"] == "llm"
        ]
        self.assertTrue(llm_nodes)
        self.assertTrue(all(node["data"]["model"]["provider"] == "" for node in llm_nodes))
        self.assertTrue(all(node["data"]["model"]["name"] == "" for node in llm_nodes))

    @patch("scripts.dify_deploy.require_supported_contract", return_value=("1.17.1", {}))
    def test_safe_openapi_export_without_secrets(self, _contract: MagicMock) -> None:
        client = FakeClient()
        bound = bind_models(DEFAULT_DSL.read_text(encoding="utf-8"), "provider", "model")
        client.queue(
            "GET",
            "/openapi/v1/apps/app-1/dsl?include_secret=false",
            (200, {"data": bound}),
        )
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "export.yml"
            result = export_workflow(client, "app-1", output)  # type: ignore[arg-type]
            exported = output.read_text(encoding="utf-8")
        self.assertTrue(result["structure_matches_repository"])
        self.assertNotIn("vision-model", exported)
        self.assertEqual(yaml.safe_load(exported)["app"]["name"], "Social Media Campaign Report")

    def test_sse_and_required_output_keys(self) -> None:
        body = "data: " + json.dumps({"event": "workflow_started", "data": {}}) + "\n\n"
        body += "data: " + json.dumps({"event": "workflow_finished", "data": _successful_outputs()})
        result = assert_workflow_outputs(parse_sse_workflow_result(body))
        self.assertEqual(result["review_status"], "needs_review")
        self.assertEqual(result["json_export"], "VERIFIED")
        self.assertEqual(result["csv_export"], "VERIFIED")

    def test_unrelated_old_output_names_do_not_pass(self) -> None:
        with self.assertRaises(DeploymentError):
            assert_workflow_outputs(
                {
                    "status": "succeeded",
                    "outputs": {
                        "report_markdown": "# Report",
                        "report_json": "{}",
                        "report_csv": "x",
                    },
                }
            )

    @patch("scripts.dify_deploy.require_supported_contract", return_value=("1.17.1", {}))
    def test_draft_smoke_uses_console_upload_and_real_output_contract(
        self, _contract: MagicMock
    ) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / "screen.png"
            image.write_bytes(b"png")
            client.queue("UPLOAD", "/console/api/files/upload", (201, {"id": "file-1"}))
            sse = "data: " + json.dumps(
                {"event": "workflow_finished", "data": _successful_outputs()}
            )
            client.queue("POST", "/console/api/apps/app-1/workflows/draft/run", (200, sse))
            result = smoke_test(client, "app-1", [image], mode="draft")  # type: ignore[arg-type]
        self.assertEqual(result["workflow_status"], "succeeded")
        self.assertEqual(client.calls[0]["path"], "/console/api/files/upload")
        self.assertEqual(client.calls[0]["form_field"], "file")
        run_payload = client.calls[1]["payload"]
        self.assertIn("files", run_payload["inputs"])
        self.assertNotEqual(run_payload["inputs"]["files"], [])


if __name__ == "__main__":
    unittest.main()
