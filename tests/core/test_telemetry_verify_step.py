"""Tests for per-step telemetry verification in suite.py."""

import pytest

from averspec.domain import domain, action, Marker, MarkerKind
from averspec.adapter import Adapter
from averspec.protocol import Protocol, TelemetryCollector
from averspec.suite import NarrativeProxy, _match_span, _apply_telemetry_verification
from averspec.trace import TraceEntry
from averspec.telemetry_types import (
    TelemetryExpectation,
    CollectedSpan,
    SpanLink,
)


# --- Helpers ---


class FakeCollector(TelemetryCollector):
    def __init__(self, spans=None):
        self._spans = spans or []

    def get_spans(self):
        return list(self._spans)

    def reset(self):
        self._spans.clear()


class FakeProtocol(Protocol):
    name = "fake"

    def __init__(self, collector=None):
        self.telemetry = collector

    def setup(self):
        return {}

    def teardown(self, ctx):
        pass


# --- Tests ---


def test_match_span_by_name():
    span = CollectedSpan(trace_id="a", span_id="1", name="order.checkout")
    exp = TelemetryExpectation(span="order.checkout")
    assert _match_span(span, exp) is True


def test_match_span_name_mismatch():
    span = CollectedSpan(trace_id="a", span_id="1", name="order.cancel")
    exp = TelemetryExpectation(span="order.checkout")
    assert _match_span(span, exp) is False


def test_match_span_with_attributes():
    span = CollectedSpan(
        trace_id="a", span_id="1", name="order.checkout",
        attributes={"order.id": "123", "extra": "val"},
    )
    exp = TelemetryExpectation(
        span="order.checkout",
        attributes={"order.id": "123"},
    )
    assert _match_span(span, exp) is True


def test_match_span_attribute_mismatch():
    span = CollectedSpan(
        trace_id="a", span_id="1", name="order.checkout",
        attributes={"order.id": "999"},
    )
    exp = TelemetryExpectation(
        span="order.checkout",
        attributes={"order.id": "123"},
    )
    assert _match_span(span, exp) is False


def test_per_step_matching_span_found(monkeypatch):
    """When a matching span exists, telemetry result is attached to entry."""
    monkeypatch.setenv("AVER_TELEMETRY_MODE", "fail")

    span = CollectedSpan(
        trace_id="aaa", span_id="001", name="order.checkout",
        attributes={"order.id": "123"},
    )
    collector = FakeCollector([span])
    protocol = FakeProtocol(collector)

    marker = Marker(MarkerKind.ACTION, type(None))
    marker.telemetry = TelemetryExpectation(
        span="order.checkout",
        attributes={"order.id": "123"},
    )

    entry = TraceEntry(kind="action", category="when", name="order.checkout")

    _apply_telemetry_verification(entry, None, marker, protocol)

    assert entry.telemetry is not None
    assert entry.telemetry.matched is True
    assert entry.telemetry.matched_span is not None
    assert entry.telemetry.matched_span.name == "order.checkout"


def test_per_step_missing_span_fail_mode_raises(monkeypatch):
    """In fail mode, missing span raises AssertionError."""
    monkeypatch.setenv("AVER_TELEMETRY_MODE", "fail")

    collector = FakeCollector([])
    protocol = FakeProtocol(collector)

    marker = Marker(MarkerKind.ACTION, type(None))
    marker.telemetry = TelemetryExpectation(span="order.checkout")

    entry = TraceEntry(kind="action", category="when", name="order.checkout")

    with pytest.raises(AssertionError, match="expected span 'order.checkout' not found"):
        _apply_telemetry_verification(entry, None, marker, protocol)

    assert entry.status == "fail"


def test_per_step_missing_span_warn_mode_no_raise(monkeypatch):
    """In warn mode, missing span does not raise."""
    monkeypatch.setenv("AVER_TELEMETRY_MODE", "warn")

    collector = FakeCollector([])
    protocol = FakeProtocol(collector)

    marker = Marker(MarkerKind.ACTION, type(None))
    marker.telemetry = TelemetryExpectation(span="order.checkout")

    entry = TraceEntry(kind="action", category="when", name="order.checkout")

    # Should not raise
    _apply_telemetry_verification(entry, None, marker, protocol)

    assert entry.telemetry is not None
    assert entry.telemetry.matched is False


def test_per_step_parameterized_telemetry(monkeypatch):
    """Parameterized telemetry function is called with payload."""
    monkeypatch.setenv("AVER_TELEMETRY_MODE", "fail")

    span = CollectedSpan(
        trace_id="aaa", span_id="001", name="order.checkout",
        attributes={"order.id": "ORD-42"},
    )
    collector = FakeCollector([span])
    protocol = FakeProtocol(collector)

    class Payload:
        order_id = "ORD-42"

    marker = Marker(MarkerKind.ACTION, type(None))
    marker.telemetry = lambda p: TelemetryExpectation(
        span="order.checkout",
        attributes={"order.id": p.order_id},
    )

    payload = Payload()
    entry = TraceEntry(kind="action", category="when", name="order.checkout")

    _apply_telemetry_verification(entry, payload, marker, protocol)

    assert entry.telemetry is not None
    assert entry.telemetry.matched is True


def test_no_telemetry_on_marker_skips_verification():
    """When marker has no telemetry, no verification happens."""
    protocol = FakeProtocol(FakeCollector([]))
    marker = Marker(MarkerKind.ACTION, type(None))  # no telemetry

    entry = TraceEntry(kind="action", category="when", name="task.create")
    _apply_telemetry_verification(entry, None, marker, protocol)

    assert entry.telemetry is None


def test_no_collector_on_protocol_skips_verification():
    """When protocol has no telemetry collector, no verification happens."""
    protocol = FakeProtocol(None)  # no collector

    marker = Marker(MarkerKind.ACTION, type(None))
    marker.telemetry = TelemetryExpectation(span="task.create")

    entry = TraceEntry(kind="action", category="when", name="task.create")
    _apply_telemetry_verification(entry, None, marker, protocol)

    assert entry.telemetry is None
