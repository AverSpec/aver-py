"""Tests for telemetry type structures."""

from averspec.telemetry_types import (
    TelemetryExpectation,
    CollectedSpan,
    SpanLink,
    TelemetryMatchResult,
)


def test_telemetry_expectation_defaults():
    exp = TelemetryExpectation(span="order.checkout")
    assert exp.span == "order.checkout"
    assert exp.attributes == {}
    assert exp.causes == []


def test_telemetry_expectation_with_attributes_and_causes():
    exp = TelemetryExpectation(
        span="order.checkout",
        attributes={"order.id": "123", "tenant.id": "acme"},
        causes=["order.fulfill"],
    )
    assert exp.attributes == {"order.id": "123", "tenant.id": "acme"}
    assert exp.causes == ["order.fulfill"]


def test_collected_span_structure():
    span = CollectedSpan(
        trace_id="aaa",
        span_id="001",
        name="order.checkout",
        attributes={"order.id": "123"},
        parent_span_id="000",
        links=[SpanLink(trace_id="bbb", span_id="002")],
    )
    assert span.trace_id == "aaa"
    assert span.span_id == "001"
    assert span.name == "order.checkout"
    assert span.attributes["order.id"] == "123"
    assert span.parent_span_id == "000"
    assert len(span.links) == 1
    assert span.links[0].trace_id == "bbb"


def test_telemetry_match_result_matched():
    exp = TelemetryExpectation(span="order.checkout")
    span = CollectedSpan(trace_id="aaa", span_id="001", name="order.checkout")
    result = TelemetryMatchResult(expected=exp, matched=True, matched_span=span)
    assert result.matched is True
    assert result.matched_span is not None
    assert result.matched_span.name == "order.checkout"


def test_telemetry_match_result_unmatched():
    exp = TelemetryExpectation(span="order.checkout")
    result = TelemetryMatchResult(expected=exp, matched=False)
    assert result.matched is False
    assert result.matched_span is None
