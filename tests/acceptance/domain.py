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

    # Queries: things we can inspect
    get_markers = query(type(None), list)
    get_trace = query(type(None), list)
    get_query_result = query(str, Any)  # payload is marker_name, returns result

    # Assertions: things we verify
    domain_has_marker = assertion(MarkerCheck)
    trace_has_entry = assertion(TraceCheck)
    trace_entry_matches = assertion(TraceEntryCheck)
    trace_has_length = assertion(TraceLengthCheck)
    query_returned_value = assertion(QueryResultCheck)
    has_vocabulary = assertion(VocabularyCheck)
    adapter_is_complete = assertion(CompletenessCheck)
    proxy_rejects_wrong_kind = assertion(ProxyRestrictionCheck)
