"""Minimal, injectable, read-only Meta Graph API client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Iterator, Mapping, MutableMapping, Optional, Protocol, cast

from .auth import MetaConfig
from .usage import UsageTracker

SENSITIVE_QUERY_KEYS = {
    "access_token",
    "appsecret_proof",
    "client_secret",
    "fb_exchange_token",
    "input_token",
}


@dataclass(frozen=True)
class HTTPResponse:
    status: int
    headers: Mapping[str, str]
    body: bytes


class Transport(Protocol):
    def __call__(self, url: str, timeout: float, user_agent: str) -> HTTPResponse: ...


class ErrorCategory(str, Enum):
    TRANSPORT = "TRANSPORT"
    SERVER_TRANSIENT = "SERVER_TRANSIENT"
    RATE_LIMIT = "RATE_LIMIT"
    AUTH = "AUTH"
    PERMISSION = "PERMISSION"
    INVALID_REQUEST = "INVALID_REQUEST"
    OTHER = "OTHER"


RATE_LIMIT_CODES = {
    4,
    17,
    32,
    341,
    613,
    80000,
    80001,
    80002,
    80003,
    80004,
    80005,
    80006,
    80008,
    80009,
    80014,
}


def redact_url(url: str) -> str:
    """Redact credential-like query values while retaining diagnostic structure."""

    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    safe_query = [
        (key, "[REDACTED]" if key.lower() in SENSITIVE_QUERY_KEYS else value)
        for key, value in query
    ]
    return urllib.parse.urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(safe_query), "")
    )


def redact_text(value: str, secrets: tuple[Optional[str], ...]) -> str:
    redacted = value
    for secret in secrets:
        if secret:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted


class MetaAPIError(RuntimeError):
    """Structured Meta error that never includes credentials or raw response bodies."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 0,
        code: Optional[int] = None,
        subcode: Optional[int] = None,
        error_type: Optional[str] = None,
        retryable: bool = False,
        category: ErrorCategory = ErrorCategory.OTHER,
        retry_after_seconds: Optional[float] = None,
        estimated_regain_seconds: Optional[int] = None,
        request_url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.subcode = subcode
        self.error_type = error_type
        self.retryable = retryable
        self.category = category
        self.retry_after_seconds = retry_after_seconds
        self.estimated_regain_seconds = estimated_regain_seconds
        self.request_url = redact_url(request_url) if request_url else None

    def as_dict(self) -> Mapping[str, object]:
        return {
            "message": str(self),
            "status": self.status,
            "code": self.code,
            "subcode": self.subcode,
            "type": self.error_type,
            "retryable": self.retryable,
            "category": self.category.value,
            "retry_after_seconds": self.retry_after_seconds,
            "estimated_regain_seconds": self.estimated_regain_seconds,
            "request_url": self.request_url,
        }


def _urllib_transport(url: str, timeout: float, user_agent: str) -> HTTPResponse:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HTTPResponse(
                status=response.status,
                headers=dict(response.headers.items()),
                body=response.read(),
            )
    except urllib.error.HTTPError as exc:
        return HTTPResponse(
            status=exc.code,
            headers=dict(exc.headers.items()) if exc.headers else {},
            body=exc.read(),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise MetaAPIError(
            "Meta API transport failed",
            retryable=True,
            category=ErrorCategory.TRANSPORT,
            request_url=url,
        ) from exc


def _clean_payload(value: Any) -> Any:
    """Remove credential-bearing paging URLs from data returned to callers."""

    if isinstance(value, list):
        return [_clean_payload(item) for item in value]
    if not isinstance(value, dict):
        return value
    cleaned: Dict[str, Any] = {}
    for key, item in value.items():
        if key in {"next", "previous"} and isinstance(item, str):
            continue
        cleaned[key] = _clean_payload(item)
    return cleaned


class MetaClient:
    """GET-only Graph API client with bounded retries and cursor pagination."""

    def __init__(
        self,
        config: MetaConfig,
        *,
        transport: Optional[Transport] = None,
        sleep: Callable[[float], None] = time.sleep,
        base_url: str = "https://graph.facebook.com",
    ) -> None:
        self.config = config
        self.transport = transport or _urllib_transport
        self.sleep = sleep
        self.base_url = base_url.rstrip("/")
        self.user_agent = "social-media-report-automation/2.0 (+read-only-meta-adapter)"
        self.usage = UsageTracker()

    @property
    def quota_summary(self) -> Mapping[str, object]:
        return self.usage.summary()

    def _url(
        self,
        path: str,
        params: Optional[Mapping[str, object]],
        *,
        inject_credentials: bool = True,
    ) -> str:
        safe_path = path.strip("/")
        version_prefix = f"{self.config.graph_version}/"
        if safe_path.startswith(version_prefix):
            route = safe_path
        else:
            route = f"{self.config.graph_version}/{safe_path}"
        query: MutableMapping[str, object] = dict(params or {})
        if inject_credentials:
            query["access_token"] = self.config.access_token
            proof = self.config.appsecret_proof
            if proof:
                query["appsecret_proof"] = proof
        encoded: Dict[str, str] = {}
        for key, value in query.items():
            encoded[key] = (
                json.dumps(value, separators=(",", ":"))
                if isinstance(value, (dict, list))
                else str(value)
            )
        return f"{self.base_url}/{route}?{urllib.parse.urlencode(encoded)}"

    @staticmethod
    def _retry_delay(response: HTTPResponse, attempt: int) -> float:
        raw = next(
            (value for key, value in response.headers.items() if key.lower() == "retry-after"),
            "",
        )
        try:
            return min(max(float(raw), 0.0), 60.0) if raw else min(2.0**attempt, 30.0)
        except ValueError:
            return min(2.0**attempt, 30.0)

    @staticmethod
    def _retry_after(response: HTTPResponse) -> Optional[float]:
        raw = next(
            (value for key, value in response.headers.items() if key.lower() == "retry-after"),
            None,
        )
        try:
            return max(float(raw), 0.0) if raw is not None else None
        except ValueError:
            return None

    @staticmethod
    def _category(status: int, code: Optional[int]) -> ErrorCategory:
        if status == 429 or code in RATE_LIMIT_CODES:
            return ErrorCategory.RATE_LIMIT
        if status >= 500 or code in {1, 2}:
            return ErrorCategory.SERVER_TRANSIENT
        if status == 401 or code in {102, 190}:
            return ErrorCategory.AUTH
        if status == 403 or code in {3, 10, 368} or (code is not None and 200 <= code <= 299):
            return ErrorCategory.PERMISSION
        if code == 100 or status in {400, 404, 405, 422}:
            return ErrorCategory.INVALID_REQUEST
        return ErrorCategory.OTHER

    def _error(self, response: HTTPResponse, url: str) -> MetaAPIError:
        error: Mapping[str, object] = {}
        try:
            payload = json.loads(response.body.decode("utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                error = payload["error"]
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        message = error.get("message")
        safe_message = redact_text(
            str(message) if isinstance(message, str) else "Meta API request failed",
            (self.config.access_token, self.config.app_secret),
        )
        code = error.get("code")
        subcode = error.get("error_subcode")
        parsed_code = code if isinstance(code, int) else None
        category = self._category(response.status, parsed_code)
        retryable = category is ErrorCategory.SERVER_TRANSIENT
        quota = self.quota_summary
        regain = quota.get("estimated_regain_seconds")
        return MetaAPIError(
            safe_message,
            status=response.status,
            code=parsed_code,
            subcode=subcode if isinstance(subcode, int) else None,
            error_type=str(error.get("type")) if error.get("type") else None,
            retryable=retryable,
            category=category,
            retry_after_seconds=self._retry_after(response),
            estimated_regain_seconds=regain if isinstance(regain, int) else None,
            request_url=url,
        )

    def _get_url(self, url: str) -> Mapping[str, Any]:
        last_transport_error: Optional[MetaAPIError] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                response = self.transport(url, self.config.timeout_seconds, self.user_agent)
            except MetaAPIError as exc:
                last_transport_error = exc
                if attempt >= self.config.max_retries or not exc.retryable:
                    raise
                self.sleep(min(2.0**attempt, 30.0))
                continue
            self.usage.observe(response.headers)
            if 200 <= response.status < 300:
                try:
                    payload = json.loads(response.body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise MetaAPIError(
                        "Meta API returned invalid JSON",
                        status=response.status,
                        request_url=url,
                    ) from exc
                if not isinstance(payload, dict):
                    raise MetaAPIError(
                        "Meta API returned an unexpected payload",
                        status=response.status,
                        request_url=url,
                    )
                return cast(Mapping[str, Any], _clean_payload(payload))
            error = self._error(response, url)
            if error.category is ErrorCategory.RATE_LIMIT:
                self.usage.mark_blocked()
            if attempt >= self.config.max_retries or not error.retryable:
                raise error
            self.sleep(self._retry_delay(response, attempt))
        if last_transport_error:
            raise last_transport_error
        raise MetaAPIError("Meta API request failed", request_url=url)

    def get(self, path: str, params: Optional[Mapping[str, object]] = None) -> Mapping[str, Any]:
        return self._get_url(self._url(path, params))

    def get_without_auth(self, path: str, params: Mapping[str, object]) -> Mapping[str, Any]:
        """Call auth bootstrap endpoints whose credentials are already explicit params."""

        return self._get_url(self._url(path, params, inject_credentials=False))

    def paginate(
        self,
        path: str,
        params: Optional[Mapping[str, object]] = None,
        *,
        max_pages: int = 100,
    ) -> Iterator[Mapping[str, Any]]:
        """Yield data items using cursors; credential-bearing next URLs are discarded."""

        query: Dict[str, object] = dict(params or {})
        seen: set[str] = set()
        for _ in range(max_pages):
            payload = self.get(path, query)
            data = payload.get("data", [])
            if not isinstance(data, list):
                raise MetaAPIError("Meta API page data is not a list")
            for item in data:
                if isinstance(item, dict):
                    yield item
            paging = payload.get("paging")
            cursors = paging.get("cursors") if isinstance(paging, dict) else None
            after = cursors.get("after") if isinstance(cursors, dict) else None
            if not isinstance(after, str) or not after or after in seen:
                return
            seen.add(after)
            query["after"] = after
        raise MetaAPIError("Meta API pagination exceeded the configured page limit")
