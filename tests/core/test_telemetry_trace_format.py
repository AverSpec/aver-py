"""Tests for telemetry info in trace format output."""

from averspec.trace import TraceEntry
from averspec.trace_format import format_trace
from averspec.telemetry_types import (
    TelemetryExpectation,
    TelemetryMatchResult,
    CollectedSpan,
)


def test_matched_span_shows_checkmark():
    entry = TraceEntry(
        kind="action",
        category="when",
        name="auth.login",
        status="pass",
        telemetry=TelemetryMatchResult(
            expected=TelemetryExpectation(span="auth.login.span", attributes={}),
            matched=True,
            matched_span=CollectedSpan(
                trace_id="t1", span_id="s1", name="auth.login.span",
            ),
        ),
    )
    output = format_trace([entry])
    assert "\u2713 telemetry: auth.login.span" in output


def test_unmatched_span_shows_warning():
    entry = TraceEntry(
        kind="action",
        category="when",
        name="auth.login",
        status="pass",
        telemetry=TelemetryMatchResult(
            expected=TelemetryExpectation(span="auth.login.span", attributes={}),
            matched=False,
            matched_span=None,
        ),
    )
    output = format_trace([entry])
    assert "\u26a0 telemetry: expected span 'auth.login.span' not found" in output


def test_attributes_displayed():
    entry = TraceEntry(
        kind="action",
        category="when",
        name="auth.login",
        status="pass",
        telemetry=TelemetryMatchResult(
            expected=TelemetryExpectation(
                span="auth.login.span",
                attributes={"user.email": "test@example.com"},
            ),
            matched=True,
            matched_span=CollectedSpan(
                trace_id="t1", span_id="s1", name="auth.login.span",
                attributes={"user.email": "test@example.com"},
            ),
        ),
    )
    output = format_trace([entry])
    assert "auth.login.span" in output
    assert "user.email" in output
    assert "test@example.com" in output


def test_no_telemetry_field_unchanged():
    entry = TraceEntry(
        kind="action",
        category="when",
        name="auth.login",
        status="pass",
    )
    output = format_trace([entry])
    assert "telemetry" not in output
    assert "[PASS]" in output
    assert "auth.login" in output
