"""Tests for cross-step telemetry correlation verification."""

from averspec.correlation import verify_correlation
from averspec.trace import TraceEntry
from averspec.telemetry_types import (
    TelemetryExpectation,
    TelemetryMatchResult,
    CollectedSpan,
    SpanLink,
)


def _make_entry(
    name: str,
    expected_attrs: dict[str, str],
    matched_span: dict | None = None,
    causes: list[str] | None = None,
) -> TraceEntry:
    """Build a TraceEntry with telemetry match result."""
    ms = None
    if matched_span is not None:
        links = [
            SpanLink(trace_id=l["trace_id"], span_id=l["span_id"])
            for l in matched_span.get("links", [])
        ]
        ms = CollectedSpan(
            trace_id=matched_span.get("trace_id", ""),
            span_id=matched_span.get("span_id", ""),
            name=matched_span["name"],
            attributes=matched_span.get("attributes", {}),
            links=links,
        )

    return TraceEntry(
        kind="action",
        category="when",
        name=name,
        telemetry=TelemetryMatchResult(
            expected=TelemetryExpectation(
                span=f"span.{name}",
                attributes=expected_attrs,
                causes=causes or [],
            ),
            matched=True,
            matched_span=ms,
        ),
    )


# --- Attribute correlation ---


def test_correlated_steps_matching_attributes_no_violations():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.groups) == 1
    assert result.groups[0].key == "order.id"
    assert len(result.violations) == 0


def test_steps_with_different_values_not_correlated():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }),
        _make_entry("checkout", {"order.id": "456"}, {
            "name": "order.checkout", "attributes": {"order.id": "456"},
            "trace_id": "bbb", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.groups) == 0  # no group with 2+ same-value steps


def test_attribute_missing_on_matched_span_reports_violation():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {},  # missing order.id
            "trace_id": "aaa", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.violations) == 1
    assert result.violations[0].kind == "attribute-mismatch"
    assert result.violations[0].key == "order.id"
    assert "fulfillOrder" in result.violations[0].message


def test_attribute_wrong_value_reports_violation():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {"order.id": "999"},
            "trace_id": "aaa", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.violations) == 1
    assert result.violations[0].kind == "attribute-mismatch"
    assert "999" in result.violations[0].message


def test_steps_without_telemetry_are_ignored():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }),
        TraceEntry(kind="query", category="query", name="getStatus"),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.groups) == 1
    assert len(result.violations) == 0


# --- Causal correlation ---


def test_correlated_steps_same_trace_pass_causal_check():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.violations) == 0


def test_different_traces_with_link_pass_when_causes_declared():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }, causes=["order.fulfill"]),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {"order.id": "123"},
            "trace_id": "bbb", "span_id": "002",
            "links": [{"trace_id": "aaa", "span_id": "001"}],
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.violations) == 0


def test_different_traces_without_link_report_causal_break():
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }, causes=["order.fulfill"]),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {"order.id": "123"},
            "trace_id": "bbb", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    causal = [v for v in result.violations if v.kind == "causal-break"]
    assert len(causal) == 1
    assert "different traces" in causal[0].message


def test_different_traces_without_causes_no_causal_break():
    """Without causes declared, different traces are not flagged."""
    trace = [
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "aaa", "span_id": "001",
        }),
        _make_entry("fulfillOrder", {"order.id": "123"}, {
            "name": "order.fulfill", "attributes": {"order.id": "123"},
            "trace_id": "bbb", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    causal = [v for v in result.violations if v.kind == "causal-break"]
    assert len(causal) == 0


def test_uncorrelated_steps_skip_causal_check():
    trace = [
        _make_entry("createUser", {"user.id": "u1"}, {
            "name": "user.create", "attributes": {"user.id": "u1"},
            "trace_id": "aaa", "span_id": "001",
        }),
        _make_entry("checkout", {"order.id": "123"}, {
            "name": "order.checkout", "attributes": {"order.id": "123"},
            "trace_id": "bbb", "span_id": "002",
        }),
    ]

    result = verify_correlation(trace)
    assert len(result.groups) == 0
    assert len(result.violations) == 0
