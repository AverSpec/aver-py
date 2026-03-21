"""Telemetry types for span collection and verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpanLink:
    """Link to another span for cross-trace correlation."""

    trace_id: str
    span_id: str


@dataclass
class CollectedSpan:
    """A span collected during test execution."""

    trace_id: str
    span_id: str
    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    parent_span_id: str | None = None
    links: list[SpanLink] = field(default_factory=list)


@dataclass
class TelemetryExpectation:
    """Expected telemetry for a domain marker step."""

    span: str
    attributes: dict[str, Any] = field(default_factory=dict)
    causes: list[str] = field(default_factory=list)


@dataclass
class TelemetryMatchResult:
    """Result of matching a telemetry expectation against collected spans."""

    expected: TelemetryExpectation
    matched: bool
    matched_span: CollectedSpan | None = None
