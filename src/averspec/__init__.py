"""AverSpec — Domain-driven acceptance testing for Python."""

from averspec.domain import domain, action, query, assertion, Marker, MarkerKind
from averspec.adapter import implement
from averspec.suite import suite, Context, ComposedSuite
from averspec.protocol import Protocol, TelemetryCollector, unit, with_fixture
from averspec.config import define_config
from averspec.trace import TraceEntry
from averspec.eventually import eventually
from averspec.trace_format import format_trace
from averspec.approvals import approve, characterize
from averspec.telemetry_types import (
    TelemetryExpectation,
    CollectedSpan,
    SpanLink,
    TelemetryMatchResult,
)
from averspec.telemetry_mode import resolve_telemetry_mode
from averspec.correlation import verify_correlation
from averspec.telemetry_contract import extract_contract, BehavioralContract
from averspec.telemetry_verify import verify_contract, ConformanceReport
from averspec.otlp_receiver import create_otlp_receiver


def __getattr__(name: str):
    if name == "http":
        from averspec.protocol_http import http
        return http
    if name == "playwright":
        from averspec.protocol_playwright import playwright
        return playwright
    raise AttributeError(f"module 'averspec' has no attribute {name!r}")


__all__ = [
    "domain",
    "action",
    "query",
    "assertion",
    "Marker",
    "MarkerKind",
    "implement",
    "suite",
    "Context",
    "ComposedSuite",
    "Protocol",
    "TelemetryCollector",
    "unit",
    "with_fixture",
    "define_config",
    "TraceEntry",
    "eventually",
    "format_trace",
    "approve",
    "characterize",
    "http",
    "playwright",
    # Telemetry
    "TelemetryExpectation",
    "CollectedSpan",
    "SpanLink",
    "TelemetryMatchResult",
    "resolve_telemetry_mode",
    "verify_correlation",
    "extract_contract",
    "BehavioralContract",
    "verify_contract",
    "ConformanceReport",
    "create_otlp_receiver",
]
