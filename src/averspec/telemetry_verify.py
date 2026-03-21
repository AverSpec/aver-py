"""Contract verification against production traces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from averspec.telemetry_contract import (
    BehavioralContract,
    ContractEntry,
    SpanExpectation,
    AttributeBinding,
)


@dataclass
class ProductionSpan:
    """A span from production trace data."""

    name: str
    attributes: dict[str, Any] = field(default_factory=dict)
    span_id: str | None = None
    parent_span_id: str | None = None


@dataclass
class ProductionTrace:
    """A production trace containing spans from a single request/flow."""

    trace_id: str
    spans: list[ProductionSpan] = field(default_factory=list)


@dataclass
class Violation:
    """A single violation found during verification."""

    kind: str  # "missing-span", "literal-mismatch", "correlation-violation", "no-matching-traces"
    # Fields vary by kind
    span_name: str | None = None
    trace_id: str | None = None
    span: str | None = None
    attribute: str | None = None
    expected: Any = None
    actual: Any = None
    symbol: str | None = None
    paths: list[dict[str, Any]] | None = None
    anchor_span: str | None = None
    message: str | None = None


@dataclass
class EntryVerificationResult:
    """Result of verifying a contract entry against production traces."""

    test_name: str
    traces_matched: int
    traces_checked: int
    violations: list[Violation] = field(default_factory=list)


@dataclass
class ConformanceReport:
    """Full conformance report for a contract."""

    domain: str
    results: list[EntryVerificationResult] = field(default_factory=list)
    total_violations: int = 0


def verify_contract(
    contract: BehavioralContract,
    traces: list[ProductionTrace],
) -> ConformanceReport:
    """Verify a behavioral contract against production traces."""
    results: list[EntryVerificationResult] = []

    for entry in contract.entries:
        results.append(_verify_entry(entry, traces))

    total = sum(len(r.violations) for r in results)

    return ConformanceReport(
        domain=contract.domain,
        results=results,
        total_violations=total,
    )


def _find_matching_span(
    expected_span: SpanExpectation,
    trace: ProductionTrace,
    used_span_ids: set[str],
) -> ProductionSpan | None:
    """Find a production span matching an expectation."""
    # Build span_id -> name lookup for parent resolution
    span_id_to_name: dict[str, str] = {}
    for s in trace.spans:
        if s.span_id:
            span_id_to_name[s.span_id] = s.name

    for s in trace.spans:
        if s.name != expected_span.name:
            continue
        # Don't reuse already-matched spans
        if s.span_id and s.span_id in used_span_ids:
            continue
        # Parent name constraint
        if expected_span.parent_name:
            if not s.parent_span_id:
                continue
            actual_parent_name = span_id_to_name.get(s.parent_span_id)
            if actual_parent_name != expected_span.parent_name:
                continue
        return s

    return None


def _verify_entry(
    entry: ContractEntry,
    traces: list[ProductionTrace],
) -> EntryVerificationResult:
    """Verify a single contract entry against production traces."""
    if not entry.spans:
        return EntryVerificationResult(
            test_name=entry.test_name,
            traces_matched=0,
            traces_checked=0,
        )

    # Anchor span is the first span in the contract entry
    anchor_name = entry.spans[0].name
    matching_traces = [
        t for t in traces
        if any(s.name == anchor_name for s in t.spans)
    ]

    violations: list[Violation] = []

    if not matching_traces:
        violations.append(Violation(
            kind="no-matching-traces",
            anchor_span=anchor_name,
            message=(
                f"Contract entry '{entry.test_name}' matched zero production "
                f"traces — anchor span '{anchor_name}' not found in any trace. "
                f"The contract may be stale or the span name may be wrong."
            ),
        ))

    for trace in matching_traces:
        used_span_ids: set[str] = set()
        matched_spans: dict[int, ProductionSpan] = {}

        # Check each expected span
        for i, expected_span in enumerate(entry.spans):
            prod_span = _find_matching_span(expected_span, trace, used_span_ids)

            if prod_span is None:
                violations.append(Violation(
                    kind="missing-span",
                    span_name=expected_span.name,
                    trace_id=trace.trace_id,
                ))
                continue

            # Track as used
            if prod_span.span_id:
                used_span_ids.add(prod_span.span_id)
            matched_spans[i] = prod_span

            # Check literal attributes
            for attr_key, binding in expected_span.attributes.items():
                if binding.kind == "literal":
                    actual = prod_span.attributes.get(attr_key)
                    if actual != binding.value:
                        violations.append(Violation(
                            kind="literal-mismatch",
                            span=expected_span.name,
                            attribute=attr_key,
                            expected=binding.value,
                            actual=actual,
                            trace_id=trace.trace_id,
                        ))

        # Check correlations
        symbol_values: dict[str, list[dict[str, Any]]] = {}
        for i, expected_span in enumerate(entry.spans):
            prod_span = matched_spans.get(i)
            if prod_span is None:
                continue

            for attr_key, binding in expected_span.attributes.items():
                if binding.kind == "correlated" and binding.symbol:
                    value = prod_span.attributes.get(attr_key)
                    if binding.symbol not in symbol_values:
                        symbol_values[binding.symbol] = []
                    symbol_values[binding.symbol].append({
                        "span": expected_span.name,
                        "attribute": attr_key,
                        "value": value,
                    })

        # For each symbol, all values must be equal
        for symbol, paths in symbol_values.items():
            if len(paths) < 2:
                continue
            first_value = paths[0]["value"]
            if not all(p["value"] == first_value for p in paths):
                violations.append(Violation(
                    kind="correlation-violation",
                    symbol=symbol,
                    paths=paths,
                    trace_id=trace.trace_id,
                ))

    return EntryVerificationResult(
        test_name=entry.test_name,
        traces_matched=len(matching_traces),
        traces_checked=len(traces),
        violations=violations,
    )
