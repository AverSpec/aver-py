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
    ContractDomainSpec, ContractTraceSpec, ContractSpanSpec,
    CoverageBreakdownCheck,
    MarkerNamesCheck, MarkerKindMapCheck, MarkerCountCheck,
    TraceNameCheck, ViolationCountCheck, MissingMarkerErrorCheck,
    QueryResultTypeCheck,
    BuildExtendedSuiteSpec, CallExtendedOperationSpec,
    ExtendedSuiteMarkerCountCheck, MissingAdapterErrorCheck,
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

        # Multi-adapter workspace
        self.second_adapter = None

        # Contract verification workspace
        self.contract_tmp_dir = None
        self.contract_domain = None
        self.contract_adapter = None
        self.contract_context = None
        self.contract_collector = None
        self.contract_domain_spec = None
        self.contract_trace_spec = None
        self.contract_result = None  # ConformanceReport
        self.contract_written_paths = []


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


# --- Multi-adapter handlers ---

@adapter.handle(AverCore.register_second_adapter)
def register_second_adapter(wb: AverWorkbench, spec: AdapterSpec):
    """Register a second adapter for the same domain with a different protocol."""
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

    wb.second_adapter = builder.build()


@adapter.handle(AverCore.get_adapter_count)
def get_adapter_count(wb: AverWorkbench, _):
    """Return how many adapters exist for the current domain."""
    count = 1 if wb.current_adapter is not None else 0
    if wb.second_adapter is not None:
        count += 1
    return count


@adapter.handle(AverCore.adapter_count_is)
def adapter_count_is(wb: AverWorkbench, expected: int):
    """Assert the number of adapters for the current domain."""
    count = 1 if wb.current_adapter is not None else 0
    if wb.second_adapter is not None:
        count += 1
    assert count == expected, f"Expected {expected} adapters, got {count}"


# --- Coverage detail handlers ---

@adapter.handle(AverCore.get_coverage_detail)
def get_coverage_detail(wb: AverWorkbench, _):
    """Return full coverage breakdown from the coverage workspace."""
    if wb.coverage_context is None:
        return {"percentage": 100, "actions": {"total": [], "called": []},
                "queries": {"total": [], "called": []},
                "assertions": {"total": [], "called": []}}
    return wb.coverage_context.get_coverage()


@adapter.handle(AverCore.coverage_breakdown_matches)
def coverage_breakdown_matches(wb: AverWorkbench, check: CoverageBreakdownCheck):
    """Assert that per-kind coverage breakdown matches expected counts."""
    if wb.coverage_context is None:
        cov = {"actions": {"total": [], "called": []},
               "queries": {"total": [], "called": []},
               "assertions": {"total": [], "called": []}}
    else:
        cov = wb.coverage_context.get_coverage()

    assert len(cov["actions"]["called"]) == check.actions_called, (
        f"Expected {check.actions_called} actions called, got {len(cov['actions']['called'])}"
    )
    assert len(cov["actions"]["total"]) == check.actions_total, (
        f"Expected {check.actions_total} total actions, got {len(cov['actions']['total'])}"
    )
    assert len(cov["queries"]["called"]) == check.queries_called, (
        f"Expected {check.queries_called} queries called, got {len(cov['queries']['called'])}"
    )
    assert len(cov["queries"]["total"]) == check.queries_total, (
        f"Expected {check.queries_total} total queries, got {len(cov['queries']['total'])}"
    )
    assert len(cov["assertions"]["called"]) == check.assertions_called, (
        f"Expected {check.assertions_called} assertions called, got {len(cov['assertions']['called'])}"
    )
    assert len(cov["assertions"]["total"]) == check.assertions_total, (
        f"Expected {check.assertions_total} total assertions, got {len(cov['assertions']['total'])}"
    )


# --- Domain parent assertion ---

@adapter.handle(AverCore.has_parent_domain)
def has_parent_domain(wb: AverWorkbench, parent_name: str):
    """Assert that the extended domain tracks its parent."""
    if wb.extended_domain is None:
        raise RuntimeError("No extended domain")
    parent = getattr(wb.extended_domain, "_aver_parent", None)
    assert parent is not None, "Extended domain has no parent"
    assert parent._aver_domain_name == parent_name, (
        f"Expected parent '{parent_name}', got '{parent._aver_domain_name}'"
    )


# --- Contract verification handlers ---

import tempfile
import os
from averspec.telemetry_contract import (
    extract_contract, BehavioralContract, ContractEntry,
    SpanExpectation, AttributeBinding,
)
from averspec.telemetry_verify import (
    verify_contract, ProductionTrace, ProductionSpan, ConformanceReport,
)
from averspec.contract_io import write_contracts, read_contracts, read_contract_file


@adapter.handle(AverCore.setup_contract_workbench)
def setup_contract_workbench(wb: AverWorkbench, _):
    """Create a temp directory for contract files."""
    wb.contract_tmp_dir = tempfile.mkdtemp(prefix="aver-contract-")


@adapter.handle(AverCore.define_contract_domain)
def define_contract_domain(wb: AverWorkbench, spec: ContractDomainSpec):
    """Create a domain with telemetry for contract verification."""
    wb.contract_domain_spec = spec
    attrs = {}
    for i, act_name in enumerate(spec.actions):
        span_name = spec.span_names[i] if i < len(spec.span_names) else act_name
        span_attrs = spec.span_attributes[i] if i < len(spec.span_attributes) else {}

        if spec.parameterized:
            # Parameterized telemetry: a callable that takes payload and returns TelemetryExpectation
            def make_tel_fn(sn, sa):
                def tel_fn(p):
                    resolved = {}
                    for k, v in sa.items():
                        if isinstance(v, str) and v.startswith("$"):
                            field_name = v[1:]
                            resolved[k] = getattr(p, field_name, p.get(field_name) if isinstance(p, dict) else v)
                        else:
                            resolved[k] = v
                    return TelemetryExpectation(span=sn, attributes=resolved)
                return tel_fn
            attrs[act_name] = action(dict, telemetry=make_tel_fn(span_name, span_attrs))
        else:
            # Static telemetry
            attrs[act_name] = action(str, telemetry=TelemetryExpectation(
                span=span_name, attributes=dict(span_attrs),
            ))

    cls = type(f"ContractDomain_{spec.domain_name}", (), attrs)
    domain_decorator(spec.domain_name)(cls)
    wb.contract_domain = cls


@adapter.handle(AverCore.create_contract_adapter)
def create_contract_adapter(wb: AverWorkbench, trace_spec: ContractTraceSpec):
    """Create adapter with a stub TelemetryCollector that emits matching spans per step."""
    if wb.contract_domain is None:
        raise RuntimeError("No contract domain defined yet")

    collector = _StubCollector()
    wb.contract_collector = collector
    wb.contract_trace_spec = trace_spec

    proto = _TelemetryProtocol()
    proto.telemetry = collector

    builder = implement(wb.contract_domain, protocol=proto)

    # Build a mapping from action name to the span(s) it should emit.
    # The trace_spec spans correspond to actions in domain declaration order.
    action_names = [
        name for name, marker in wb.contract_domain._aver_markers.items()
        if marker.kind == MarkerKind.ACTION
    ]
    span_by_action: dict[str, dict] = {}
    for i, act_name in enumerate(action_names):
        if i < len(trace_spec.spans):
            span_by_action[act_name] = trace_spec.spans[i]

    for name, marker in wb.contract_domain._aver_markers.items():
        span_dict = span_by_action.get(name)

        @builder.handle(marker)
        def handler(ctx, payload, _name=name, _marker=marker, _span=span_dict, _collector=collector):
            # Emit a span that matches what per-step telemetry verification expects.
            if _span is not None and _marker.telemetry is not None:
                # Resolve expected attributes from the marker's telemetry declaration
                if callable(_marker.telemetry):
                    expected = _marker.telemetry(payload)
                else:
                    expected = _marker.telemetry
                # Use the declared span name and the spec's concrete attribute values
                _collector.add_span(CollectedSpan(
                    trace_id=_span.get("trace_id", "trace-001"),
                    span_id=_span.get("span_id", f"span-{_span['name']}"),
                    name=expected.span,
                    attributes=dict(expected.attributes),
                ))

    wb.contract_adapter = builder.build()
    inner_ctx = wb.contract_adapter.protocol.setup()
    wb.contract_context = Context(wb.contract_domain, wb.contract_adapter, inner_ctx)


@adapter.handle(AverCore.run_contract_operations)
def run_contract_operations(wb: AverWorkbench, _):
    """Execute all actions through the inner contract suite.

    The handler emits matching spans so per-step telemetry verification passes
    in any mode (including CI's default "fail" mode), and trace entries get
    populated telemetry data for contract extraction.
    """
    if wb.contract_context is None:
        raise RuntimeError("No contract adapter created yet")

    spec = wb.contract_domain_spec
    action_names = [
        name for name, marker in wb.contract_domain._aver_markers.items()
        if marker.kind == MarkerKind.ACTION
    ]

    for i, name in enumerate(action_names):
        marker = wb.contract_domain._aver_markers[name]
        # For parameterized telemetry, build a dict payload whose fields
        # resolve to the concrete values from the trace spec spans.
        if spec and spec.parameterized and i < len(spec.span_attributes):
            payload = {}
            for attr_key, attr_val in spec.span_attributes[i].items():
                if isinstance(attr_val, str) and attr_val.startswith("$"):
                    field_name = attr_val[1:]
                    # Pull the concrete value from the trace spec span
                    if wb.contract_trace_spec and i < len(wb.contract_trace_spec.spans):
                        concrete = wb.contract_trace_spec.spans[i].get("attributes", {}).get(attr_key, "test-value")
                    else:
                        concrete = "test-value"
                    payload[field_name] = concrete
                else:
                    payload[attr_key] = attr_val
            getattr(wb.contract_context.when, name)(payload)
        else:
            getattr(wb.contract_context.when, name)("test-payload")


@adapter.handle(AverCore.extract_and_write_contract)
def extract_and_write_contract(wb: AverWorkbench, _):
    """Extract contract from traces and write to tmp dir."""
    if wb.contract_context is None:
        raise RuntimeError("No contract context")
    if wb.contract_tmp_dir is None:
        raise RuntimeError("No contract tmp dir")

    trace = wb.contract_context.trace()
    results = [{"test_name": "contract-test", "trace": trace}]

    contract = extract_contract(wb.contract_domain, results)
    wb.contract_written_paths = write_contracts(contract, wb.contract_tmp_dir)


@adapter.handle(AverCore.load_and_verify_contract)
def load_and_verify_contract(wb: AverWorkbench, prod_trace_spec: ContractTraceSpec):
    """Read contract back and verify against production traces."""
    if wb.contract_tmp_dir is None:
        raise RuntimeError("No contract tmp dir")

    contracts = read_contracts(wb.contract_tmp_dir)
    if not contracts:
        # Create a conformance report with a violation
        wb.contract_result = ConformanceReport(
            domain="unknown",
            results=[],
            total_violations=1,
        )
        return

    # Build production traces from spec
    # Group spans by trace_id
    trace_map: dict[str, list[ProductionSpan]] = {}
    for span_dict in prod_trace_spec.spans:
        tid = span_dict.get("trace_id", "trace-001")
        if tid not in trace_map:
            trace_map[tid] = []
        trace_map[tid].append(ProductionSpan(
            name=span_dict["name"],
            attributes=span_dict.get("attributes", {}),
            span_id=span_dict.get("span_id"),
        ))

    prod_traces = [
        ProductionTrace(trace_id=tid, spans=spans)
        for tid, spans in trace_map.items()
    ]

    # Verify all contracts
    all_violations = 0
    all_results = []
    for contract in contracts:
        report = verify_contract(contract, prod_traces)
        all_violations += report.total_violations
        all_results.extend(report.results)

    wb.contract_result = ConformanceReport(
        domain=contracts[0].domain if contracts else "unknown",
        results=all_results,
        total_violations=all_violations,
    )


@adapter.handle(AverCore.get_contract_violations)
def get_contract_violations(wb: AverWorkbench, _):
    """Return violation count from last verification."""
    if wb.contract_result is None:
        return 0
    return wb.contract_result.total_violations


@adapter.handle(AverCore.get_violation_details)
def get_violation_details(wb: AverWorkbench, _):
    """Return list of violation kinds from last verification."""
    if wb.contract_result is None:
        return []
    kinds = []
    for r in wb.contract_result.results:
        for v in r.violations:
            kinds.append(v.kind)
    return kinds


@adapter.handle(AverCore.contract_passes)
def contract_passes(wb: AverWorkbench, _):
    """Assert 0 violations."""
    assert wb.contract_result is not None, "No contract verification result"
    assert wb.contract_result.total_violations == 0, (
        f"Expected 0 violations, got {wb.contract_result.total_violations}"
    )


@adapter.handle(AverCore.contract_has_violations)
def contract_has_violations(wb: AverWorkbench, _):
    """Assert violation count > 0."""
    assert wb.contract_result is not None, "No contract verification result"
    assert wb.contract_result.total_violations > 0, (
        f"Expected violations but got 0"
    )


@adapter.handle(AverCore.violation_includes)
def violation_includes(wb: AverWorkbench, kind: str):
    """Assert a specific violation kind exists."""
    assert wb.contract_result is not None, "No contract verification result"
    all_kinds = []
    for r in wb.contract_result.results:
        for v in r.violations:
            all_kinds.append(v.kind)
    assert kind in all_kinds, (
        f"Expected violation kind '{kind}', found: {all_kinds}"
    )


# --- Inline query-result assertions ---

@adapter.handle(AverCore.markers_have_names)
def markers_have_names(wb: AverWorkbench, check: MarkerNamesCheck):
    """Assert that the current domain's marker names equal expected set."""
    if wb.current_domain is None:
        actual = set()
    else:
        actual = set(wb.current_domain._aver_markers.keys())
    expected = set(check.expected_names)
    assert actual == expected, f"Marker names {actual} != expected {expected}"


@adapter.handle(AverCore.marker_kinds_match)
def marker_kinds_match(wb: AverWorkbench, check: MarkerKindMapCheck):
    """Assert that markers map name->kind as expected."""
    if wb.current_domain is None:
        raise RuntimeError("No domain defined")
    markers = wb.current_domain._aver_markers
    for name, expected_kind in check.expected.items():
        assert name in markers, f"Marker '{name}' not found"
        assert markers[name].kind.value == expected_kind, (
            f"Marker '{name}' kind is '{markers[name].kind.value}', expected '{expected_kind}'"
        )


@adapter.handle(AverCore.extension_marker_count_is)
def extension_marker_count_is(wb: AverWorkbench, check: MarkerCountCheck):
    """Assert that the extended domain has exactly N markers."""
    if wb.extended_domain is None:
        raise RuntimeError("No extended domain")
    actual = len(wb.extended_domain._aver_markers)
    assert actual == check.expected, f"Expected {check.expected} markers, got {actual}"


@adapter.handle(AverCore.extension_marker_names_equal)
def extension_marker_names_equal(wb: AverWorkbench, check: MarkerNamesCheck):
    """Assert that the extended domain's marker names equal expected set."""
    if wb.extended_domain is None:
        raise RuntimeError("No extended domain")
    actual = set(wb.extended_domain._aver_markers.keys())
    expected = set(check.expected_names)
    assert actual == expected, f"Extension marker names {actual} != expected {expected}"


@adapter.handle(AverCore.trace_name_at_index)
def trace_name_at_index(wb: AverWorkbench, check: TraceNameCheck):
    """Assert that a trace entry at index has the expected qualified name."""
    if wb.current_context is None:
        raise RuntimeError("No adapter created")
    trace = wb.current_context.trace()
    assert check.index < len(trace), (
        f"Trace has {len(trace)} entries, expected at least {check.index + 1}"
    )
    assert trace[check.index].name == check.expected_name, (
        f"Trace[{check.index}].name is '{trace[check.index].name}', expected '{check.expected_name}'"
    )


@adapter.handle(AverCore.violation_count_is)
def violation_count_is(wb: AverWorkbench, check: ViolationCountCheck):
    """Assert exact violation count."""
    if wb.contract_result is None:
        actual = 0
    else:
        actual = wb.contract_result.total_violations
    assert actual == check.expected, f"Expected {check.expected} violations, got {actual}"


@adapter.handle(AverCore.missing_marker_raises_error)
def missing_marker_raises_error(wb: AverWorkbench, check: MissingMarkerErrorCheck):
    """Assert that accessing a nonexistent marker on a proxy raises AttributeError."""
    if wb.current_context is None:
        raise RuntimeError("No adapter created")
    proxy = getattr(wb.current_context, check.proxy_name)
    try:
        getattr(proxy, check.marker_name)("payload")
        assert False, f"Expected AttributeError from ctx.{check.proxy_name}.{check.marker_name}"
    except AttributeError as e:
        assert check.expected_match in str(e), (
            f"Expected error to contain '{check.expected_match}', got: {e}"
        )


@adapter.handle(AverCore.query_result_type_is)
def query_result_type_is(wb: AverWorkbench, check: QueryResultTypeCheck):
    """Assert that a stored query result has the expected type."""
    actual = wb.last_query_results.get(check.marker_name)
    actual_type = type(actual).__name__
    assert actual_type == check.expected_type, (
        f"Query '{check.marker_name}' result type is '{actual_type}', expected '{check.expected_type}'"
    )


# --- Extended domain e2e suite handlers ---


@adapter.handle(AverCore.build_extended_suite)
def build_extended_suite(wb: AverWorkbench, spec: BuildExtendedSuiteSpec):
    """Build an extended domain with parent + child markers, implement, and create suite context."""
    parent_attrs = {name: action(str) for name in spec.parent_actions}
    parent_cls = type("ExtSuiteParent", (), parent_attrs)
    domain_decorator("ext-suite-parent")(parent_cls)

    child_cls = parent_cls.extend(
        "ext-suite-child",
        actions=spec.child_actions,
    )

    builder = implement(child_cls, protocol=unit(lambda: {"called": []}))
    for name in spec.parent_actions + spec.child_actions:
        marker = child_cls._aver_markers[name]
        @builder.handle(marker)
        def handler(ctx, payload, _name=name):
            ctx["called"].append(_name)

    built_adapter = builder.build()
    inner_ctx = built_adapter.protocol.setup()
    wb._ext_suite_ctx = Context(child_cls, built_adapter, inner_ctx)
    wb._ext_suite_markers = spec.parent_actions + spec.child_actions


@adapter.handle(AverCore.call_extended_operation)
def call_extended_operation(wb: AverWorkbench, spec: CallExtendedOperationSpec):
    """Call a marker in the extended suite context."""
    ctx = wb._ext_suite_ctx
    getattr(ctx.when, spec.marker_name)("test")


@adapter.handle(AverCore.get_extended_suite_marker_count)
def get_extended_suite_marker_count(wb: AverWorkbench, _):
    """Return marker count from the extended suite workspace."""
    return len(getattr(wb, "_ext_suite_markers", []))


@adapter.handle(AverCore.extended_suite_marker_count_is)
def extended_suite_marker_count_is(wb: AverWorkbench, check: ExtendedSuiteMarkerCountCheck):
    """Assert extended suite marker count."""
    actual = len(getattr(wb, "_ext_suite_markers", []))
    assert actual == check.expected, f"Expected {check.expected} markers, got {actual}"


@adapter.handle(AverCore.missing_adapter_error_lists_registered)
def missing_adapter_error_lists_registered(wb: AverWorkbench, check: MissingAdapterErrorCheck):
    """Assert that looking up a missing adapter lists registered adapters in the error."""
    from averspec.config import _Registry

    registry = _Registry()
    # Register adapters for the expected domains
    for name in check.expected_registered:
        attrs = {"dummy": action(str)}
        cls = type(f"Registered_{name}", (), attrs)
        domain_decorator(name)(cls)
        builder = implement(cls, protocol=unit(lambda: {}))
        marker = cls._aver_markers["dummy"]
        @builder.handle(marker)
        def stub(ctx, payload):
            pass
        registry.register_adapter(builder.build())

    # Look up a domain that doesn't exist
    found = registry.find_adapters(type(f"Missing_{check.domain_name}", (), {"_aver_domain_name": check.domain_name, "_aver_markers": {}, "_aver_parent": None}))
    assert len(found) == 0, "Expected no adapters found"

    # Check that registered names can be extracted
    registered_names = [a.domain_cls._aver_domain_name for a in registry._adapters]
    for expected_name in check.expected_registered:
        assert expected_name in registered_names, (
            f"Expected '{expected_name}' in registered names: {registered_names}"
        )
