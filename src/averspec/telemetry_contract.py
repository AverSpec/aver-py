"""Behavioral contract extraction from test traces."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from averspec.trace import TraceEntry


@dataclass
class AttributeBinding:
    """A binding for a span attribute in a contract."""

    kind: str  # "literal" or "correlated"
    value: Any = None  # for literal bindings
    symbol: str | None = None  # for correlated bindings (e.g., "$email")


@dataclass
class SpanExpectation:
    """Expected span in the behavioral contract."""

    name: str
    attributes: dict[str, AttributeBinding] = field(default_factory=dict)
    parent_name: str | None = None


@dataclass
class ContractEntry:
    """A single contract entry from one test's expected trace pattern."""

    test_name: str
    spans: list[SpanExpectation] = field(default_factory=list)


@dataclass
class BehavioralContract:
    """The full behavioral contract exported from test runs."""

    domain: str
    entries: list[ContractEntry] = field(default_factory=list)


class _FieldTracker:
    """Proxy that tracks field accesses and returns sentinel values.

    Supports both attribute access (p.field) and item access (p["field"])
    so it works with both dataclass-style and dict-style payloads.
    """

    def __init__(self):
        self._accessed: dict[str, str] = {}

    def __getattr__(self, name: str) -> str:
        if name.startswith("_"):
            raise AttributeError(name)
        sentinel = f"__aver_sentinel_{name}__"
        self._accessed[name] = sentinel
        return sentinel

    def __getitem__(self, key: str) -> str:
        sentinel = f"__aver_sentinel_{key}__"
        self._accessed[key] = sentinel
        return sentinel


def _track_field_accesses(
    telemetry_fn: Any,
    payload: Any,
) -> dict[str, str]:
    """Run a telemetry function with a field tracker to discover attribute bindings.

    Returns a dict mapping attribute_key -> param_field_name.
    """
    tracker = _FieldTracker()
    result = telemetry_fn(tracker)

    sentinel_to_field: dict[str, str] = {}
    for field_name, sentinel in tracker._accessed.items():
        sentinel_to_field[sentinel] = field_name

    attr_to_field: dict[str, str] = {}
    if hasattr(result, "attributes") and result.attributes:
        for attr_key, attr_value in result.attributes.items():
            field_name = sentinel_to_field.get(attr_value)
            if field_name:
                attr_to_field[attr_key] = field_name

    return attr_to_field


def extract_contract(
    domain_cls: Any,
    results: list[dict[str, Any]],
) -> BehavioralContract:
    """Extract a behavioral contract from test execution traces.

    Args:
        domain_cls: The domain class (decorated with @domain).
        results: List of {"test_name": str, "trace": list[TraceEntry]} from passing tests.

    Returns:
        A BehavioralContract with entries for each test.
    """
    entries: list[ContractEntry] = []

    for result in results:
        spans = _extract_spans(domain_cls, result["trace"])
        if spans:
            entries.append(ContractEntry(
                test_name=result["test_name"],
                spans=spans,
            ))

    return BehavioralContract(
        domain=domain_cls._aver_domain_name,
        entries=entries,
    )


def _extract_spans(domain_cls: Any, trace: list[TraceEntry]) -> list[SpanExpectation]:
    """Extract span expectations from trace entries."""
    spans: list[SpanExpectation] = []

    # Build span_id -> name map for parent lookups
    span_id_to_name: dict[str, str] = {}
    for entry in trace:
        if entry.telemetry and entry.telemetry.matched_span:
            ms = entry.telemetry.matched_span
            if ms.span_id:
                span_id_to_name[ms.span_id] = ms.name

    markers = domain_cls._aver_markers

    for entry in trace:
        if not entry.telemetry or not entry.telemetry.expected:
            continue

        expected = entry.telemetry.expected
        attributes: dict[str, AttributeBinding] = {}

        # Find the marker to check if telemetry is parameterized
        marker_name = entry.name.split(".")[-1] if "." in entry.name else entry.name
        marker = markers.get(marker_name)
        is_parameterized = (
            marker is not None
            and marker.telemetry is not None
            and callable(marker.telemetry)
        )

        if is_parameterized and entry.payload is not None:
            # Use field tracker to discover correlated bindings
            attr_to_field = _track_field_accesses(marker.telemetry, entry.payload)

            for attr_key, attr_value in expected.attributes.items():
                param_field = attr_to_field.get(attr_key)
                if param_field:
                    attributes[attr_key] = AttributeBinding(
                        kind="correlated",
                        symbol=f"${param_field}",
                    )
                else:
                    attributes[attr_key] = AttributeBinding(
                        kind="literal",
                        value=attr_value,
                    )
        else:
            # Static declaration: all literal
            for attr_key, attr_value in expected.attributes.items():
                attributes[attr_key] = AttributeBinding(
                    kind="literal",
                    value=attr_value,
                )

        # Resolve parent name from matched span hierarchy
        parent_name = None
        matched_span = entry.telemetry.matched_span
        if matched_span and matched_span.parent_span_id:
            parent_name = span_id_to_name.get(matched_span.parent_span_id)

        expectation = SpanExpectation(
            name=expected.span,
            attributes=attributes,
            parent_name=parent_name,
        )
        spans.append(expectation)

    return spans
