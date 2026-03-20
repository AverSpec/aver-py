"""Dogfood domain: aver-py describes its own behavior."""

from dataclasses import dataclass
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
class ProxyRestrictionCheck:
    """Check that a proxy rejects a marker of the wrong kind."""
    proxy_name: str
    marker_name: str


@dataclass
class CompletenessCheck:
    """Check that an adapter handles all markers."""
    missing: list[str]  # expected missing marker names (empty = complete)


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

    # Queries: things we can inspect
    get_markers = query(type(None), list)
    get_trace = query(type(None), list)

    # Assertions: things we verify
    domain_has_marker = assertion(MarkerCheck)
    trace_has_entry = assertion(TraceCheck)
    adapter_is_complete = assertion(CompletenessCheck)
    proxy_rejects_wrong_kind = assertion(ProxyRestrictionCheck)
