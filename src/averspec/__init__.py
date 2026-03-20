"""AverSpec — Domain-driven acceptance testing for Python."""

from averspec.domain import domain, action, query, assertion, Marker, MarkerKind
from averspec.adapter import implement
from averspec.suite import suite
from averspec.protocol import Protocol, unit, with_fixture
from averspec.config import define_config
from averspec.trace import TraceEntry

__all__ = [
    "domain",
    "action",
    "query",
    "assertion",
    "Marker",
    "MarkerKind",
    "implement",
    "suite",
    "Protocol",
    "unit",
    "with_fixture",
    "define_config",
    "TraceEntry",
]
