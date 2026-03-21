"""Dogfood domain: aver-py describes its own behavior."""

from dataclasses import dataclass, field
from typing import Any
from averspec import domain, action, query, assertion


# --- Payloads ---

@dataclass
class DomainSpec:
    """Specification for creating a domain."""
    name: str
    actions: list[str]
    queries: list[str]
    assertions: list[str]


@dataclass
class AdapterSpec:
    """Specification for creating an adapter."""
    protocol_name: str = "unit"


@dataclass
class OperationCall:
    """A domain operation to invoke."""
    marker_name: str
    payload: Any = None


@dataclass
class ProxyCall:
    """An attempt to call a marker through a specific proxy."""
    proxy_name: str  # "given", "when", "then", "query"
    marker_name: str
    payload: Any = None


@dataclass
class MarkerCheck:
    """Check that a domain has a specific marker."""
    name: str
    kind: str  # "action", "query", "assertion"


@dataclass
class TraceCheck:
    """Check a trace entry at a given index."""
    index: int
    category: str
    status: str = "pass"


@dataclass
class TraceEntryCheck:
    """Check a trace entry at a given index for kind, category, and status."""
    index: int
    kind: str
    category: str
    status: str = "pass"


@dataclass
class TraceLengthCheck:
    """Check the trace has an expected number of entries."""
    expected: int


@dataclass
class QueryResultCheck:
    """Check that a query returned a specific value."""
    marker_name: str
    expected: Any


@dataclass
class VocabularyCheck:
    """Check vocabulary counts on the current domain."""
    actions: int
    queries: int
    assertions: int


@dataclass
class ProxyRestrictionCheck:
    """Check that a proxy rejects a marker of the wrong kind."""
    proxy_name: str
    marker_name: str


@dataclass
class CompletenessCheck:
    """Check that an adapter handles all markers."""
    missing: list[str]  # expected missing marker names (empty = complete)


@dataclass
class FailingAssertionSpec:
    """Execute an assertion that is rigged to fail."""
    marker_name: str
    payload: Any = None


# --- Coverage payloads ---

@dataclass
class CoverageCheck:
    """Check coverage percentage for the current inner domain."""
    expected_percentage: int


# --- Telemetry payloads ---

@dataclass
class TelemetryDomainSpec:
    """Specification for creating a domain with telemetry declarations."""
    name: str
    actions: list[str]
    span_names: list[str]  # parallel to actions: span name per action


@dataclass
class TelemetryAdapterSpec:
    """Specification for creating an adapter with a telemetry collector."""
    pass


@dataclass
class TelemetrySpanCheck:
    """Check that a trace entry has a telemetry match result."""
    index: int
    expected_span: str
    matched: bool


# --- Extension payloads ---

@dataclass
class ExtensionSpec:
    """Specification for extending a domain."""
    child_name: str
    new_actions: list[str]
    new_queries: list[str]
    new_assertions: list[str]


@dataclass
class ExtensionMarkerCheck:
    """Check that the extended domain has markers from parent and child."""
    parent_marker_names: list[str]
    child_marker_names: list[str]


# --- Results ---

@dataclass
class MarkerInfo:
    name: str
    kind: str
    domain_name: str


@dataclass
class TraceSnapshot:
    entries: list[dict]


# --- Domain ---

@domain("aver-core")
class AverCore:
    # Actions: things the framework does
    define_domain = action(DomainSpec)
    create_adapter = action(AdapterSpec)
    call_operation = action(OperationCall)
    call_through_proxy = action(ProxyCall)
    execute_failing_assertion = action(FailingAssertionSpec)

    # Coverage actions
    define_domain_for_coverage = action(DomainSpec)
    create_adapter_for_coverage = action(AdapterSpec)
    call_coverage_operation = action(OperationCall)

    # Telemetry actions
    define_telemetry_domain = action(TelemetryDomainSpec)
    create_telemetry_adapter = action(TelemetryAdapterSpec)
    call_telemetry_operation = action(OperationCall)

    # Extension actions
    extend_domain = action(ExtensionSpec)

    # Queries: things we can inspect
    get_markers = query(type(None), list)
    get_trace = query(type(None), list)
    get_query_result = query(str, Any)  # payload is marker_name, returns result
    get_coverage_percentage = query(type(None), int)
    get_extension_markers = query(type(None), list)

    # Assertions: things we verify
    domain_has_marker = assertion(MarkerCheck)
    trace_has_entry = assertion(TraceCheck)
    trace_entry_matches = assertion(TraceEntryCheck)
    trace_has_length = assertion(TraceLengthCheck)
    query_returned_value = assertion(QueryResultCheck)
    has_vocabulary = assertion(VocabularyCheck)
    adapter_is_complete = assertion(CompletenessCheck)
    proxy_rejects_wrong_kind = assertion(ProxyRestrictionCheck)
    coverage_is = assertion(CoverageCheck)
    telemetry_span_matched = assertion(TelemetrySpanCheck)
    extension_has_markers = assertion(ExtensionMarkerCheck)
