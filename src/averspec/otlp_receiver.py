"""Lightweight OTLP HTTP receiver for test-time span collection."""

from __future__ import annotations

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any

from averspec.protocol import TelemetryCollector
from averspec.telemetry_types import CollectedSpan, SpanLink

DEFAULT_MAX_SPANS = 10_000


class _OtlpHandler(BaseHTTPRequestHandler):
    """HTTP handler for OTLP /v1/traces endpoint."""

    def log_message(self, format, *args):
        # Suppress default request logging
        pass

    def do_POST(self):
        if self.path != "/v1/traces":
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": f"Unsupported path: POST {self.path}"
            }).encode())
            return

        content_type = self.headers.get("Content-Type", "")

        # Reject protobuf / grpc
        if "application/x-protobuf" in content_type or "application/grpc" in content_type:
            self.send_response(415)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "error": (
                    f'Unsupported content-type "{content_type}". '
                    "The Aver OTLP receiver only accepts JSON. "
                    "Configure your exporter to use OTLP/HTTP JSON (application/json)."
                )
            }).encode())
            return

        # Read body
        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length)

        try:
            body = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Invalid JSON body"}).encode())
            return

        # Parse spans
        receiver: OtlpReceiver = self.server._otlp_receiver  # type: ignore[attr-defined]
        receiver._ingest(body)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")


class OtlpReceiver(TelemetryCollector):
    """OTLP HTTP JSON receiver implementing TelemetryCollector."""

    def __init__(self, max_spans: int = DEFAULT_MAX_SPANS):
        self._max_spans = max_spans
        self._spans: list[CollectedSpan] = []
        self._lock = threading.Lock()
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port: int = 0
        self._limit_warned = False

    @property
    def port(self) -> int:
        return self._port

    def get_spans(self) -> list[CollectedSpan]:
        with self._lock:
            return list(self._spans)

    def reset(self) -> None:
        with self._lock:
            self._spans.clear()
            self._limit_warned = False

    def _ingest(self, body: dict[str, Any]) -> None:
        """Parse OTLP JSON body and collect spans."""
        with self._lock:
            for rs in body.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    for span in ss.get("spans", []):
                        if len(self._spans) >= self._max_spans:
                            if not self._limit_warned:
                                self._limit_warned = True
                            return

                        parent_span_id = span.get("parentSpanId")
                        if parent_span_id == "" or parent_span_id == "0000000000000000":
                            parent_span_id = None

                        raw_links = span.get("links", [])
                        links: list[SpanLink] = []
                        for link in raw_links:
                            sc = link.get("spanContext", {})
                            links.append(SpanLink(
                                trace_id=sc.get("traceId", link.get("traceId", "")),
                                span_id=sc.get("spanId", link.get("spanId", "")),
                            ))

                        attributes = _parse_attributes(span.get("attributes", []))

                        self._spans.append(CollectedSpan(
                            trace_id=span.get("traceId", ""),
                            span_id=span.get("spanId", ""),
                            name=span.get("name", ""),
                            attributes=attributes,
                            parent_span_id=parent_span_id,
                            links=links,
                        ))

    def start(self) -> int:
        """Start the OTLP receiver on a random port. Returns the port number."""
        self._server = HTTPServer(("127.0.0.1", 0), _OtlpHandler)
        self._server._otlp_receiver = self  # type: ignore[attr-defined]
        self._port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self._port

    def stop(self) -> None:
        """Stop the OTLP receiver."""
        if self._server:
            self._server.shutdown()
            self._server = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None


def _parse_attributes(attrs: list[dict[str, Any]]) -> dict[str, Any]:
    """Parse OTLP attribute array into a flat dict."""
    result: dict[str, Any] = {}
    for attr in attrs:
        key = attr.get("key", "")
        value = attr.get("value", {})
        if "stringValue" in value:
            result[key] = value["stringValue"]
        elif "intValue" in value:
            result[key] = int(value["intValue"])
        elif "doubleValue" in value:
            result[key] = float(value["doubleValue"])
        elif "boolValue" in value:
            result[key] = value["boolValue"]
        else:
            result[key] = str(value)
    return result


def create_otlp_receiver(max_spans: int = DEFAULT_MAX_SPANS) -> OtlpReceiver:
    """Create an OTLP HTTP JSON receiver."""
    return OtlpReceiver(max_spans=max_spans)
