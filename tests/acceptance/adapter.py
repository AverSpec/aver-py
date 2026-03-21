"""Dogfood adapter: exercises aver-py through its own public API."""

from averspec import implement, unit, domain as domain_decorator, action, query, assertion
from averspec.adapter import AdapterBuilder
from averspec.suite import Context, NarrativeProxy
from averspec.domain import Marker, MarkerKind
from averspec.trace import TraceEntry
from averspec.telemetry_types import TelemetryExpectation, CollectedSpan, TelemetryMatchResult
from averspec.protocol import Protocol, TelemetryCollector
from tests.acceptance.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall, ProxyCall,
    MarkerCheck, TraceCheck, TraceEntryCheck, TraceLengthCheck,
    QueryResultCheck, VocabularyCheck,
    ProxyRestrictionCheck, CompletenessCheck, FailingAssertionSpec,
    MarkerInfo,
    CoverageCheck,
    TelemetryDomainSpec, TelemetryAdapterSpec, TelemetrySpanCheck,
    ExtensionSpec, ExtensionMarkerCheck,
)


class AverWorkbench:
    """Context object: a workspace for creating and testing aver constructs."""

    def __init__(self):
        self.current_domain = None
        self.current_adapter = None
        self.current_builder = None
        self.current_context = None  # a Context from the inner domain
        self.inner_trace = []
        self.last_query_results = {}  # marker_name -> result

        # Coverage tracking workspace
        self.coverage_domain = None
        self.coverage_adapter = None
        self.coverage_context = None

        # Telemetry workspace
        self.telemetry_domain = None
        self.telemetry_adapter = None
        self.telemetry_context = None
        self.telemetry_collector = None

        # Extension workspace
        self.extended_domain = None


adapter = implement(AverCore, protocol=unit(lambda: AverWorkbench()))


@adapter.handle(AverCore.define_domain)
def define_domain(wb: AverWorkbench, spec: DomainSpec):
    """Create a real domain using the aver public API."""
    # Build marker attributes dynamically
    attrs = {}
    for name in spec.actions:
        attrs[name] = action(str)
    for name in spec.queries:
        attrs[name] = query(str, str)
    for name in spec.assertions:
        attrs[name] = assertion(str)

    # Create and decorate the class
    cls = type(f"Domain_{spec.name}", (), attrs)
    domain_decorator(spec.name)(cls)
    wb.current_domain = cls


@adapter.handle(AverCore.create_adapter)
def create_adapter(wb: AverWorkbench, spec: AdapterSpec):
    """Create an adapter for the current domain with stub handlers."""
    if wb.current_domain is None:
        raise RuntimeError("No domain defined yet")

    builder = implement(wb.current_domain, protocol=unit(lambda: {}, name=spec.protocol_name))

    for name, marker in wb.current_domain._aver_markers.items():
        if marker.kind == MarkerKind.ACTION:
            @builder.handle(marker)
            def action_handler(ctx, payload, _name=name):
                pass
        elif marker.kind == MarkerKind.QUERY:
            @builder.handle(marker)
            def query_handler(ctx, payload, _name=name):
                return f"result-{_name}"
        elif marker.kind == MarkerKind.ASSERTION:
            @builder.handle(marker)
            def assertion_handler(ctx, payload, _name=name):
                pass

    wb.current_adapter = builder.build()

    # Create an inner Context for testing dispatch
    inner_ctx = wb.current_adapter.protocol.setup()
    wb.current_context = Context(wb.current_domain, wb.current_adapter, inner_ctx)


@adapter.handle(AverCore.call_operation)
def call_operation(wb: AverWorkbench, op: OperationCall):
    """Call a domain operation through the inner context's when proxy."""
    if wb.current_context is None:
        raise RuntimeError("No adapter created yet")
    marker = wb.current_domain._aver_markers[op.marker_name]
    if marker.kind == MarkerKind.ACTION:
        getattr(wb.current_context.when, op.marker_name)(op.payload)
    elif marker.kind == MarkerKind.QUERY:
        result = getattr(wb.current_context.query, op.marker_name)(op.payload)
        wb.last_query_results[op.marker_name] = result
    elif marker.kind == MarkerKind.ASSERTION:
        getattr(wb.current_context.then, op.marker_name)(op.payload)


@adapter.handle(AverCore.call_through_proxy)
def call_through_proxy(wb: AverWorkbench, call: ProxyCall):
    """Call a marker through a specific proxy — may raise TypeError."""
    if wb.current_context is None:
        raise RuntimeError("No adapter created yet")
    proxy = getattr(wb.current_context, call.proxy_name)
    getattr(proxy, call.marker_name)(call.payload)


@adapter.handle(AverCore.execute_failing_assertion)
def execute_failing_assertion(wb: AverWorkbench, spec: FailingAssertionSpec):
    """Replace the assertion handler with one that raises, then call it."""
    if wb.current_context is None:
        raise RuntimeError("No adapter created yet")

    original = wb.current_adapter.handlers[spec.marker_name]

    def failing_handler(ctx, payload):
        raise AssertionError(f"Intentional failure in {spec.marker_name}")

    wb.current_adapter.handlers[spec.marker_name] = (failing_handler, 2)
    try:
        try:
            getattr(wb.current_context.then, spec.marker_name)(spec.payload)
        except AssertionError:
            pass  # Expected — the trace records the failure status
    finally:
        wb.current_adapter.handlers[spec.marker_name] = original


@adapter.handle(AverCore.get_markers)
def get_markers(wb: AverWorkbench, _):
    """Return marker info from the current domain."""
    if wb.current_domain is None:
        return []
    return [
        MarkerInfo(name=m.name, kind=m.kind.value, domain_name=m.domain_name)
        for m in wb.current_domain._aver_markers.values()
    ]


@adapter.handle(AverCore.get_trace)
def get_trace(wb: AverWorkbench, _):
    """Return the inner context's trace."""
    if wb.current_context is None:
        return []
    return wb.current_context.trace()


@adapter.handle(AverCore.get_query_result)
def get_query_result(wb: AverWorkbench, marker_name: str):
    """Return the last query result for a given marker name."""
    return wb.last_query_results.get(marker_name)


@adapter.handle(AverCore.domain_has_marker)
def domain_has_marker(wb: AverWorkbench, check: MarkerCheck):
    """Assert that the current domain has a marker with the given name and kind."""
    markers = wb.current_domain._aver_markers
    assert check.name in markers, f"Domain has no marker '{check.name}'"
    assert markers[check.name].kind.value == check.kind, (
        f"Marker '{check.name}' is {markers[check.name].kind.value}, expected {check.kind}"
    )


@adapter.handle(AverCore.trace_has_entry)
def trace_has_entry(wb: AverWorkbench, check: TraceCheck):
    """Assert that the inner trace has an entry at the given index with expected values."""
    trace = wb.current_context.trace()
    assert check.index < len(trace), (
        f"Trace has {len(trace)} entries, expected at least {check.index + 1}"
    )
    entry = trace[check.index]
    assert entry.category == check.category, (
        f"Trace[{check.index}] category is '{entry.category}', expected '{check.category}'"
    )
    assert entry.status == check.status, (
        f"Trace[{check.index}] status is '{entry.status}', expected '{check.status}'"
    )


@adapter.handle(AverCore.trace_entry_matches)
def trace_entry_matches(wb: AverWorkbench, check: TraceEntryCheck):
    """Assert that a trace entry matches kind, category, and status."""
    trace = wb.current_context.trace()
    assert check.index < len(trace), (
        f"Trace has {len(trace)} entries, expected at least {check.index + 1}"
    )
    entry = trace[check.index]
    assert entry.kind == check.kind, (
        f"Trace[{check.index}] kind is '{entry.kind}', expected '{check.kind}'"
    )
    assert entry.category == check.category, (
        f"Trace[{check.index}] category is '{entry.category}', expected '{check.category}'"
    )
    assert entry.status == check.status, (
        f"Trace[{check.index}] status is '{entry.status}', expected '{check.status}'"
    )


@adapter.handle(AverCore.trace_has_length)
def trace_has_length(wb: AverWorkbench, check: TraceLengthCheck):
    """Assert the trace has exactly the expected number of entries."""
    trace = wb.current_context.trace()
    assert len(trace) == check.expected, (
        f"Trace has {len(trace)} entries, expected {check.expected}"
    )


@adapter.handle(AverCore.query_returned_value)
def query_returned_value(wb: AverWorkbench, check: QueryResultCheck):
    """Assert that a query returned the expected value."""
    actual = wb.last_query_results.get(check.marker_name)
    assert actual == check.expected, (
        f"Query '{check.marker_name}' returned {actual!r}, expected {check.expected!r}"
    )


@adapter.handle(AverCore.has_vocabulary)
def has_vocabulary(wb: AverWorkbench, check: VocabularyCheck):
    """Assert the domain has the expected number of actions, queries, assertions."""
    markers = wb.current_domain._aver_markers
    actual_actions = sum(1 for m in markers.values() if m.kind == MarkerKind.ACTION)
    actual_queries = sum(1 for m in markers.values() if m.kind == MarkerKind.QUERY)
    actual_assertions = sum(1 for m in markers.values() if m.kind == MarkerKind.ASSERTION)

    assert actual_actions == check.actions, (
        f"Expected {check.actions} actions, got {actual_actions}"
    )
    assert actual_queries == check.queries, (
        f"Expected {check.queries} queries, got {actual_queries}"
    )
    assert actual_assertions == check.assertions, (
        f"Expected {check.assertions} assertions, got {actual_assertions}"
    )


@adapter.handle(AverCore.adapter_is_complete)
def adapter_is_complete(wb: AverWorkbench, check: CompletenessCheck):
    """Assert adapter completeness by attempting to build with missing handlers."""
    if not check.missing:
        # Adapter should already be complete
        assert wb.current_adapter is not None, "No adapter created"
    else:
        # Try building an incomplete adapter and verify the error
        incomplete = implement(
            wb.current_domain,
            protocol=unit(lambda: {}, name="incomplete"),
        )
        # Only register handlers for markers NOT in the missing list
        for name, marker in wb.current_domain._aver_markers.items():
            if name not in check.missing:
                @incomplete.handle(marker)
                def stub(ctx, payload):
                    pass

        try:
            incomplete.build()
            assert False, "Expected AdapterError for missing handlers"
        except Exception as e:
            for missing_name in check.missing:
                assert missing_name in str(e), (
                    f"Error should mention missing handler '{missing_name}', got: {e}"
                )


@adapter.handle(AverCore.proxy_rejects_wrong_kind)
def proxy_rejects_wrong_kind(wb: AverWorkbench, check: ProxyRestrictionCheck):
    """Assert that a proxy rejects a marker of the wrong kind."""
    proxy = getattr(wb.current_context, check.proxy_name)
    try:
        getattr(proxy, check.marker_name)("test")
        assert False, f"Expected TypeError from ctx.{check.proxy_name}.{check.marker_name}"
    except TypeError:
        pass  # Expected


# --- Coverage handlers ---

@adapter.handle(AverCore.define_domain_for_coverage)
def define_domain_for_coverage(wb: AverWorkbench, spec: DomainSpec):
    """Create a domain in the coverage workspace."""
    attrs = {}
    for name in spec.actions:
        attrs[name] = action(str)
    for name in spec.queries:
        attrs[name] = query(str, str)
    for name in spec.assertions:
        attrs[name] = assertion(str)

    cls = type(f"CoverageDomain_{spec.name}", (), attrs)
    domain_decorator(spec.name)(cls)
    wb.coverage_domain = cls


@adapter.handle(AverCore.create_adapter_for_coverage)
def create_adapter_for_coverage(wb: AverWorkbench, spec: AdapterSpec):
    """Create an adapter in the coverage workspace."""
    if wb.coverage_domain is None:
        raise RuntimeError("No coverage domain defined yet")

    builder = implement(wb.coverage_domain, protocol=unit(lambda: {}))

    for name, marker in wb.coverage_domain._aver_markers.items():
        if marker.kind == MarkerKind.ACTION:
            @builder.handle(marker)
            def action_handler(ctx, payload, _name=name):
                pass
        elif marker.kind == MarkerKind.QUERY:
            @builder.handle(marker)
            def query_handler(ctx, payload, _name=name):
                return f"result-{_name}"
        elif marker.kind == MarkerKind.ASSERTION:
            @builder.handle(marker)
            def assertion_handler(ctx, payload, _name=name):
                pass

    wb.coverage_adapter = builder.build()
    inner_ctx = wb.coverage_adapter.protocol.setup()
    wb.coverage_context = Context(wb.coverage_domain, wb.coverage_adapter, inner_ctx)


@adapter.handle(AverCore.call_coverage_operation)
def call_coverage_operation(wb: AverWorkbench, op: OperationCall):
    """Call a domain operation in the coverage workspace."""
    if wb.coverage_context is None:
        raise RuntimeError("No coverage adapter created yet")
    marker = wb.coverage_domain._aver_markers[op.marker_name]
    if marker.kind == MarkerKind.ACTION:
        getattr(wb.coverage_context.when, op.marker_name)(op.payload)
    elif marker.kind == MarkerKind.QUERY:
        getattr(wb.coverage_context.query, op.marker_name)(op.payload)
    elif marker.kind == MarkerKind.ASSERTION:
        getattr(wb.coverage_context.then, op.marker_name)(op.payload)


@adapter.handle(AverCore.get_coverage_percentage)
def get_coverage_percentage(wb: AverWorkbench, _):
    """Return coverage percentage from the coverage workspace."""
    if wb.coverage_context is None:
        return 100  # No domain = 100%
    coverage = wb.coverage_context.get_coverage()
    return coverage["percentage"]


@adapter.handle(AverCore.coverage_is)
def coverage_is(wb: AverWorkbench, check: CoverageCheck):
    """Assert that coverage percentage matches expected."""
    if wb.coverage_context is None:
        actual = 100
    else:
        actual = wb.coverage_context.get_coverage()["percentage"]
    assert actual == check.expected_percentage, (
        f"Coverage is {actual}%, expected {check.expected_percentage}%"
    )


# --- Telemetry handlers ---

class _StubCollector(TelemetryCollector):
    """In-memory telemetry collector for testing."""

    def __init__(self):
        self._spans: list[CollectedSpan] = []

    def get_spans(self) -> list[CollectedSpan]:
        return list(self._spans)

    def reset(self) -> None:
        self._spans.clear()

    def add_span(self, span: CollectedSpan) -> None:
        self._spans.append(span)


class _TelemetryProtocol(Protocol):
    """Protocol with a telemetry collector attached."""
    name = "telemetry-test"

    def __init__(self):
        self.telemetry = _StubCollector()

    def setup(self):
        return {}

    def teardown(self, ctx):
        pass


@adapter.handle(AverCore.define_telemetry_domain)
def define_telemetry_domain(wb: AverWorkbench, spec: TelemetryDomainSpec):
    """Create a domain with telemetry declarations."""
    attrs = {}
    for act_name, span_name in zip(spec.actions, spec.span_names):
        attrs[act_name] = action(str, telemetry=TelemetryExpectation(span=span_name))

    cls = type(f"TelemetryDomain_{spec.name}", (), attrs)
    domain_decorator(spec.name)(cls)
    wb.telemetry_domain = cls


@adapter.handle(AverCore.create_telemetry_adapter)
def create_telemetry_adapter(wb: AverWorkbench, _):
    """Create an adapter with a telemetry collector for the telemetry domain."""
    if wb.telemetry_domain is None:
        raise RuntimeError("No telemetry domain defined yet")

    proto = _TelemetryProtocol()
    wb.telemetry_collector = proto.telemetry

    builder = implement(wb.telemetry_domain, protocol=proto)

    for name, marker in wb.telemetry_domain._aver_markers.items():
        tel = marker.telemetry

        @builder.handle(marker)
        def handler(ctx, payload, _tel=tel, _collector=wb.telemetry_collector):
            # Simulate: the adapter injects a matching span
            if _tel is not None and isinstance(_tel, TelemetryExpectation):
                _collector.add_span(CollectedSpan(
                    trace_id="trace-001",
                    span_id=f"span-{_tel.span}",
                    name=_tel.span,
                    attributes=dict(_tel.attributes),
                ))

    wb.telemetry_adapter = builder.build()
    inner_ctx = wb.telemetry_adapter.protocol.setup()
    wb.telemetry_context = Context(wb.telemetry_domain, wb.telemetry_adapter, inner_ctx)


@adapter.handle(AverCore.call_telemetry_operation)
def call_telemetry_operation(wb: AverWorkbench, op: OperationCall):
    """Call an operation through the telemetry context."""
    if wb.telemetry_context is None:
        raise RuntimeError("No telemetry adapter created yet")
    marker = wb.telemetry_domain._aver_markers[op.marker_name]
    if marker.kind == MarkerKind.ACTION:
        getattr(wb.telemetry_context.when, op.marker_name)(op.payload)


@adapter.handle(AverCore.telemetry_span_matched)
def telemetry_span_matched(wb: AverWorkbench, check: TelemetrySpanCheck):
    """Assert that a trace entry has a telemetry match result."""
    if wb.telemetry_context is None:
        raise RuntimeError("No telemetry context")
    trace = wb.telemetry_context.trace()
    assert check.index < len(trace), (
        f"Trace has {len(trace)} entries, expected at least {check.index + 1}"
    )
    entry = trace[check.index]
    assert entry.telemetry is not None, (
        f"Trace[{check.index}] has no telemetry result"
    )
    assert entry.telemetry.expected.span == check.expected_span, (
        f"Expected span '{check.expected_span}', got '{entry.telemetry.expected.span}'"
    )
    assert entry.telemetry.matched == check.matched, (
        f"Expected matched={check.matched}, got matched={entry.telemetry.matched}"
    )


# --- Extension handlers ---

@adapter.handle(AverCore.extend_domain)
def extend_domain(wb: AverWorkbench, spec: ExtensionSpec):
    """Extend the current domain with new markers."""
    if wb.current_domain is None:
        raise RuntimeError("No domain defined yet")

    new_actions = {n: action(str) for n in spec.new_actions}
    new_queries = {n: query(str, str) for n in spec.new_queries}
    new_assertions = {n: assertion(str) for n in spec.new_assertions}

    wb.extended_domain = wb.current_domain.extend(
        spec.child_name,
        actions=new_actions,
        queries=new_queries,
        assertions=new_assertions,
    )


@adapter.handle(AverCore.get_extension_markers)
def get_extension_markers(wb: AverWorkbench, _):
    """Return marker info from the extended domain."""
    if wb.extended_domain is None:
        return []
    return [
        MarkerInfo(name=m.name, kind=m.kind.value, domain_name=m.domain_name)
        for m in wb.extended_domain._aver_markers.values()
    ]


@adapter.handle(AverCore.extension_has_markers)
def extension_has_markers(wb: AverWorkbench, check: ExtensionMarkerCheck):
    """Assert the extended domain has both parent and child markers."""
    if wb.extended_domain is None:
        raise RuntimeError("No extended domain")

    marker_names = set(wb.extended_domain._aver_markers.keys())

    for name in check.parent_marker_names:
        assert name in marker_names, (
            f"Extended domain missing parent marker '{name}'. Has: {marker_names}"
        )

    for name in check.child_marker_names:
        assert name in marker_names, (
            f"Extended domain missing child marker '{name}'. Has: {marker_names}"
        )
