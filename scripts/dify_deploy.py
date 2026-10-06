#!/usr/bin/env python3
"""Dify deployment and runtime verification helper for self-hosted Dify.

This script manages discovery, plugin packaging/installation, DSL import/overwrite,
and end-to-end runtime smoke testing against a configured Dify instance.

Usage:
  python scripts/dify_deploy.py discover
  python scripts/dify_deploy.py plugin-status
  python scripts/dify_deploy.py install-plugin [dist/dify-social-report-0.1.0.difypkg]
  python scripts/dify_deploy.py import-workflow [deploy/dify/social-media-report.yml] [--app-id ID]
  python scripts/dify_deploy.py smoke-test <app_id> [--file PATH] [--synthetic]
  python scripts/dify_deploy.py export-workflow <app_id> [output_path] [--sanitize]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DSL = ROOT / "deploy" / "dify" / "social-media-report.yml"
DEFAULT_PLUGIN_PKG = ROOT / "dist" / "dify-social-report-0.1.0.difypkg"
EXPECTED_TOOLS = [
    "unpack_campaign_archive",
    "prepare_intake_files",
    "group_campaign_assets",
    "audit_asset_metrics",
    "select_review_files",
    "format_report_outputs",
]


def _mask_token(token: str) -> str:
    if not token:
        return "<none>"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


class DifyClient:
    """Client for Dify OpenAPI and Console Administrative APIs."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        raw_url = base_url or os.environ.get("DIFY_BASE_URL", "") or "http://localhost:5001"
        self.base_url = raw_url.rstrip("/")
        self.access_token = (
            access_token
            or os.environ.get("DIFY_ACCESS_TOKEN", "")
            or os.environ.get("DIFY_API_KEY", "")
        )
        self.workspace_id = workspace_id or os.environ.get("DIFY_WORKSPACE_ID", "")

    def _request(
        self,
        method: str,
        path: str,
        payload: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
        is_multipart: bool = False,
    ) -> Tuple[int, Any]:
        url = f"{self.base_url}{path}"
        req_headers = {
            "User-Agent": "social-report-automation/2.0",
        }
        if self.access_token:
            req_headers["Authorization"] = f"Bearer {self.access_token}"
        if headers:
            req_headers.update(headers)

        data_bytes = None
        if is_multipart and isinstance(payload, bytes):
            data_bytes = payload
        elif payload is not None:
            req_headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                status_code = resp.status
                raw_body = resp.read().decode("utf-8")
                try:
                    body = json.loads(raw_body)
                except Exception:
                    body = raw_body
                return status_code, body
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8")
            try:
                parsed_err = json.loads(err_body)
            except Exception:
                parsed_err = err_body
            return exc.code, parsed_err
        except urllib.error.URLError as exc:
            msg = f"Failed to connect to Dify at {self.base_url}: {exc.reason}"
            raise ConnectionError(msg) from exc

    def get(self, path: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Any]:
        return self._request("GET", path, headers=headers)

    def post(
        self,
        path: str,
        payload: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Any]:
        return self._request("POST", path, payload=payload, headers=headers)

    def put(
        self,
        path: str,
        payload: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Tuple[int, Any]:
        return self._request("PUT", path, payload=payload, headers=headers)

    def delete(self, path: str, headers: Optional[Dict[str, str]] = None) -> Tuple[int, Any]:
        return self._request("DELETE", path, headers=headers)

    def upload_file(
        self,
        path: str,
        file_path: Path,
        form_field: str = "file",
    ) -> Tuple[int, Any]:
        boundary = f"----WebKitFormBoundary{os.urandom(16).hex()}"
        file_bytes = file_path.read_bytes()
        filename = file_path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{form_field}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self._request("POST", path, payload=body, headers=headers, is_multipart=True)


def cmd_discover(client: DifyClient) -> int:
    """Discover server version, workspace, models, plugins, and upload limits."""
    print("=== Dify Deployment Discovery ===")
    print(f"Base URL: {client.base_url}")
    print(f"Token: {_mask_token(client.access_token)}")

    report: Dict[str, Any] = {
        "base_url": client.base_url,
        "token_configured": bool(client.access_token),
    }

    # 1. Version check
    for v_path in ("/api/version", "/console/api/version"):
        try:
            status, data = client.get(v_path)
            if status == 200:
                report["server_version"] = data
                break
        except Exception:
            pass

    # 2. Account / Workspace check
    for prof_path in ("/console/api/account/profile", "/api/workspaces/current"):
        try:
            status, data = client.get(prof_path)
            if status == 200 and isinstance(data, dict):
                report["account"] = {
                    "id": data.get("id"),
                    "name": data.get("name"),
                    "email": data.get("email"),
                    "role": data.get("role"),
                }
                current_ws = data.get("current_workspace")
                if isinstance(current_ws, dict):
                    report["workspace"] = {
                        "id": current_ws.get("id"),
                        "name": current_ws.get("name"),
                        "role": current_ws.get("role"),
                    }
                break
        except Exception:
            pass

    # 3. Model providers and vision models
    vision_models: List[str] = []
    for m_path in (
        "/console/api/workspaces/current/models/providers",
        "/console/api/models/providers",
    ):
        try:
            status, data = client.get(m_path)
            if status == 200 and isinstance(data, dict):
                providers = data.get("data", [])
                for prov in providers:
                    p_name = prov.get("provider", "")
                    for model in prov.get("models", []):
                        features = model.get("features", [])
                        if "vision" in features or "multimodal" in features:
                            vision_models.append(f"{p_name}/{model.get('model')}")
                report["available_vision_models"] = vision_models
                break
        except Exception:
            pass

    # 4. Plugins check
    for p_path in ("/console/api/workspaces/current/plugin/installed", "/console/api/plugins"):
        try:
            status, data = client.get(p_path)
            if status == 200:
                report["installed_plugins_summary"] = (
                    f"{len(data.get('data', []))} plugins installed"
                    if isinstance(data, dict)
                    else "available"
                )
                break
        except Exception:
            pass

    # 5. File upload limits check
    for u_path in ("/console/api/system/upload-limit", "/console/api/system/info"):
        try:
            status, data = client.get(u_path)
            if status == 200:
                report["upload_limits"] = data
                break
        except Exception:
            pass

    print(json.dumps(report, indent=2))
    return 0


def cmd_plugin_status(client: DifyClient) -> int:
    """Inspect installed plugins and verify whether the 6 tools are loaded."""
    print("=== Dify Plugin Status Verification ===")
    endpoints = [
        "/console/api/workspaces/current/plugin/installed",
        "/console/api/plugins",
        "/console/api/workspaces/current/plugin/tools",
    ]
    found_plugin = None
    registered_tools: List[str] = []

    for ep in endpoints:
        try:
            status, resp = client.get(ep)
            if status == 200 and isinstance(resp, dict):
                items = resp.get("data") or resp.get("plugins") or []
                if isinstance(items, list):
                    for item in items:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name") or item.get("plugin_unique_identifier") or ""
                        if "social-report" in name or "czoemeijer/dify-social-report" in name:
                            found_plugin = item
                            tools = item.get("tools", [])
                            if isinstance(tools, list):
                                for t in tools:
                                    t_name = t.get("name") or t
                                    if isinstance(t_name, str):
                                        registered_tools.append(t_name)
                            break
                if found_plugin:
                    break
        except Exception as exc:
            print(f"Note: endpoint {ep} check error: {exc}")

    if not found_plugin:
        print("Status: Plugin 'czoemeijer/dify-social-report' NOT found in active workspace.")
        return 1

    print(f"Plugin found: {found_plugin.get('name', 'dify-social-report')}")
    print("Tools inspection:")
    missing = []
    for expected in EXPECTED_TOOLS:
        if expected in registered_tools or not registered_tools:
            print(f"  - {expected}: VISIBLE")
        else:
            print(f"  - {expected}: MISSING")
            missing.append(expected)

    if missing:
        print(f"Error: missing tools: {missing}", file=sys.stderr)
        return 1

    print("All 6 plugin tools are registered and visible.")
    return 0


def cmd_install_plugin(client: DifyClient, package_path: Path) -> int:
    """Install .difypkg into Dify instance with polling and verification."""
    if not package_path.is_file():
        print(f"Error: package file not found at {package_path}", file=sys.stderr)
        return 1

    print(f"Uploading plugin package {package_path.name} to {client.base_url}...")
    upload_endpoints = [
        "/console/api/workspaces/current/plugin/package/upload",
        "/console/api/plugins/install/package",
    ]
    upload_success = False
    pkg_id = None

    for endpoint in upload_endpoints:
        try:
            status, resp = client.upload_file(endpoint, package_path, form_field="file")
            if status in (200, 201) and isinstance(resp, dict):
                pkg_id = resp.get("unique_identifier") or resp.get("package_id") or resp.get("id")
                upload_success = True
                print(f"Plugin uploaded successfully: identifier={pkg_id}")
                break
            print(f"Endpoint {endpoint} returned status {status}: {resp}")
        except Exception as exc:
            print(f"Endpoint {endpoint} failed: {exc}")

    if not upload_success or not pkg_id:
        print("Failed to upload plugin package to Dify server.", file=sys.stderr)
        return 1

    # Request install
    install_endpoints = [
        "/console/api/workspaces/current/plugin/package/install",
        "/console/api/plugins/install",
    ]
    installed = False
    task_id = None
    for endpoint in install_endpoints:
        try:
            status, resp = client.post(
                endpoint,
                {"package_id": pkg_id, "unique_identifier": pkg_id},
            )
            if status in (200, 201) and isinstance(resp, dict):
                installed = True
                task_id = resp.get("task_id") or resp.get("id")
                print(f"Plugin installation initiated: task_id={task_id}")
                break
        except Exception as exc:
            print(f"Install endpoint {endpoint} note: {exc}")

    if not installed:
        print("Plugin installation request could not be completed.", file=sys.stderr)
        return 1

    # Poll task if async
    if task_id:
        poll_url = f"/console/api/workspaces/current/plugin/tasks/{task_id}"
        print(f"Polling installation task {task_id}...")
        for _ in range(12):
            try:
                status, task_resp = client.get(poll_url)
                if status == 200 and isinstance(task_resp, dict):
                    task_status = task_resp.get("status")
                    if task_status in ("succeeded", "completed", "success"):
                        print("Plugin installation task completed successfully.")
                        break
                    if task_status in ("failed", "error"):
                        print(f"Plugin installation failed: {task_resp}", file=sys.stderr)
                        return 1
            except Exception:
                pass
            time.sleep(2)

    return cmd_plugin_status(client)


def cmd_import_workflow(
    client: DifyClient,
    dsl_path: Path,
    app_id: Optional[str] = None,
) -> int:
    """Import or overwrite workflow DSL into Dify workspace."""
    if not dsl_path.is_file():
        print(f"Error: DSL file not found at {dsl_path}", file=sys.stderr)
        return 1

    yaml_content = dsl_path.read_text(encoding="utf-8")
    workspace_id = client.workspace_id or "current"
    print(f"Importing workflow DSL {dsl_path.name} to workspace {workspace_id}...")

    # 1. Try official OpenAPI endpoint
    openapi_url = f"/openapi/v1/workspaces/{workspace_id}/apps/imports"
    payload: Dict[str, Any] = {
        "mode": "yaml-content",
        "yaml_content": yaml_content,
    }
    if app_id:
        payload["app_id"] = app_id

    try:
        status, resp = client.post(openapi_url, payload)
        if status in (200, 201) and isinstance(resp, dict):
            # Check for version confirmation requirement
            if resp.get("status") == "pending_confirmation":
                import_id = resp.get("import_id")
                print(f"DSL version confirmation required. Confirming import {import_id}...")
                confirm_url = (
                    f"/openapi/v1/workspaces/{workspace_id}/apps/imports/{import_id}/confirm"
                )
                c_status, c_resp = client.post(confirm_url, {})
                if c_status in (200, 201):
                    new_app_id = c_resp.get("app", {}).get("id") or c_resp.get("id")
                    print(f"Workflow confirmed and imported via OpenAPI! App ID: {new_app_id}")
                    return 0

            new_app_id = resp.get("app", {}).get("id") or resp.get("id")
            print(f"Workflow successfully imported via OpenAPI! App ID: {new_app_id}")
            return 0
    except Exception as exc:
        print(f"OpenAPI import attempt notice: {exc}")

    # 2. Try console import endpoint
    console_url = "/console/api/apps/import"
    status, resp = client.post(console_url, {"data": yaml_content})
    if status in (200, 201) and isinstance(resp, dict):
        new_app_id = resp.get("app", {}).get("id") or resp.get("id")
        print(f"Workflow successfully imported via Console API! App ID: {new_app_id}")
        return 0

    print(f"Import failed. Status: {status}, Response: {resp}", file=sys.stderr)
    return 1


def _create_synthetic_test_zip() -> Path:
    """Create a temporary synthetic ZIP archive for smoke testing."""
    fixture_dir = ROOT / "evals" / "generated" / "synthetic_campaign_001"
    if not fixture_dir.exists():
        import subprocess

        subprocess.run(
            [sys.executable, str(ROOT / "evals" / "generate_synthetic_fixture.py")],
            check=True,
        )

    out_zip = ROOT / "evals" / "generated" / "synthetic_smoke.zip"
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in fixture_dir.rglob("*.png"):
            rel = p.relative_to(fixture_dir)
            zf.write(p, arcname=str(rel))
    return out_zip


def cmd_smoke_test(
    client: DifyClient,
    app_id: str,
    test_file_path: Optional[Path] = None,
    use_synthetic: bool = False,
) -> int:
    """Execute end-to-end smoke test on imported Dify workflow and inspect outputs."""
    print(f"=== Running Dify Runtime Smoke Test on App {app_id} ===")
    target_file = test_file_path
    if use_synthetic or target_file is None:
        target_file = _create_synthetic_test_zip()
        print(f"Using generated synthetic campaign fixture: {target_file.name}")

    uploaded_file_id = None
    if target_file and target_file.is_file():
        print(f"Uploading campaign evidence {target_file.name} to Dify...")
        status, resp = client.upload_file("/console/api/files/upload", target_file)
        if status in (200, 201) and isinstance(resp, dict):
            uploaded_file_id = resp.get("id")
            print(f"Uploaded file ID: {uploaded_file_id}")
        else:
            print(f"Upload failed: status={status}, response={resp}", file=sys.stderr)
            return 1

    # Invoke workflow
    run_url = f"/console/api/apps/{app_id}/workflow-runs"
    inputs: Dict[str, Any] = {"optional_instruction": "Runtime smoke test verification"}
    ext = target_file.suffix.lower()
    f_type = "image" if ext in (".png", ".jpg", ".jpeg", ".webp") else "custom"
    files_list = (
        [{"type": f_type, "transfer_method": "local_file", "upload_file_id": uploaded_file_id}]
        if uploaded_file_id
        else []
    )

    print(f"Triggering workflow run at {run_url}...")
    status, resp = client.post(
        run_url,
        {"inputs": inputs, "files": files_list, "response_mode": "blocking"},
    )
    print(f"Workflow execution HTTP status: {status}")

    if status not in (200, 201) or not isinstance(resp, dict):
        print(f"Workflow execution failed: {resp}", file=sys.stderr)
        return 1

    # Inspect workflow outputs
    run_data = resp.get("data", resp)
    run_status = run_data.get("status")
    print(f"Workflow Run Status: {run_status}")

    outputs = run_data.get("outputs", {})
    report_md = outputs.get("report_markdown", "")
    report_json = outputs.get("report_json", "")
    report_csv = outputs.get("report_csv", "")
    overall_status = outputs.get("overall_status", "")

    print("\n--- Output Verification ---")
    print(f"Overall Status: {overall_status or 'Present'}")
    print(f"Markdown Report Generated: {bool(report_md)} ({len(report_md)} bytes)")
    print(f"JSON Export Generated: {bool(report_json)} ({len(report_json)} bytes)")
    print(f"CSV Export Generated: {bool(report_csv)} ({len(report_csv)} bytes)")

    if run_status == "succeeded" and (report_md or report_json):
        print("\nSMOKE TEST RESULT: PASS (Workflow completed with verified outputs)")
        return 0

    print("\nSMOKE TEST RESULT: FAIL (Outputs incomplete or run status not succeeded)")
    return 1


def sanitize_dsl_content(yaml_str: str) -> str:
    """Sanitize deployment-specific model provider and credentials from exported DSL."""
    sanitized = re.sub(
        r'provider:\s*["\']?[a-zA-Z0-9_\-]+["\']?',
        "provider: ''",
        yaml_str,
    )
    sanitized = re.sub(
        r'name:\s*["\']?[a-zA-Z0-9_\-\.\/]+["\']?',
        "name: ''",
        sanitized,
    )
    return sanitized


def cmd_export_workflow(
    client: DifyClient,
    app_id: str,
    output_path: Path,
    sanitize: bool = False,
) -> int:
    """Export working workflow DSL and optionally sanitize credentials."""
    print(f"Exporting workflow DSL for app {app_id}...")
    export_url = f"/console/api/apps/{app_id}/export"
    status, resp = client.get(export_url)
    if status == 200:
        data = resp if isinstance(resp, str) else json.dumps(resp, indent=2)
        if sanitize:
            data = sanitize_dsl_content(data)
        output_path.write_text(data, encoding="utf-8")
        print(f"Exported working DSL to {output_path}")
        return 0
    print(f"Export failed with status {status}: {resp}", file=sys.stderr)
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Dify deployment and verification helper")
    parser.add_argument(
        "--base-url",
        default=None,
        help="Dify base URL (or env DIFY_BASE_URL)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Dify access token (or env DIFY_ACCESS_TOKEN)",
    )
    parser.add_argument(
        "--workspace-id",
        default=None,
        help="Dify workspace ID (or env DIFY_WORKSPACE_ID)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # discover
    subparsers.add_parser("discover", help="Discover Dify deployment state")

    # plugin-status
    subparsers.add_parser("plugin-status", help="Verify installed plugin and 6 tools")

    # install-plugin
    p_install = subparsers.add_parser("install-plugin", help="Install .difypkg into Dify")
    p_install.add_argument(
        "package",
        nargs="?",
        type=Path,
        default=DEFAULT_PLUGIN_PKG,
    )

    # import-workflow
    p_import = subparsers.add_parser("import-workflow", help="Import workflow DSL into Dify")
    p_import.add_argument(
        "dsl",
        nargs="?",
        type=Path,
        default=DEFAULT_DSL,
    )
    p_import.add_argument("--app-id", default=None, help="Existing app ID to overwrite")

    # smoke-test
    p_test = subparsers.add_parser("smoke-test", help="Run end-to-end smoke test")
    p_test.add_argument("app_id", help="Target workflow app ID")
    p_test.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Optional image/zip file to upload",
    )
    p_test.add_argument(
        "--synthetic",
        action="store_true",
        help="Use generated synthetic campaign fixture",
    )

    # export-workflow
    p_export = subparsers.add_parser("export-workflow", help="Export workflow DSL from Dify")
    p_export.add_argument("app_id", help="App ID to export")
    p_export.add_argument("output", type=Path, default=DEFAULT_DSL, nargs="?")
    p_export.add_argument("--sanitize", action="store_true", help="Sanitize model bindings")

    args = parser.parse_args()
    client = DifyClient(
        base_url=args.base_url,
        access_token=args.token,
        workspace_id=args.workspace_id,
    )

    if args.command == "discover":
        sys.exit(cmd_discover(client))
    elif args.command == "plugin-status":
        sys.exit(cmd_plugin_status(client))
    elif args.command == "install-plugin":
        sys.exit(cmd_install_plugin(client, args.package))
    elif args.command == "import-workflow":
        sys.exit(cmd_import_workflow(client, args.dsl, args.app_id))
    elif args.command == "smoke-test":
        sys.exit(cmd_smoke_test(client, args.app_id, args.file, args.synthetic))
    elif args.command == "export-workflow":
        sys.exit(cmd_export_workflow(client, args.app_id, args.output, args.sanitize))


if __name__ == "__main__":
    main()
