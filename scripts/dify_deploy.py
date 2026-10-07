#!/usr/bin/env python3
"""Version-pinned Dify deployment and runtime verification helper.

Supported released contracts:

* Dify 1.14.2: Console API for plugin administration, DSL import/export,
  dependency checks, file upload, and draft execution.
* Dify 1.17.1: account-scoped OpenAPI for DSL import/export, dependency
  checks, app file upload, and published execution; Console API remains the
  administrative surface for plugin installation and draft execution.

The helper deliberately fails closed for other server versions. It never
uses an App Service API key as an account or Console credential.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DSL = ROOT / "deploy" / "dify" / "social-media-report.yml"
DEFAULT_PLUGIN_PKG = ROOT / "dist" / "dify-social-report-0.1.1.difypkg"
DEFAULT_ENV_FILE = ROOT / ".env.local"
USER_ENV_FILE = Path.home() / ".config" / "social-report" / "dify.env"
PROVIDER_YAML = ROOT / "plugins" / "dify-social-report" / "provider" / "social_report.yaml"

SUPPORTED_CONTRACTS = {
    "1.14.2": "console-1.14.2",
    "1.17.1": "openapi-1.17.1",
}
ENV_KEYS = (
    "DIFY_BASE_URL",
    "DIFY_WORKSPACE_ID",
    "DIFY_OPENAPI_TOKEN",
    "DIFY_CONSOLE_ACCESS_TOKEN",
    "DIFY_CSRF_TOKEN",
    "DIFY_MODEL_PROVIDER",
    "DIFY_MODEL_NAME",
)
REVIEW_STATUSES = {"verified", "verified_with_warning", "needs_review", "rejected"}
SCOPE_BUCKETS = {"organic", "paid", "mixed_or_unknown", "unknown"}
ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class DeploymentError(RuntimeError):
    """A safe, user-facing deployment failure."""


@dataclass(frozen=True)
class DifySettings:
    base_url: str
    workspace_id: str = ""
    openapi_token: str = ""
    console_access_token: str = ""
    csrf_token: str = ""
    model_provider: str = ""
    model_name: str = ""


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: Any
    headers: Mapping[str, str]
    body_sha256: str


def _strip_unquoted_comment(value: str) -> str:
    quote: Optional[str] = None
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and quote == '"':
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.strip()


def _parse_env_value(value: str, *, path: Path, line_number: int) -> str:
    value = _strip_unquoted_comment(value.strip())
    if not value:
        return ""
    if value[0] not in {"'", '"'}:
        return value.strip()
    if len(value) < 2 or value[-1] != value[0]:
        raise DeploymentError(f"{path}:{line_number}: unterminated quoted value")
    inner = value[1:-1]
    if value[0] == "'":
        return inner
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise DeploymentError(f"{path}:{line_number}: invalid quoted value") from exc
    if not isinstance(parsed, str):
        raise DeploymentError(f"{path}:{line_number}: quoted value must be a string")
    return parsed


def parse_env_file(path: Path, *, missing_ok: bool = False) -> Dict[str, str]:
    """Parse a narrow dotenv subset without shell evaluation or expansion."""

    if not path.is_file():
        if missing_ok:
            return {}
        raise DeploymentError(f"Environment file not found: {path}")
    values: Dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise DeploymentError(f"{path}:{line_number}: expected KEY=VALUE")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not ENV_KEY_RE.fullmatch(key):
            raise DeploymentError(f"{path}:{line_number}: invalid environment key")
        values[key] = _parse_env_value(raw_value, path=path, line_number=line_number)
    return values


def resolve_settings(
    *,
    environ: Optional[Mapping[str, str]] = None,
    env_file: Optional[Path] = None,
    cli_values: Optional[Mapping[str, Optional[str]]] = None,
) -> DifySettings:
    """Resolve user config < repo config < explicit file < process env < CLI."""

    process_env = dict(os.environ if environ is None else environ)
    file_values: Dict[str, str] = {}
    file_values.update(parse_env_file(USER_ENV_FILE, missing_ok=True))
    file_values.update(parse_env_file(DEFAULT_ENV_FILE, missing_ok=True))
    if env_file is not None:
        file_values.update(parse_env_file(env_file))
    resolved = {key: file_values.get(key, "") for key in ENV_KEYS}
    for key in ENV_KEYS:
        if key in process_env:
            resolved[key] = process_env[key]
    for key, value in (cli_values or {}).items():
        if key in resolved and value is not None:
            resolved[key] = value
    return DifySettings(
        base_url=resolved["DIFY_BASE_URL"].strip().rstrip("/"),
        workspace_id=resolved["DIFY_WORKSPACE_ID"].strip(),
        openapi_token=resolved["DIFY_OPENAPI_TOKEN"].strip(),
        console_access_token=resolved["DIFY_CONSOLE_ACCESS_TOKEN"].strip(),
        csrf_token=resolved["DIFY_CSRF_TOKEN"].strip(),
        model_provider=resolved["DIFY_MODEL_PROVIDER"].strip(),
        model_name=resolved["DIFY_MODEL_NAME"].strip(),
    )


def _redact(value: Any, secrets: Iterable[str]) -> Any:
    """Redact configured secrets in text or recursively in JSON-like data."""

    if isinstance(value, str):
        result = value
        for secret in secrets:
            if secret:
                result = result.replace(secret, "<redacted>")
        return result
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    if isinstance(value, dict):
        return {key: _redact(item, secrets) for key, item in value.items()}
    return value


def _error_detail(body: Any, secrets: Iterable[str]) -> str:
    """Return a short, redacted server error without dumping response data."""

    safe = _redact(body, secrets)
    if isinstance(safe, dict):
        code = safe.get("code")
        message = safe.get("message") or safe.get("error")
        parts = [str(part) for part in (code, message) if part]
        detail = ": ".join(parts)
    elif isinstance(safe, str):
        detail = safe.strip()
    else:
        detail = ""
    return detail[:500]


class DifyClient:
    """Small HTTP client with intentionally separate OpenAPI and Console auth."""

    def __init__(self, settings: DifySettings, *, timeout: float = 60.0):
        if not settings.base_url:
            raise DeploymentError("DIFY_BASE_URL is required")
        self.settings = settings
        self.base_url = settings.base_url
        self.timeout = timeout
        self.catalog_fingerprint = ""

    @property
    def secrets(self) -> Tuple[str, ...]:
        return (
            self.settings.openapi_token,
            self.settings.console_access_token,
            self.settings.csrf_token,
        )

    def _auth_headers(self, auth: str) -> Dict[str, str]:
        if auth == "none":
            return {}
        if auth == "openapi":
            if not self.settings.openapi_token:
                raise DeploymentError("DIFY_OPENAPI_TOKEN is required for this operation")
            return {"Authorization": f"Bearer {self.settings.openapi_token}"}
        if auth == "console":
            missing = []
            if not self.settings.console_access_token:
                missing.append("DIFY_CONSOLE_ACCESS_TOKEN")
            if not self.settings.csrf_token:
                missing.append("DIFY_CSRF_TOKEN")
            if missing:
                raise DeploymentError(f"Console authentication requires: {', '.join(missing)}")
            return {
                "Authorization": f"Bearer {self.settings.console_access_token}",
                "X-CSRF-Token": self.settings.csrf_token,
                "Cookie": (
                    f"csrf_token={self.settings.csrf_token}; "
                    f"__Host-csrf_token={self.settings.csrf_token}"
                ),
            }
        raise DeploymentError(f"Unknown authentication context: {auth}")

    def request(
        self,
        method: str,
        path: str,
        *,
        auth: str,
        payload: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        raw_payload: Optional[bytes] = None,
    ) -> Tuple[int, Any]:
        if auth == "openapi" and not self.catalog_fingerprint:
            self.refresh_catalog()
        result = self._request_once(
            method,
            path,
            auth=auth,
            payload=payload,
            headers=headers,
            raw_payload=raw_payload,
        )
        if (
            auth == "openapi"
            and method.upper() in {"GET", "HEAD"}
            and result.status == 412
            and isinstance(result.body, dict)
            and result.body.get("code") == "catalog_stale"
        ):
            self.refresh_catalog()
            result = self._request_once(
                method,
                path,
                auth=auth,
                payload=payload,
                headers=headers,
                raw_payload=raw_payload,
            )
        return result.status, result.body

    def _request_once(
        self,
        method: str,
        path: str,
        *,
        auth: str,
        payload: Optional[Any] = None,
        headers: Optional[Mapping[str, str]] = None,
        raw_payload: Optional[bytes] = None,
    ) -> HttpResult:
        request_headers = {
            "User-Agent": "social-report-automation/2.0 dify-contract-client",
            **self._auth_headers(auth),
        }
        if auth == "openapi":
            request_headers["X-Dify-Catalog"] = self.catalog_fingerprint
        if headers:
            request_headers.update(headers)
        data: Optional[bytes] = raw_payload
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers=request_headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw_bytes = response.read()
                raw_body = raw_bytes.decode("utf-8")
                try:
                    body: Any = json.loads(raw_body)
                except json.JSONDecodeError:
                    body = raw_body
                response_headers = {
                    str(key).lower(): str(value) for key, value in response.headers.items()
                }
                self._capture_catalog_fingerprint(response_headers)
                return HttpResult(
                    status=response.status,
                    body=body,
                    headers=response_headers,
                    body_sha256=hashlib.sha256(raw_bytes).hexdigest(),
                )
        except urllib.error.HTTPError as exc:
            raw_bytes = exc.read()
            raw_body = raw_bytes.decode("utf-8", errors="replace")
            try:
                body = json.loads(raw_body)
            except json.JSONDecodeError:
                body = raw_body
            response_headers = (
                {str(key).lower(): str(value) for key, value in exc.headers.items()}
                if exc.headers
                else {}
            )
            self._capture_catalog_fingerprint(response_headers)
            return HttpResult(
                status=exc.code,
                body=_redact(body, self.secrets),
                headers=response_headers,
                body_sha256=hashlib.sha256(raw_bytes).hexdigest(),
            )
        except urllib.error.URLError as exc:
            raise DeploymentError(
                f"Failed to connect to Dify at {self.base_url}: {exc.reason}"
            ) from exc

    def _capture_catalog_fingerprint(self, headers: Mapping[str, str]) -> None:
        fingerprint = headers.get("x-dify-catalog", "").strip().lower()
        if not fingerprint:
            return
        if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
            raise DeploymentError("Dify returned a malformed OpenAPI catalog fingerprint")
        self.catalog_fingerprint = fingerprint

    def refresh_catalog(self) -> None:
        result = self._request_once("GET", "/openapi/v1/_catalog", auth="none")
        fingerprint = result.headers.get("x-dify-catalog", "").strip().lower()
        if result.status != 200:
            raise DeploymentError(f"OpenAPI catalog discovery failed with HTTP {result.status}")
        if not fingerprint:
            raise DeploymentError("OpenAPI catalog response is missing its catalog fingerprint")
        if fingerprint != result.body_sha256:
            raise DeploymentError("OpenAPI catalog fingerprint does not match the catalog body")
        self.catalog_fingerprint = fingerprint

    def get(self, path: str, *, auth: str) -> Tuple[int, Any]:
        return self.request("GET", path, auth=auth)

    def post(self, path: str, payload: Any, *, auth: str) -> Tuple[int, Any]:
        return self.request("POST", path, auth=auth, payload=payload)

    def upload_file(
        self, path: str, file_path: Path, *, form_field: str, auth: str
    ) -> Tuple[int, Any]:
        boundary = f"----social-report-{os.urandom(12).hex()}"
        file_bytes = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{form_field}"; filename="{file_path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode()
        body += file_bytes + f"\r\n--{boundary}--\r\n".encode()
        return self.request(
            "POST",
            path,
            auth=auth,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            raw_payload=body,
        )


def _http_capability_state(status: int) -> str:
    if status == 200:
        return "VERIFIED"
    if status in {401, 403}:
        return "UNAUTHORIZED"
    if status == 404:
        return "UNSUPPORTED_VERSION"
    return "ERROR"


def discover_vision_models(client: DifyClient) -> Dict[str, Any]:
    """List configured LLM models that explicitly advertise vision support."""

    status, body = client.get(
        "/console/api/workspaces/current/models/model-types/llm", auth="console"
    )
    if status != 200 or not isinstance(body, dict) or not isinstance(body.get("data"), list):
        return {"state": _http_capability_state(status), "models": []}
    models = []
    for provider in body["data"]:
        if not isinstance(provider, dict):
            continue
        provider_id = provider.get("provider")
        provider_status = provider.get("status")
        for model in provider.get("models", []):
            if not isinstance(model, dict):
                continue
            features = model.get("features") or []
            if "vision" not in features and "multimodal" not in features:
                continue
            models.append(
                {
                    "provider": provider_id,
                    "model": model.get("model"),
                    "provider_status": provider_status,
                    "model_status": model.get("status"),
                }
            )
    return {"state": "VERIFIED", "models": models}


def discover_server(client: DifyClient) -> Dict[str, Any]:
    """Discover an exact released version and authenticated capabilities."""

    report: Dict[str, Any] = {
        "base_url": client.base_url,
        "version": None,
        "edition": None,
        "version_state": "ERROR",
        "capabilities": {},
        "credentials": {
            "openapi_token": "configured" if client.settings.openapi_token else "missing",
            "console_access_token": (
                "configured" if client.settings.console_access_token else "missing"
            ),
            "csrf_token": "configured" if client.settings.csrf_token else "missing",
        },
    }
    status, body = client.get("/openapi/v1/_version", auth="none")
    if status == 200 and isinstance(body, dict) and isinstance(body.get("version"), str):
        report.update(
            version=body["version"],
            edition=body.get("edition"),
            version_state="VERIFIED",
            contract=SUPPORTED_CONTRACTS.get(body["version"], "unsupported"),
        )
        health_status, health = client.get("/openapi/v1/_health", auth="none")
        report["capabilities"]["openapi_health"] = (
            "VERIFIED"
            if health_status == 200 and isinstance(health, dict) and health.get("ok") is True
            else "ERROR"
        )
    else:
        status, body = client.get("/console/api/version?current_version=0.0.0", auth="none")
        if status == 200 and isinstance(body, dict) and isinstance(body.get("version"), str):
            report.update(
                version=body["version"],
                version_state="VERIFIED",
                contract=SUPPORTED_CONTRACTS.get(body["version"], "unsupported"),
            )
            report["capabilities"]["openapi_health"] = "UNSUPPORTED_VERSION"
    version = report.get("version")
    report["capabilities"]["released_contract"] = (
        "VERIFIED" if version in SUPPORTED_CONTRACTS else "UNSUPPORTED_VERSION"
    )
    if version == "1.17.1":
        try:
            client.refresh_catalog()
        except DeploymentError:
            report["capabilities"]["openapi_catalog"] = "ERROR"
        else:
            report["capabilities"]["openapi_catalog"] = "VERIFIED"
    else:
        report["capabilities"]["openapi_catalog"] = "UNSUPPORTED_VERSION"
    if version == "1.17.1" and client.settings.openapi_token:
        openapi_status, _ = client.get("/openapi/v1/workspaces", auth="openapi")
        report["capabilities"]["openapi_account"] = _http_capability_state(openapi_status)
    elif version == "1.17.1":
        report["capabilities"]["openapi_account"] = "UNAVAILABLE"
    else:
        report["capabilities"]["openapi_account"] = "UNSUPPORTED_VERSION"
    if client.settings.console_access_token and client.settings.csrf_token:
        console_status, _ = client.get("/console/api/account/profile", auth="console")
        report["capabilities"]["console_admin"] = _http_capability_state(console_status)
    else:
        report["capabilities"]["console_admin"] = "UNAVAILABLE"
    if report["capabilities"]["console_admin"] == "VERIFIED":
        report["vision_models"] = discover_vision_models(client)
    else:
        report["vision_models"] = {"state": "UNAVAILABLE", "models": []}
    report["capabilities"]["openapi_dsl_import"] = (
        report["capabilities"]["openapi_account"] if version == "1.17.1" else "UNSUPPORTED_VERSION"
    )
    report["capabilities"]["console_plugin_management"] = report["capabilities"]["console_admin"]
    return report


def require_supported_contract(client: DifyClient) -> Tuple[str, Dict[str, Any]]:
    report = discover_server(client)
    version = report.get("version")
    if version not in SUPPORTED_CONTRACTS:
        raise DeploymentError(
            f"Unsupported Dify server version {version!r}; supported released contracts are "
            f"{', '.join(sorted(SUPPORTED_CONTRACTS))}"
        )
    return str(version), report


def expected_tool_names(provider_path: Path = PROVIDER_YAML) -> List[str]:
    provider = yaml.safe_load(provider_path.read_text(encoding="utf-8"))
    tool_paths = provider.get("tools") if isinstance(provider, dict) else None
    if not isinstance(tool_paths, list) or not tool_paths:
        raise DeploymentError(f"No tools registered in {provider_path}")
    names = []
    plugin_root = provider_path.parents[1]
    for relative_path in tool_paths:
        tool_path = plugin_root / str(relative_path)
        declaration = yaml.safe_load(tool_path.read_text(encoding="utf-8"))
        name = (
            declaration.get("identity", {}).get("name") if isinstance(declaration, dict) else None
        )
        if not isinstance(name, str) or not name:
            raise DeploymentError(f"Tool identity is missing in {tool_path}")
        names.append(name)
    return names


def expected_plugin_identifier(dsl_path: Path = DEFAULT_DSL) -> str:
    dsl = yaml.safe_load(dsl_path.read_text(encoding="utf-8"))
    dependencies = dsl.get("dependencies", []) if isinstance(dsl, dict) else []
    for dependency in dependencies:
        if dependency.get("type") == "package":
            identifier = dependency.get("value", {}).get("plugin_unique_identifier")
            if isinstance(identifier, str) and identifier:
                return identifier
    raise DeploymentError(f"Plugin dependency identifier is missing in {dsl_path}")


def _plugin_identity(identifier: str) -> Tuple[str, str, str]:
    match = re.fullmatch(r"([^:]+):(\d+\.\d+\.\d+)@([0-9a-f]{64})", identifier)
    if not match:
        raise DeploymentError(f"Malformed plugin unique identifier: {identifier!r}")
    return match.group(1), match.group(2), match.group(3)


def _validate_deployment_plugin_identifier(identifier: str) -> None:
    repository_id, repository_version, _ = _plugin_identity(expected_plugin_identifier())
    deployment_id, deployment_version, _ = _plugin_identity(identifier)
    if (deployment_id, deployment_version) != (repository_id, repository_version):
        raise DeploymentError(
            "Deployment plugin identifier must preserve the repository plugin id and version"
        )


def bind_plugin_dependency(yaml_content: str, identifier: str) -> str:
    """Bind a deployment-only signed-package checksum without changing the repository DSL."""

    _validate_deployment_plugin_identifier(identifier)
    data = yaml.safe_load(yaml_content)
    dependencies = data.get("dependencies", []) if isinstance(data, dict) else []
    bound = 0
    for dependency in dependencies:
        if not isinstance(dependency, dict) or dependency.get("type") != "package":
            continue
        value = dependency.get("value")
        if not isinstance(value, dict) or "plugin_unique_identifier" not in value:
            continue
        current = value.get("plugin_unique_identifier")
        if not isinstance(current, str):
            continue
        current_id, current_version, _ = _plugin_identity(current)
        target_id, target_version, _ = _plugin_identity(identifier)
        if (current_id, current_version) == (target_id, target_version):
            value["plugin_unique_identifier"] = identifier
            bound += 1
    if bound != 1:
        raise DeploymentError(f"Expected one compatible package dependency, found {bound}")
    rendered = str(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120))
    yaml.safe_load(rendered)
    return rendered


def verify_plugin(
    client: DifyClient, expected_identifier: Optional[str] = None
) -> Dict[str, Any]:
    """Verify exact installation identity plus provider and tool visibility."""

    expected_identifier = expected_identifier or expected_plugin_identifier()
    _validate_deployment_plugin_identifier(expected_identifier)
    expected_tools = expected_tool_names()
    plugin_id, expected_version, expected_checksum = _plugin_identity(expected_identifier)
    status, body = client.get(
        "/console/api/workspaces/current/plugin/list?page=1&page_size=256", auth="console"
    )
    if status != 200 or not isinstance(body, dict):
        raise DeploymentError(f"Plugin list failed with HTTP {status}")
    plugins = body.get("plugins")
    if not isinstance(plugins, list):
        raise DeploymentError("Plugin list response did not contain a plugins array")
    exact = next(
        (
            item
            for item in plugins
            if isinstance(item, dict)
            and item.get("plugin_unique_identifier") == expected_identifier
        ),
        None,
    )
    same_plugin = [
        item
        for item in plugins
        if isinstance(item, dict)
        and (item.get("plugin_id") == plugin_id or item.get("name") == plugin_id.split("/", 1)[-1])
    ]
    if exact is None:
        return {
            "status": "FAIL",
            "expected_identifier": expected_identifier,
            "installed": False,
            "mismatched_identifiers": [
                item.get("plugin_unique_identifier")
                for item in same_plugin
                if item.get("plugin_unique_identifier")
            ],
            "provider_loaded": False,
            "tools_state": "NOT_VERIFIED",
        }
    identifier_ok = exact.get("plugin_unique_identifier") == expected_identifier
    version_ok = exact.get("version") == expected_version
    checksum_ok = exact.get("checksum") == expected_checksum
    provider_status, provider_body = client.get(
        "/console/api/workspaces/current/tool-providers", auth="console"
    )
    if provider_status != 200 or not isinstance(provider_body, list):
        return {
            "status": "PARTIAL",
            "expected_identifier": expected_identifier,
            "installed": True,
            "identity_verified": identifier_ok,
            "version_verified": version_ok,
            "checksum_verified": checksum_ok,
            "provider_loaded": False,
            "tools_state": "NOT_VERIFIED",
        }
    provider = next(
        (
            item
            for item in provider_body
            if isinstance(item, dict)
            and item.get("plugin_unique_identifier") == expected_identifier
        ),
        None,
    )
    if provider is None:
        return {
            "status": "FAIL",
            "expected_identifier": expected_identifier,
            "installed": True,
            "identity_verified": identifier_ok,
            "version_verified": version_ok,
            "checksum_verified": checksum_ok,
            "provider_loaded": False,
            "tools_state": "MISSING_PROVIDER",
        }
    provider_name = provider.get("name") or provider.get("id")
    tools = provider.get("tools")
    if (not isinstance(tools, list) or not tools) and isinstance(provider_name, str):
        tool_path = (
            "/console/api/workspaces/current/tool-provider/builtin/"
            f"{urllib.parse.quote(provider_name, safe='/')}/tools"
        )
        tools_status, tools_body = client.get(tool_path, auth="console")
        tools = tools_body if tools_status == 200 and isinstance(tools_body, list) else None
    if not isinstance(tools, list) or not tools:
        tools_state = "NOT_VERIFIED"
        actual_tools = []
    else:
        actual_tools = sorted(
            {
                str(tool.get("name"))
                for tool in tools
                if isinstance(tool, dict) and isinstance(tool.get("name"), str)
            }
        )
        missing = sorted(set(expected_tools) - set(actual_tools))
        tools_state = "VERIFIED" if not missing else "MISSING"
    all_verified = identifier_ok and version_ok and checksum_ok and tools_state == "VERIFIED"
    overall = "PASS" if all_verified else ("PARTIAL" if tools_state == "NOT_VERIFIED" else "FAIL")
    return {
        "status": overall,
        "expected_identifier": expected_identifier,
        "installed": True,
        "identity_verified": identifier_ok,
        "version_verified": version_ok,
        "checksum_verified": checksum_ok,
        "provider_loaded": True,
        "tools_state": tools_state,
        "expected_tools": expected_tools,
        "visible_tools": actual_tools,
        "missing_tools": sorted(set(expected_tools) - set(actual_tools)),
    }


def poll_plugin_task(
    client: DifyClient,
    task_id: str,
    *,
    timeout: float = 120.0,
    initial_backoff: float = 1.0,
) -> Dict[str, Any]:
    deadline = time.monotonic() + timeout
    backoff = initial_backoff
    while True:
        status, body = client.get(
            f"/console/api/workspaces/current/plugin/tasks/{urllib.parse.quote(task_id)}",
            auth="console",
        )
        if status != 200 or not isinstance(body, dict) or not isinstance(body.get("task"), dict):
            raise DeploymentError(f"Plugin task polling failed with HTTP {status}")
        task: Dict[str, Any] = body["task"]
        task_status = task.get("status")
        if task_status == "success":
            return task
        if task_status == "failed":
            messages = [str(task.get("message", ""))]
            for plugin in task.get("plugins", []):
                if isinstance(plugin, dict) and plugin.get("message"):
                    messages.append(str(plugin["message"]))
            message = "; ".join(part for part in messages if part) or "no server message"
            raise DeploymentError(f"Plugin installation failed: {_redact(message, client.secrets)}")
        if task_status not in {"pending", "running"}:
            raise DeploymentError(f"Plugin task returned unknown status: {task_status!r}")
        if time.monotonic() >= deadline:
            raise DeploymentError(f"Plugin installation timed out after {timeout:g} seconds")
        time.sleep(backoff)
        backoff = min(backoff * 1.5, 5.0)


def install_plugin(
    client: DifyClient,
    package_path: Path,
    *,
    timeout: float = 120.0,
    replace_installed: bool = False,
) -> Dict[str, Any]:
    if not package_path.is_file():
        raise DeploymentError(f"Plugin package not found: {package_path}")
    require_supported_contract(client)
    upload_status, upload = client.upload_file(
        "/console/api/workspaces/current/plugin/upload/pkg",
        package_path,
        form_field="pkg",
        auth="console",
    )
    if upload_status != 200 or not isinstance(upload, dict):
        detail = _error_detail(upload, client.secrets)
        suffix = f": {detail}" if detail else ""
        raise DeploymentError(f"Plugin upload failed with HTTP {upload_status}{suffix}")
    unique_identifier = upload.get("unique_identifier")
    if not isinstance(unique_identifier, str) or not unique_identifier:
        raise DeploymentError("Plugin upload response is missing unique_identifier")
    repository_identifier = expected_plugin_identifier()
    _validate_deployment_plugin_identifier(unique_identifier)
    replaced_identifier: Optional[str] = None
    if replace_installed:
        plugin_id, _, _ = _plugin_identity(unique_identifier)
        list_status, list_body = client.get(
            "/console/api/workspaces/current/plugin/list?page=1&page_size=256",
            auth="console",
        )
        plugins = list_body.get("plugins") if isinstance(list_body, dict) else None
        if list_status != 200 or not isinstance(plugins, list):
            raise DeploymentError(f"Plugin replacement preflight failed with HTTP {list_status}")
        existing = next(
            (
                item
                for item in plugins
                if isinstance(item, dict) and item.get("plugin_id") == plugin_id
            ),
            None,
        )
        if existing and existing.get("plugin_unique_identifier") != unique_identifier:
            installation_id = existing.get("installation_id")
            if not isinstance(installation_id, str) or not installation_id:
                raise DeploymentError("Installed plugin is missing installation_id")
            uninstall_status, uninstall = client.post(
                "/console/api/workspaces/current/plugin/uninstall",
                {"plugin_installation_id": installation_id, "preserve_credentials": True},
                auth="console",
            )
            if (
                uninstall_status != 200
                or not isinstance(uninstall, dict)
                or uninstall.get("success") is not True
            ):
                raise DeploymentError(
                    f"Plugin replacement uninstall failed with HTTP {uninstall_status}"
                )
            replaced_identifier = str(existing.get("plugin_unique_identifier") or "")
    install_status, install = client.post(
        "/console/api/workspaces/current/plugin/install/pkg",
        {"plugin_unique_identifiers": [unique_identifier]},
        auth="console",
    )
    if install_status != 200 or not isinstance(install, dict):
        raise DeploymentError(f"Plugin install request failed with HTTP {install_status}")
    all_installed = install.get("all_installed") is True
    task_id = install.get("task_id")
    if not all_installed:
        if not isinstance(task_id, str) or not task_id:
            raise DeploymentError("Plugin install response is missing task_id")
        poll_plugin_task(client, task_id, timeout=timeout)
    verification = verify_plugin(client, unique_identifier)
    if verification["status"] != "PASS":
        raise DeploymentError(
            f"Plugin installation finished but verification was {verification['status']}"
        )
    return {
        "unique_identifier": unique_identifier,
        "repository_identifier": repository_identifier,
        "deployment_checksum_differs": unique_identifier != repository_identifier,
        "replaced_identifier": replaced_identifier,
        "package_sha256": hashlib.sha256(package_path.read_bytes()).hexdigest(),
        "task_id": task_id,
        "verification": verification,
    }


def bind_models(yaml_content: str, provider: str, name: str) -> str:
    if not provider or not name:
        raise DeploymentError("Both model provider and model name are required")
    data = yaml.safe_load(yaml_content)
    nodes = data.get("workflow", {}).get("graph", {}).get("nodes", [])
    bound = 0
    for node in nodes:
        node_data = node.get("data", {}) if isinstance(node, dict) else {}
        if node_data.get("type") == "llm":
            model = node_data.setdefault("model", {})
            model["provider"] = provider
            model["name"] = name
            bound += 1
    if not bound:
        raise DeploymentError("DSL contains no LLM nodes to bind")
    rendered = str(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120))
    yaml.safe_load(rendered)
    return rendered


def verify_model_binding(client: DifyClient, provider: str, name: str) -> bool:
    discovery = discover_vision_models(client)
    if discovery["state"] != "VERIFIED":
        raise DeploymentError("Configured vision models could not be verified through Console API")
    return any(
        item.get("provider") == provider
        and item.get("model") == name
        and item.get("provider_status") == "active"
        and item.get("model_status") == "active"
        for item in discovery["models"]
        if isinstance(item, dict)
    )


def sanitize_model_bindings(yaml_content: str) -> str:
    """Clear only LLM provider/name fields using parsed YAML."""

    data = yaml.safe_load(yaml_content)
    if not isinstance(data, dict):
        raise DeploymentError("Exported DSL root is not an object")
    nodes = data.get("workflow", {}).get("graph", {}).get("nodes", [])
    for node in nodes:
        node_data = node.get("data", {}) if isinstance(node, dict) else {}
        if node_data.get("type") == "llm":
            model = node_data.get("model")
            if isinstance(model, dict):
                model["provider"] = ""
                model["name"] = ""
    rendered = str(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120))
    yaml.safe_load(rendered)
    return rendered


def _app_name(yaml_content: str) -> str:
    data = yaml.safe_load(yaml_content)
    name = data.get("app", {}).get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name:
        raise DeploymentError("DSL app name is missing")
    return name


def find_existing_app(client: DifyClient, version: str, app_name: str) -> Optional[str]:
    if version == "1.17.1":
        if not client.settings.workspace_id:
            raise DeploymentError("DIFY_WORKSPACE_ID is required for OpenAPI app discovery")
        path = "/openapi/v1/apps?" + urllib.parse.urlencode(
            {
                "workspace_id": client.settings.workspace_id,
                "page": 1,
                "limit": 100,
                "name": app_name,
            }
        )
        status, body = client.get(path, auth="openapi")
    else:
        path = "/console/api/apps?" + urllib.parse.urlencode(
            {"page": 1, "limit": 100, "mode": "workflow", "name": app_name}
        )
        status, body = client.get(path, auth="console")
    if status != 200 or not isinstance(body, dict):
        raise DeploymentError(f"App discovery failed with HTTP {status}")
    items = body.get("data")
    if not isinstance(items, list):
        raise DeploymentError("App discovery response did not contain a data array")
    exact = [item for item in items if isinstance(item, dict) and item.get("name") == app_name]
    if len(exact) > 1:
        raise DeploymentError("Multiple apps have the deployment name; pass --app-id explicitly")
    if not exact:
        return None
    app_id = exact[0].get("id")
    if not isinstance(app_id, str) or not app_id:
        raise DeploymentError("Discovered app is missing its id")
    return app_id


def _complete_import(
    client: DifyClient, version: str, response: Mapping[str, Any]
) -> Dict[str, Any]:
    import_status = response.get("status")
    result = dict(response)
    if import_status == "pending":
        import_id = response.get("id")
        if not isinstance(import_id, str) or not import_id:
            raise DeploymentError("Pending import response is missing id")
        if version == "1.17.1":
            path = (
                f"/openapi/v1/workspaces/{urllib.parse.quote(client.settings.workspace_id)}"
                f"/apps/imports/{urllib.parse.quote(import_id)}:confirm"
            )
            status, confirmed = client.post(path, {}, auth="openapi")
        else:
            path = f"/console/api/apps/imports/{urllib.parse.quote(import_id)}/confirm"
            status, confirmed = client.post(path, {}, auth="console")
        if status != 200 or not isinstance(confirmed, dict):
            raise DeploymentError(f"DSL import confirmation failed with HTTP {status}")
        result = confirmed
        import_status = result.get("status")
    if import_status == "failed":
        raise DeploymentError(f"DSL import failed: {result.get('error') or 'no server message'}")
    if import_status not in {"completed", "completed-with-warnings"}:
        raise DeploymentError(f"DSL import returned unknown status: {import_status!r}")
    app_id = result.get("app_id")
    if not isinstance(app_id, str) or not app_id:
        raise DeploymentError("Completed DSL import response is missing app_id")
    return result


def check_dependencies(client: DifyClient, version: str, app_id: str) -> Dict[str, Any]:
    if version == "1.17.1":
        path = f"/openapi/v1/apps/{urllib.parse.quote(app_id)}/dependencies:check"
        status, body = client.get(path, auth="openapi")
    else:
        path = f"/console/api/apps/imports/{urllib.parse.quote(app_id)}/check-dependencies"
        status, body = client.get(path, auth="console")
    if status != 200 or not isinstance(body, dict):
        raise DeploymentError(f"Dependency check failed with HTTP {status}")
    leaked = body.get("leaked_dependencies")
    if not isinstance(leaked, list):
        raise DeploymentError("Dependency response is missing leaked_dependencies")
    if leaked:
        raise DeploymentError(f"Workflow has {len(leaked)} unresolved plugin dependencies")
    return body


def import_workflow(
    client: DifyClient,
    dsl_path: Path,
    *,
    app_id: Optional[str] = None,
    model_provider: str = "",
    model_name: str = "",
    plugin_identifier: str = "",
) -> Dict[str, Any]:
    if not dsl_path.is_file():
        raise DeploymentError(f"DSL file not found: {dsl_path}")
    version, _ = require_supported_contract(client)
    yaml_content = dsl_path.read_text(encoding="utf-8")
    if plugin_identifier:
        yaml_content = bind_plugin_dependency(yaml_content, plugin_identifier)
    if bool(model_provider) != bool(model_name):
        raise DeploymentError("Model binding requires both --model-provider and --model-name")
    if model_provider and model_name:
        if not client.settings.console_access_token or not client.settings.csrf_token:
            raise DeploymentError(
                "Console credentials are required to verify an existing vision model binding"
            )
        if not verify_model_binding(client, model_provider, model_name):
            raise DeploymentError(
                "Requested model is not an active, configured vision model in this workspace"
            )
        yaml_content = bind_models(yaml_content, model_provider, model_name)
    deployment_app_id = app_id or find_existing_app(client, version, _app_name(yaml_content))
    action = "update" if deployment_app_id else "create"
    payload: Dict[str, Any] = {"mode": "yaml-content", "yaml_content": yaml_content}
    if deployment_app_id:
        payload["app_id"] = deployment_app_id
    if version == "1.17.1":
        if not client.settings.workspace_id:
            raise DeploymentError("DIFY_WORKSPACE_ID is required for OpenAPI DSL import")
        workspace_id = urllib.parse.quote(client.settings.workspace_id)
        path = f"/openapi/v1/workspaces/{workspace_id}/apps/imports"
        status, body = client.post(path, payload, auth="openapi")
    else:
        status, body = client.post("/console/api/apps/imports", payload, auth="console")
    if status not in {200, 202} or not isinstance(body, dict):
        raise DeploymentError(f"DSL import failed with HTTP {status}")
    result = _complete_import(client, version, body)
    final_app_id = str(result["app_id"])
    check_dependencies(client, version, final_app_id)
    return {
        "version": version,
        "action": action,
        "app_id": final_app_id,
        "import_status": result.get("status"),
        "warnings": result.get("warnings", []),
        "dependencies": "VERIFIED",
        "plugin_identifier": plugin_identifier or expected_plugin_identifier(),
        "model_binding": (
            {"provider": model_provider, "name": model_name}
            if model_provider and model_name
            else "unbound"
        ),
        "model_binding_verified": bool(model_provider and model_name),
    }


def _create_synthetic_test_zip() -> Path:
    fixture_dir = ROOT / "evals" / "generated" / "synthetic_campaign_001"
    if not fixture_dir.exists():
        subprocess.run(
            [sys.executable, str(ROOT / "evals" / "generate_synthetic_fixture.py")], check=True
        )
    out_zip = ROOT / "evals" / "generated" / "synthetic_smoke.zip"
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for image_path in sorted(fixture_dir.rglob("*.png")):
            archive.write(image_path, arcname=str(image_path.relative_to(fixture_dir)))
    return out_zip


def _synthetic_images() -> List[Path]:
    fixture_dir = ROOT / "evals" / "generated" / "synthetic_campaign_001"
    if not fixture_dir.exists():
        subprocess.run(
            [sys.executable, str(ROOT / "evals" / "generate_synthetic_fixture.py")], check=True
        )
    images = sorted(fixture_dir.rglob("*.png"))
    if not images:
        raise DeploymentError("Synthetic fixture generator produced no images")
    return images


def parse_sse_workflow_result(body: Any) -> Dict[str, Any]:
    if isinstance(body, dict):
        data = body.get("data", body)
        if isinstance(data, dict):
            return data
        raise DeploymentError("Workflow response data is not an object")
    if not isinstance(body, str):
        raise DeploymentError("Workflow response is neither JSON nor SSE text")
    finished: Optional[Dict[str, Any]] = None
    for line in body.splitlines():
        if not line.startswith("data:"):
            continue
        payload_text = line[5:].strip()
        if not payload_text:
            continue
        try:
            event = json.loads(payload_text)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("event") in {"error", "workflow_error"}:
            message = event.get("message") or event.get("data")
            raise DeploymentError(f"Workflow SSE error: {message}")
        if event.get("event") == "workflow_finished" and isinstance(event.get("data"), dict):
            finished = event["data"]
    if finished is None:
        raise DeploymentError("Workflow SSE stream did not contain workflow_finished")
    return finished


def assert_workflow_outputs(run_data: Mapping[str, Any]) -> Dict[str, Any]:
    if run_data.get("status") != "succeeded":
        error = str(run_data.get("error") or "no server error").strip()[:1000]
        raise DeploymentError(
            f"Workflow status was {run_data.get('status')!r}, not 'succeeded': {error}"
        )
    outputs = run_data.get("outputs")
    if not isinstance(outputs, dict):
        raise DeploymentError("Workflow outputs are missing")
    report_markdown = outputs.get("report_markdown")
    audit = outputs.get("audit_json")
    if isinstance(audit, str):
        try:
            audit = json.loads(audit)
        except json.JSONDecodeError as exc:
            raise DeploymentError("audit_json is not valid JSON") from exc
    json_files = outputs.get("json_files")
    csv_files = outputs.get("csv_files")
    if not isinstance(report_markdown, str) or not report_markdown.strip():
        raise DeploymentError("report_markdown is empty")
    if not isinstance(audit, dict):
        raise DeploymentError("audit_json is not a structured object")
    if audit.get("review_status") not in REVIEW_STATUSES:
        raise DeploymentError("audit_json review_status is missing or invalid")
    summary = audit.get("campaign_summary")
    buckets = summary.get("scope_buckets") if isinstance(summary, dict) else None
    if not isinstance(buckets, dict) or not SCOPE_BUCKETS.issubset(buckets):
        raise DeploymentError("audit_json scope buckets are missing")
    warnings = audit.get("warnings", [])
    if not isinstance(warnings, list):
        raise DeploymentError("audit_json warnings is not a list")
    if not isinstance(json_files, list) or not json_files:
        raise DeploymentError("json_files does not contain a generated JSON file")
    if not isinstance(csv_files, list) or not csv_files:
        raise DeploymentError("csv_files does not contain a generated CSV file")
    return {
        "workflow_status": "succeeded",
        "report_markdown": "VERIFIED",
        "audit_json": "VERIFIED",
        "review_status": audit["review_status"],
        "scope_buckets": sorted(buckets),
        "warning_count": len(warnings),
        "json_export": "VERIFIED",
        "csv_export": "VERIFIED",
    }


def _file_type(path: Path) -> str:
    image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
    return "image" if path.suffix.lower() in image_extensions else "custom"


def smoke_test(
    client: DifyClient, app_id: str, files: Sequence[Path], *, mode: str = "draft"
) -> Dict[str, Any]:
    version, _ = require_supported_contract(client)
    if not files:
        raise DeploymentError("At least one smoke-test file is required")
    uploaded = []
    for file_path in files:
        if not file_path.is_file():
            raise DeploymentError(f"Smoke-test file not found: {file_path}")
        if mode == "published":
            if version != "1.17.1":
                raise DeploymentError("Published OpenAPI smoke tests require Dify 1.17.1")
            path = f"/openapi/v1/apps/{urllib.parse.quote(app_id)}/files"
            auth = "openapi"
        else:
            path = "/console/api/files/upload"
            auth = "console"
        upload_status, response = client.upload_file(path, file_path, form_field="file", auth=auth)
        if upload_status not in {200, 201} or not isinstance(response, dict):
            raise DeploymentError(f"File upload failed with HTTP {upload_status}")
        file_id = response.get("id")
        if not isinstance(file_id, str) or not file_id:
            raise DeploymentError("File upload response is missing id")
        uploaded.append(
            {
                "type": _file_type(file_path),
                "transfer_method": "local_file",
                "upload_file_id": file_id,
            }
        )
    payload: Dict[str, Any] = {
        "inputs": {
            "files": uploaded,
            "optional_instruction": "Synthetic runtime verification",
        }
    }
    if mode == "published":
        path = f"/openapi/v1/apps/{urllib.parse.quote(app_id)}:run"
        auth = "openapi"
    else:
        path = f"/console/api/apps/{urllib.parse.quote(app_id)}/workflows/draft/run"
        auth = "console"
        payload["files"] = []
    status, body = client.post(path, payload, auth=auth)
    if status != 200:
        raise DeploymentError(f"Workflow run failed with HTTP {status}")
    result = assert_workflow_outputs(parse_sse_workflow_result(body))
    result.update(
        mode=mode,
        file_count=len(files),
        input_kind="zip" if len(files) == 1 and files[0].suffix.lower() == ".zip" else "direct",
    )
    return result


def verify_deterministic_parity(
    client: DifyClient, app_id: str, run_id: Optional[str] = None
) -> Dict[str, Any]:
    from social_report.metrics import audit_campaign

    if not client.settings.console_access_token or not client.settings.csrf_token:
        raise DeploymentError("Console authentication is required to verify live parity")

    target_run_id = run_id
    if not target_run_id:
        status, runs_data = client.get(
            f"/console/api/apps/{urllib.parse.quote(app_id)}/workflow-runs?limit=10",
            auth="console",
        )
        if status != 200 or not isinstance(runs_data, dict):
            raise DeploymentError(f"Failed to fetch workflow runs with HTTP {status}")
        runs = [
            r
            for r in runs_data.get("data", [])
            if isinstance(r, dict) and r.get("status") == "succeeded"
        ]
        if not runs:
            raise DeploymentError("No successful workflow runs found for parity verification")
        target_run_id = runs[0].get("id")
        if not isinstance(target_run_id, str) or not target_run_id:
            raise DeploymentError("Workflow run missing id")

    status, ne_data = client.get(
        f"/console/api/apps/{urllib.parse.quote(app_id)}/workflow-runs/{urllib.parse.quote(target_run_id)}/node-executions",
        auth="console",
    )
    if status != 200 or not isinstance(ne_data, dict):
        raise DeploymentError(f"Failed to fetch node executions for run {target_run_id}")

    audit_nodes = [
        ne
        for ne in ne_data.get("data", [])
        if isinstance(ne, dict)
        and "audit" in str(ne.get("title", "")).lower()
        and isinstance(ne.get("inputs"), dict)
        and "campaign_json" in ne["inputs"]
    ]
    if not audit_nodes:
        raise DeploymentError(f"No audit node execution found in run {target_run_id}")

    node = audit_nodes[0]
    campaign_input = node["inputs"]["campaign_json"]
    live_audit = node.get("outputs", {}).get("audit")
    if not isinstance(live_audit, dict):
        raw_json = node.get("outputs", {}).get("audit_json")
        if isinstance(raw_json, str):
            live_audit = json.loads(raw_json)
        else:
            raise DeploymentError(f"Audit outputs missing in node execution {node.get('id')}")

    local_audit = audit_campaign(campaign_input)

    diffs: List[str] = []
    verified_fields: List[str] = []

    for field in ("review_status", "warnings"):
        if local_audit.get(field) != live_audit.get(field):
            diffs.append(
                f"{field}: local={local_audit.get(field)!r} != live={live_audit.get(field)!r}"
            )
        else:
            verified_fields.append(field)

    local_summary = local_audit.get("campaign_summary", {})
    live_summary = live_audit.get("campaign_summary", {})
    summary_fields = (
        "scope",
        "asset_count",
        "total_views",
        "total_likes",
        "total_comments",
        "total_shares",
        "total_saves",
        "sum_of_content_reach",
        "total_known_engagement_actions",
        "total_platform_reported_interactions",
        "weighted_calculated_er_by_reach",
        "weighted_er_lower_bound_by_reach",
        "er_is_complete",
        "er_status",
        "interaction_discrepancy_value",
        "total_uncategorized_interactions",
        "sum_of_content_reach_is_approximate",
        "total_known_engagement_actions_is_approximate",
        "weighted_er_is_approximate",
        "overall_save_rate_is_approximate",
        "overall_comment_to_like_ratio_is_approximate",
    )
    for field in summary_fields:
        if local_summary.get(field) != live_summary.get(field):
            diffs.append(
                f"campaign_summary.{field}: "
                f"local={local_summary.get(field)!r} != live={live_summary.get(field)!r}"
            )
        else:
            verified_fields.append(f"campaign_summary.{field}")

    local_buckets = local_summary.get("scope_buckets", {})
    live_buckets = live_summary.get("scope_buckets", {})
    for bucket_name in ("organic", "paid", "mixed_or_unknown", "unknown"):
        loc_b = local_buckets.get(bucket_name, {})
        liv_b = live_buckets.get(bucket_name, {})
        for field in (
            "scope",
            "asset_count",
            "total_views",
            "total_likes",
            "total_comments",
            "total_shares",
            "total_saves",
            "sum_of_content_reach",
            "total_known_engagement_actions",
            "weighted_er_lower_bound_by_reach",
            "er_status",
        ):
            if loc_b.get(field) != liv_b.get(field):
                diffs.append(
                    f"scope_buckets[{bucket_name}].{field}: "
                    f"local={loc_b.get(field)!r} != live={liv_b.get(field)!r}"
                )
            else:
                verified_fields.append(f"scope_buckets[{bucket_name}].{field}")

    local_assets = {
        a.get("asset_group_id"): a for a in local_audit.get("assets", []) if isinstance(a, dict)
    }
    live_assets = {
        a.get("asset_group_id"): a for a in live_audit.get("assets", []) if isinstance(a, dict)
    }
    if set(local_assets.keys()) != set(live_assets.keys()):
        diffs.append(
            f"asset_group_ids mismatch: "
            f"local={sorted(local_assets.keys())} != live={sorted(live_assets.keys())}"
        )
    else:
        for aid, loc_a in local_assets.items():
            liv_a = live_assets[aid]
            for field in (
                "platform",
                "content_format",
                "scope",
                "review_status",
                "known_engagement_actions",
                "calculated_er_by_reach",
                "er_lower_bound_by_reach",
                "interaction_discrepancy_value",
            ):
                if loc_a.get(field) != liv_a.get(field):
                    diffs.append(
                        f"asset[{aid}].{field}: "
                        f"local={loc_a.get(field)!r} != live={liv_a.get(field)!r}"
                    )
                else:
                    verified_fields.append(f"asset[{aid}].{field}")

    if diffs:
        raise DeploymentError(
            f"Deterministic parity failed with {len(diffs)} diffs: {'; '.join(diffs[:5])}"
        )

    return {
        "status": "PASS",
        "run_id": target_run_id,
        "verified_fields_count": len(verified_fields),
        "diffs_count": 0,
    }


def _dsl_structure(yaml_content: str) -> Dict[str, Any]:
    data = yaml.safe_load(yaml_content)
    nodes = data.get("workflow", {}).get("graph", {}).get("nodes", [])
    edges = data.get("workflow", {}).get("graph", {}).get("edges", [])
    return {
        "kind": data.get("kind"),
        "mode": data.get("app", {}).get("mode"),
        "node_types": sorted(
            (str(node.get("id")), str(node.get("data", {}).get("type"))) for node in nodes
        ),
        "tools": sorted(
            str(node.get("data", {}).get("tool_name"))
            for node in nodes
            if node.get("data", {}).get("type") == "tool"
        ),
        "edges": sorted((str(edge.get("source")), str(edge.get("target"))) for edge in edges),
    }


def _validate_portable_dsl(yaml_content: str) -> None:
    from scripts.validate_dify_dsl import validate

    with tempfile.TemporaryDirectory(prefix="social-report-dsl-") as tmp:
        candidate = Path(tmp) / "social-media-report.yml"
        candidate.write_text(yaml_content, encoding="utf-8")
        validate(candidate)


def export_workflow(
    client: DifyClient,
    app_id: str,
    output_path: Path,
    *,
    sanitize: bool = True,
) -> Dict[str, Any]:
    version, _ = require_supported_contract(client)
    if version == "1.17.1":
        path = f"/openapi/v1/apps/{urllib.parse.quote(app_id)}/dsl?include_secret=false"
        status, response = client.get(path, auth="openapi")
    else:
        path = f"/console/api/apps/{urllib.parse.quote(app_id)}/export?include_secret=false"
        status, response = client.get(path, auth="console")
    if status != 200 or not isinstance(response, dict) or not isinstance(response.get("data"), str):
        raise DeploymentError(f"Workflow export failed with HTTP {status}")
    exported = response["data"]
    if sanitize:
        exported = sanitize_model_bindings(exported)
    yaml.safe_load(exported)
    if sanitize:
        _validate_portable_dsl(exported)
    structure_matches = _dsl_structure(exported) == _dsl_structure(
        DEFAULT_DSL.read_text(encoding="utf-8")
    )
    if not structure_matches:
        raise DeploymentError("Exported workflow structure differs from the repository DSL")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(exported, encoding="utf-8")
    return {
        "output": str(output_path),
        "include_secret": False,
        "model_bindings_sanitized": sanitize,
        "structure_matches_repository": True,
    }


def cmd_discover(client: DifyClient) -> int:
    report = discover_server(client)
    print(json.dumps(report, indent=2))
    return 0 if report.get("version_state") == "VERIFIED" else 1


def cmd_plugin_status(client: DifyClient, plugin_identifier: str = "") -> int:
    result = verify_plugin(client, plugin_identifier or None)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


def _print_result(result: Mapping[str, Any]) -> None:
    print(json.dumps(dict(result), indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dify deployment and verification helper")
    parser.add_argument("--env-file", type=Path, default=None, help="Explicit local dotenv file")
    parser.add_argument("--base-url", default=None, help="Override DIFY_BASE_URL")
    parser.add_argument("--workspace-id", default=None, help="Override DIFY_WORKSPACE_ID")
    parser.add_argument("--openapi-token", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--console-access-token", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--csrf-token", default=None, help=argparse.SUPPRESS)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("discover", help="Discover exact Dify version and capability states")
    plugin_status = commands.add_parser(
        "plugin-status", help="Verify plugin identity, provider, and six tools"
    )
    plugin_status.add_argument("--plugin-identifier", default="")
    install = commands.add_parser("install-plugin", help="Upload and install the local plugin")
    install.add_argument("package", nargs="?", type=Path, default=DEFAULT_PLUGIN_PKG)
    install.add_argument("--timeout", type=float, default=120.0)
    install.add_argument(
        "--replace-installed",
        action="store_true",
        help="Replace another installed build of the same plugin id",
    )
    import_parser = commands.add_parser("import-workflow", help="Create or update workflow draft")
    import_parser.add_argument("dsl", nargs="?", type=Path, default=DEFAULT_DSL)
    import_parser.add_argument("--app-id", default=None)
    import_parser.add_argument("--model-provider", default=None)
    import_parser.add_argument("--model-name", default=None)
    import_parser.add_argument("--plugin-identifier", default="")
    smoke = commands.add_parser("smoke-test", help="Run a draft or published synthetic E2E")
    smoke.add_argument("app_id")
    smoke.add_argument("--file", action="append", type=Path, default=[])
    smoke.add_argument("--synthetic", choices=("direct", "zip"), default=None)
    smoke.add_argument("--mode", choices=("draft", "published"), default="draft")
    export = commands.add_parser(
        "export-workflow", help="Export without secrets and verify structure"
    )
    export.add_argument("app_id")
    export.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=ROOT / "dist" / "social-media-report.live-export.yml",
    )
    export.add_argument("--keep-model-bindings", action="store_true")
    live = commands.add_parser("verify-live", help="Opt-in live dependency and E2E verification")
    live.add_argument("app_id")
    live.add_argument("--synthetic", choices=("direct", "zip"), default="zip")
    live.add_argument("--mode", choices=("draft", "published"), default="draft")
    live.add_argument("--confirm-live", action="store_true")
    live.add_argument("--plugin-identifier", default="")
    parity = commands.add_parser(
        "verify-parity", help="Compare deterministic fields between local core and live Dify audit"
    )
    parity.add_argument("app_id")
    parity.add_argument(
        "--run-id", default=None, help="Workflow run ID to verify (defaults to latest succeeded)"
    )
    parity.add_argument("--confirm-live", action="store_true")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        settings = resolve_settings(
            env_file=args.env_file,
            cli_values={
                "DIFY_BASE_URL": args.base_url,
                "DIFY_WORKSPACE_ID": args.workspace_id,
                "DIFY_OPENAPI_TOKEN": args.openapi_token,
                "DIFY_CONSOLE_ACCESS_TOKEN": args.console_access_token,
                "DIFY_CSRF_TOKEN": args.csrf_token,
            },
        )
        client = DifyClient(settings)
        if args.command == "discover":
            return cmd_discover(client)
        if args.command == "plugin-status":
            return cmd_plugin_status(client, args.plugin_identifier)
        if args.command == "install-plugin":
            _print_result(
                install_plugin(
                    client,
                    args.package,
                    timeout=args.timeout,
                    replace_installed=args.replace_installed,
                )
            )
            return 0
        if args.command == "import-workflow":
            _print_result(
                import_workflow(
                    client,
                    args.dsl,
                    app_id=args.app_id,
                    model_provider=args.model_provider or settings.model_provider,
                    model_name=args.model_name or settings.model_name,
                    plugin_identifier=args.plugin_identifier,
                )
            )
            return 0
        if args.command == "smoke-test":
            files = list(args.file)
            if args.synthetic == "zip":
                files = [_create_synthetic_test_zip()]
            elif args.synthetic == "direct":
                files = _synthetic_images()
            _print_result(smoke_test(client, args.app_id, files, mode=args.mode))
            return 0
        if args.command == "export-workflow":
            _print_result(
                export_workflow(
                    client,
                    args.app_id,
                    args.output,
                    sanitize=not args.keep_model_bindings,
                )
            )
            return 0
        if args.command == "verify-live":
            if not args.confirm_live and os.environ.get("DIFY_LIVE_TEST") != "1":
                raise DeploymentError(
                    "Live verification is opt-in; set DIFY_LIVE_TEST=1 or pass --confirm-live"
                )
            version, discovery = require_supported_contract(client)
            plugin = verify_plugin(client, args.plugin_identifier or None)
            if plugin["status"] != "PASS":
                raise DeploymentError(f"Plugin verification was {plugin['status']}")
            check_dependencies(client, version, args.app_id)
            files = (
                [_create_synthetic_test_zip()] if args.synthetic == "zip" else _synthetic_images()
            )
            run = smoke_test(client, args.app_id, files, mode=args.mode)
            _print_result(
                {
                    "discovery": discovery,
                    "plugin": plugin,
                    "dependencies": "VERIFIED",
                    "run": run,
                }
            )
            return 0
        if args.command == "verify-parity":
            if not args.confirm_live and os.environ.get("DIFY_LIVE_TEST") != "1":
                raise DeploymentError(
                    "Live parity verification is opt-in; "
                    "set DIFY_LIVE_TEST=1 or pass --confirm-live"
                )
            _print_result(verify_deterministic_parity(client, args.app_id, args.run_id))
            return 0
        raise DeploymentError(f"Unknown command: {args.command}")
    except DeploymentError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
