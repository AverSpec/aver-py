"""Tests for trace formatting."""

from averspec.trace import TraceEntry
from averspec.trace_format import format_trace


def test_uses_category_labels_when_present():
    trace = [
        TraceEntry(kind="action", category="given", name="Cart.add_item",
                   payload={"name": "Widget"}, status="pass", duration_ms=12),
        TraceEntry(kind="action", category="when", name="Cart.checkout",
                   payload=None, status="pass", duration_ms=45),
        TraceEntry(kind="assertion", category="then", name="Cart.total_charged",
                   payload={"amount": 35}, status="pass", duration_ms=2),
    ]
    output = format_trace(trace)
    assert "GIVEN" in output
    assert "WHEN" in output
    assert "THEN" in output
    assert "add_item" in output
    assert "checkout" in output
    assert "total_charged" in output


def test_falls_back_to_kind_labels_when_no_category():
    trace = [
        TraceEntry(kind="action", category="", name="Test.do_thing",
                   payload=None, status="pass"),
        TraceEntry(kind="query", category="", name="Test.get_val",
                   payload=None, status="pass"),
        TraceEntry(kind="assertion", category="", name="Test.check",
                   payload=None, status="pass"),
    ]
    output = format_trace(trace)
    assert "ACT" in output
    assert "QUERY" in output
    assert "ASSERT" in output


def test_shows_fail_status():
    trace = [
        TraceEntry(kind="action", category="given", name="Test.setup",
                   payload=None, status="pass"),
        TraceEntry(kind="assertion", category="then", name="Test.check",
                   payload=None, status="fail", error="boom"),
    ]
    output = format_trace(trace)
    assert "[PASS]" in output
    assert "[FAIL]" in output
    assert "boom" in output


def test_shows_duration_when_available():
    trace = [
        TraceEntry(kind="action", category="act", name="Test.do_thing",
                   payload=None, status="pass", duration_ms=42),
    ]
    output = format_trace(trace)
    assert "42ms" in output


def test_truncates_long_payloads_on_passing_steps():
    trace = [
        TraceEntry(kind="action", category="act", name="Test.do_thing",
                   payload={"data": "a" * 100}, status="pass"),
    ]
    output = format_trace(trace)
    assert "..." in output
    assert "a" * 100 not in output


def test_shows_full_payload_on_failing_steps():
    long_value = "a" * 100
    trace = [
        TraceEntry(kind="assertion", category="then", name="Test.check",
                   payload={"data": long_value}, status="fail", error="mismatch"),
    ]
    output = format_trace(trace)
    assert long_value in output


def test_handles_none_payload():
    trace = [
        TraceEntry(kind="action", category="when", name="Test.noop",
                   payload=None, status="pass"),
    ]
    output = format_trace(trace)
    assert "Test.noop()" in output


def test_handles_unknown_kind_without_category():
    trace = [
        TraceEntry(kind="test", category="", name="Test.hook",
                   payload=None, status="fail", error="hook broke"),
    ]
    output = format_trace(trace)
    assert "[FAIL]" in output
    assert "hook" in output
