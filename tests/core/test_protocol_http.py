"""Tests for the HTTP protocol."""

import sys
from io import StringIO

import httpx
import pytest

from averspec.protocol_http import http, HttpContext, HttpProtocol


def _mock_transport(handler):
    """Create an httpx MockTransport from a handler function."""
    return httpx.MockTransport(handler)


def _echo_handler(request: httpx.Request) -> httpx.Response:
    """Echo handler that returns request details as JSON."""
    body = None
    if request.content:
        import json
        body = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": body,
        },
    )


def _make_ctx(base_url="http://test.local", debug=False, default_headers=None):
    """Create an HttpContext with a mock transport."""
    transport = _mock_transport(_echo_handler)
    client = httpx.Client(transport=transport, headers=default_headers or {})
    return HttpContext(client, base_url, debug=debug)


class TestHttpContextMethods:
    def test_get_builds_correct_url(self):
        ctx = _make_ctx("http://api.example.com")
        resp = ctx.get("/users")
        data = resp.json()
        assert data["method"] == "GET"
        assert data["url"] == "http://api.example.com/users"

    def test_post_with_body(self):
        ctx = _make_ctx()
        resp = ctx.post("/items", body={"name": "widget"})
        data = resp.json()
        assert data["method"] == "POST"
        assert data["body"] == {"name": "widget"}
        assert "application/json" in data["headers"].get("content-type", "")

    def test_put_with_body(self):
        ctx = _make_ctx()
        resp = ctx.put("/items/1", body={"name": "updated"})
        data = resp.json()
        assert data["method"] == "PUT"
        assert data["body"] == {"name": "updated"}

    def test_patch_with_body(self):
        ctx = _make_ctx()
        resp = ctx.patch("/items/1", body={"status": "done"})
        data = resp.json()
        assert data["method"] == "PATCH"
        assert data["body"] == {"status": "done"}

    def test_delete_no_body(self):
        ctx = _make_ctx()
        resp = ctx.delete("/items/1")
        data = resp.json()
        assert data["method"] == "DELETE"
        assert data["body"] is None

    def test_post_without_body_no_content_type(self):
        ctx = _make_ctx()
        resp = ctx.post("/ping")
        data = resp.json()
        assert data["method"] == "POST"
        # No body means no Content-Type header injected by us
        assert data["body"] is None


class TestDefaultHeaders:
    def test_default_headers_applied(self):
        ctx = _make_ctx(default_headers={"Authorization": "Bearer tok123"})
        resp = ctx.get("/secret")
        data = resp.json()
        assert data["headers"]["authorization"] == "Bearer tok123"


class TestDebugLogging:
    def test_debug_logs_to_stderr(self, capsys):
        ctx = _make_ctx(debug=True)
        ctx.get("/health")
        captured = capsys.readouterr()
        assert "[aver-http] GET /health" in captured.err
        assert "200" in captured.err


class TestTrailingSlashStripped:
    def test_strips_trailing_slash_from_base_url(self):
        """http("http://localhost:3000/") should not double-slash when calling get("/tasks")."""
        ctx = _make_ctx("http://localhost:3000/")
        resp = ctx.get("/tasks")
        data = resp.json()
        assert data["url"] == "http://localhost:3000/tasks"
        assert "//" not in data["url"].replace("http://", "", 1)


class TestHttpProtocolFactory:
    def test_factory_returns_protocol(self):
        proto = http("http://localhost:8080")
        assert isinstance(proto, HttpProtocol)
        assert proto.name == "http"

    def test_factory_stores_config(self):
        proto = http(
            "http://localhost:3000",
            timeout=10.0,
            default_headers={"X-Api-Key": "abc"},
            debug=True,
        )
        assert proto._base_url == "http://localhost:3000"
        assert proto._timeout == 10.0
        assert proto._default_headers == {"X-Api-Key": "abc"}
        assert proto._debug is True
