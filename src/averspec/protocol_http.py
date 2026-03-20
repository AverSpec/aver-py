"""HTTP protocol for AverSpec — sends requests via httpx."""

from __future__ import annotations

import sys
import time
from typing import Any

from averspec.protocol import Protocol


class HttpContext:
    """HTTP client context wrapping an httpx.Client."""

    def __init__(self, client: Any, base_url: str, debug: bool = False):
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._debug = debug

    def _request(self, method: str, path: str, body: Any = None) -> Any:
        url = f"{self._base_url}{path}"
        headers = {}
        kwargs: dict[str, Any] = {}

        if body is not None:
            headers["Content-Type"] = "application/json"
            kwargs["json"] = body

        start = time.perf_counter()
        response = self._client.request(method, url, headers=headers, **kwargs)
        elapsed = time.perf_counter() - start

        if self._debug:
            print(
                f"[aver-http] {method} {path} -> {response.status_code} ({elapsed * 1000:.1f}ms)",
                file=sys.stderr,
            )

        return response

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, body: Any = None) -> Any:
        return self._request("POST", path, body)

    def put(self, path: str, body: Any = None) -> Any:
        return self._request("PUT", path, body)

    def patch(self, path: str, body: Any = None) -> Any:
        return self._request("PATCH", path, body)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)


class HttpProtocol(Protocol):
    """HTTP protocol: creates an httpx-backed HttpContext per test."""

    name = "http"

    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        default_headers: dict | None = None,
        debug: bool = False,
    ):
        self._base_url = base_url
        self._timeout = timeout
        self._default_headers = default_headers or {}
        self._debug = debug

    def setup(self) -> HttpContext:
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for the HTTP protocol. "
                "Install it with: pip install averspec[http]"
            )

        client = httpx.Client(
            timeout=self._timeout,
            headers=self._default_headers,
        )
        return HttpContext(client, self._base_url, debug=self._debug)

    def teardown(self, ctx: HttpContext) -> None:
        ctx._client.close()


def http(
    base_url: str,
    *,
    timeout: float = 30.0,
    default_headers: dict | None = None,
    debug: bool = False,
) -> HttpProtocol:
    """Create an HTTP protocol targeting the given base URL."""
    return HttpProtocol(
        base_url,
        timeout=timeout,
        default_headers=default_headers,
        debug=debug,
    )
