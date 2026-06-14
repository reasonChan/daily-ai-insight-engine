"""Small HTTP helpers for collector modules.

The collector layer should not raise on transient network problems. These
helpers return structured dictionaries so callers can convert failures into
collection errors and keep the rest of a run alive.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_USER_AGENT = (
    "DailyAIInsightEngine/0.1 "
    "(collector; https://example.local/daily-ai-insight-engine)"
)


def _with_params(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url

    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{urlencode(params)}"


def fetch_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch a URL as text and return either an ok result or structured error."""

    request_url = _with_params(url, params)
    request_headers = {"User-Agent": DEFAULT_USER_AGENT, **(headers or {})}
    request = Request(request_url, headers=request_headers)

    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return {
                "ok": True,
                "url": response.geturl(),
                "status_code": response.status,
                "headers": dict(response.headers.items()),
                "text": body.decode(encoding, errors="replace"),
            }
    except HTTPError as exc:
        return {
            "ok": False,
            "url": request_url,
            "status_code": exc.code,
            "error": {
                "type": "http_error",
                "message": str(exc),
            },
        }
    except URLError as exc:
        return {
            "ok": False,
            "url": request_url,
            "error": {
                "type": "network_error",
                "message": str(exc.reason),
            },
        }
    except TimeoutError as exc:
        return {
            "ok": False,
            "url": request_url,
            "error": {
                "type": "timeout",
                "message": str(exc),
            },
        }
    except Exception as exc:  # pragma: no cover - defensive collector boundary.
        return {
            "ok": False,
            "url": request_url,
            "error": {
                "type": exc.__class__.__name__,
                "message": str(exc),
            },
        }


def fetch_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch and decode a JSON URL without throwing into collector code."""

    result = fetch_text(url, params=params, headers=headers, timeout=timeout)
    if not result.get("ok"):
        return result

    try:
        result["json"] = json.loads(result.get("text") or "")
        result.pop("text", None)
        return result
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "url": result.get("url", url),
            "status_code": result.get("status_code"),
            "error": {
                "type": "json_decode_error",
                "message": str(exc),
            },
        }


class HttpClient:
    """Compatibility HTTP client used by class-based collectors."""

    def __init__(
        self,
        *,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        headers: dict[str, str] | None = None,
    ):
        self.timeout = timeout
        self.headers = headers or {}

    def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        result = fetch_text(url, params=params, headers=self.headers, timeout=self.timeout)
        if result.get("ok"):
            return str(result.get("text") or "")
        error = result.get("error") or {}
        raise RuntimeError(error.get("message") or f"HTTP request failed: {url}")

    def get_json(self, url: str, *, params: dict[str, Any] | None = None) -> Any:
        result = fetch_json(url, params=params, headers=self.headers, timeout=self.timeout)
        if result.get("ok"):
            return result.get("json")
        error = result.get("error") or {}
        raise RuntimeError(error.get("message") or f"HTTP JSON request failed: {url}")
