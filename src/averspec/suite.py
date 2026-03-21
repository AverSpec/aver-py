"""Suite, Context, and narrative proxies."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from averspec.adapter import Adapter
from averspec.domain import Marker, MarkerKind
from averspec.trace import TraceEntry
from averspec.telemetry_types import TelemetryExpectation, TelemetryMatchResult
from averspec.telemetry_mode import resolve_telemetry_mode

logger = logging.getLogger("averspec")


class NarrativeProxy:
    """Provides ctx.when.create_task(payload) style access."""

    def __init__(
        self,
        domain_cls: type,
        adapter: Adapter,
        protocol_ctx: Any,
        trace: list[TraceEntry],
        category: str,
        allowed_kinds: set[MarkerKind],
        called_markers: set[str] | None = None,
    ):
        self._domain = domain_cls
        self._adapter = adapter
        self._ctx = protocol_ctx
        self._trace = trace
        self._category = category
        self._allowed_kinds = allowed_kinds
        self._called_markers = called_markers

    def __getattr__(self, name: str) -> Callable:
        markers = self._domain._aver_markers
        marker = markers.get(name)

        if marker is None:
            raise AttributeError(
                f"Domain '{self._domain._aver_domain_name}' has no marker '{name}'"
            )

        if marker.kind not in self._allowed_kinds:
            kind_names = ", ".join(k.value for k in self._allowed_kinds)
            raise TypeError(
                f"ctx.{self._category}.{name} — '{name}' is a {marker.kind.value}, "
                f"but ctx.{self._category} only accepts {kind_names}"
            )

        def invoke(payload=None):
            # Track coverage
            if self._called_markers is not None:
                self._called_markers.add(name)

            start = time.perf_counter()
            try:
                result = self._adapter.execute_sync(marker.name, self._ctx, payload)
                elapsed = time.perf_counter() - start
                entry = TraceEntry(
                    kind=marker.kind.value,
                    category=self._category,
                    name=f"{self._domain._aver_domain_name}.{marker.name}",
                    payload=payload,
                    status="pass",
                    duration_ms=elapsed * 1000,
                    result=result,
                )
                self._trace.append(entry)

                # Per-step telemetry verification
                _apply_telemetry_verification(
                    entry, payload, marker, self._adapter.protocol
                )

                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                self._trace.append(
                    TraceEntry(
                        kind=marker.kind.value,
                        category=self._category,
                        name=f"{self._domain._aver_domain_name}.{marker.name}",
                        payload=payload,
                        status="fail",
                        duration_ms=elapsed * 1000,
                        error=str(e),
                    )
                )
                raise

        return invoke


def _match_span(span, expected: TelemetryExpectation) -> bool:
    """Check if a collected span matches an expectation."""
    if span.name != expected.span:
        return False
    for key, value in expected.attributes.items():
        actual = span.attributes.get(key)
        if actual != value:
            return False
    return True


def _apply_telemetry_verification(
    entry: TraceEntry,
    payload: Any,
    marker: Marker,
    protocol: Any,
) -> None:
    """Run per-step telemetry verification after a successful step.

    Resolves the marker's telemetry declaration (static or callable),
    searches collected spans for a match, and attaches the result to the entry.
    In "fail" mode, raises on mismatch. In "warn" mode, logs a warning.
    """
    if marker.telemetry is None:
        return

    collector = getattr(protocol, "telemetry", None)
    if collector is None:
        return

    mode = resolve_telemetry_mode()
    if mode == "off":
        return

    # Resolve telemetry declaration
    if callable(marker.telemetry):
        expected = marker.telemetry(payload)
    else:
        expected = marker.telemetry

    if not isinstance(expected, TelemetryExpectation):
        return

    # Search collected spans
    spans = collector.get_spans()
    matched_span = None
    for span in spans:
        if _match_span(span, expected):
            matched_span = span
            break

    from averspec.telemetry_types import CollectedSpan

    result = TelemetryMatchResult(
        expected=TelemetryExpectation(
            span=expected.span,
            attributes=dict(expected.attributes),
            causes=list(expected.causes),
        ),
        matched=matched_span is not None,
        matched_span=CollectedSpan(
            trace_id=matched_span.trace_id,
            span_id=matched_span.span_id,
            name=matched_span.name,
            attributes=dict(matched_span.attributes),
            parent_span_id=matched_span.parent_span_id,
            links=list(matched_span.links),
        ) if matched_span is not None else None,
    )
    entry.telemetry = result

    if not result.matched:
        if mode == "fail":
            entry.status = "fail"
            raise AssertionError(
                f"Telemetry mismatch: expected span '{expected.span}' not found"
            )
        if mode == "warn":
            attr_info = ""
            if expected.attributes:
                attr_info = f" with attributes {expected.attributes}"
            available = [s.name for s in spans]
            logger.warning(
                f"Telemetry warning: expected span '{expected.span}'"
                f"{attr_info} not found. Available spans: {available}"
            )


class Context:
    """Test context with narrative proxies, injected into test functions."""

    def __init__(self, domain_cls: type, adapter: Adapter, protocol_ctx: Any):
        self._trace_entries: list[TraceEntry] = []
        self._adapter = adapter
        self._protocol_ctx = protocol_ctx
        self._domain_cls = domain_cls
        self._called_markers: set[str] = set()

        self.given = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "given", {MarkerKind.ACTION, MarkerKind.ASSERTION},
            self._called_markers,
        )
        self.when = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "when", {MarkerKind.ACTION},
            self._called_markers,
        )
        self.then = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "then", {MarkerKind.ASSERTION},
            self._called_markers,
        )
        self.query = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "query", {MarkerKind.QUERY},
            self._called_markers,
        )

    def trace(self) -> list[TraceEntry]:
        return list(self._trace_entries)

    def get_coverage(self) -> dict:
        """Compute vocabulary coverage for the domain."""
        markers = self._domain_cls._aver_markers
        total_actions = [n for n, m in markers.items() if m.kind == MarkerKind.ACTION]
        total_queries = [n for n, m in markers.items() if m.kind == MarkerKind.QUERY]
        total_assertions = [n for n, m in markers.items() if m.kind == MarkerKind.ASSERTION]

        called_actions = [n for n in total_actions if n in self._called_markers]
        called_queries = [n for n in total_queries if n in self._called_markers]
        called_assertions = [n for n in total_assertions if n in self._called_markers]

        total = len(total_actions) + len(total_queries) + len(total_assertions)
        called = len(called_actions) + len(called_queries) + len(called_assertions)
        percentage = 100 if total == 0 else round((called / total) * 100)

        return {
            "domain": self._domain_cls._aver_domain_name,
            "percentage": percentage,
            "actions": {"total": total_actions, "called": called_actions},
            "queries": {"total": total_queries, "called": called_queries},
            "assertions": {"total": total_assertions, "called": called_assertions},
        }


class Suite:
    """Test suite for a domain. Provides @s.test decorator."""

    def __init__(self, domain_cls: type):
        if not getattr(domain_cls, "_aver_is_domain", False):
            raise TypeError(
                f"{domain_cls.__name__} is not a domain. Decorate it with @domain first."
            )
        self.domain_cls = domain_cls

    def test(self, fn: Callable) -> Callable:
        """Decorator that marks a test function for aver collection."""
        if not fn.__name__.startswith("test_"):
            raise ValueError(
                f"@s.test function must start with 'test_', got '{fn.__name__}'. "
                f"Rename to 'test_{fn.__name__}' for pytest collection."
            )
        fn._aver_suite = self
        return fn


# --- Composed suite support ---


class NamespaceProxy:
    """A namespace within a composed suite: ctx.admin.when.create_project()."""

    def __init__(
        self,
        domain_cls: type,
        adapter: Adapter,
        protocol_ctx: Any,
        trace: list[TraceEntry],
    ):
        self._domain = domain_cls
        self._adapter = adapter
        self._protocol_ctx = protocol_ctx
        self._trace = trace

        self.given = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, trace,
            "given", {MarkerKind.ACTION, MarkerKind.ASSERTION},
        )
        self.when = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, trace,
            "when", {MarkerKind.ACTION},
        )
        self.then = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, trace,
            "then", {MarkerKind.ASSERTION},
        )
        self.query = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, trace,
            "query", {MarkerKind.QUERY},
        )


class ComposedContext:
    """Context for composed suites. Exposes namespaces and shared trace."""

    def __init__(self, namespaces: dict[str, NamespaceProxy], trace: list[TraceEntry]):
        self._namespaces = namespaces
        self._trace_entries = trace

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        ns = self._namespaces.get(name)
        if ns is None:
            raise AttributeError(f"No domain namespace '{name}' in composed suite")
        return ns

    def trace(self) -> list[TraceEntry]:
        return list(self._trace_entries)


def _create_composed_context(
    config: dict[str, tuple[type, Adapter]],
    protocol_contexts: dict[str, Any],
    trace: list[TraceEntry],
) -> ComposedContext:
    """Build a ComposedContext from config entries and their protocol contexts."""
    namespaces = {}
    for ns_name, (domain_cls, adapter) in config.items():
        proto_ctx = protocol_contexts[ns_name]
        namespaces[ns_name] = NamespaceProxy(domain_cls, adapter, proto_ctx, trace)
    return ComposedContext(namespaces, trace)


def suite(domain_cls_or_config) -> Suite | ComposedSuite:
    """Create a test suite.

    Single domain: suite(MyDomain) -> Suite
    Composed:      suite({"admin": (AdminDomain, admin_adapter), ...}) -> ComposedSuite
    """
    if isinstance(domain_cls_or_config, dict):
        return ComposedSuite(domain_cls_or_config)
    return Suite(domain_cls_or_config)


class ComposedSuite:
    """Multi-domain suite where each namespace dispatches to its own adapter."""

    def __init__(self, config: dict[str, tuple[type, Adapter]]):
        self._config = config
        # Validate all entries are domains
        for ns_name, (domain_cls, adapter) in config.items():
            if not getattr(domain_cls, "_aver_is_domain", False):
                raise TypeError(
                    f"'{ns_name}' value is not a domain. "
                    f"Decorate it with @domain first."
                )

    def run_test(self, fn: Callable) -> None:
        """Execute a test function with composed context, handling protocol lifecycle."""
        trace: list[TraceEntry] = []
        protocol_contexts: dict[str, Any] = {}
        setup_order: list[str] = []

        try:
            # Setup all protocols
            for ns_name, (domain_cls, adapter) in self._config.items():
                proto_ctx = adapter.protocol.setup()
                protocol_contexts[ns_name] = proto_ctx
                setup_order.append(ns_name)

            # Build composed context
            ctx = _create_composed_context(self._config, protocol_contexts, trace)
            fn(ctx)

        finally:
            # Teardown in reverse order
            for ns_name in reversed(setup_order):
                domain_cls, adapter = self._config[ns_name]
                proto_ctx = protocol_contexts.get(ns_name)
                if proto_ctx is not None:
                    adapter.protocol.teardown(proto_ctx)
