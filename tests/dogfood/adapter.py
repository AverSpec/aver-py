"""Dogfood adapter: exercises aver-py through its own public API."""

from averspec import implement, unit, domain as domain_decorator, action, query, assertion
from averspec.adapter import AdapterBuilder
from averspec.suite import Context, NarrativeProxy
from averspec.domain import Marker, MarkerKind
from averspec.trace import TraceEntry
from tests.dogfood.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall, ProxyCall,
    MarkerCheck, TraceCheck, ProxyRestrictionCheck, CompletenessCheck,
    MarkerInfo,
)


class AverWorkbench:
    """Context object: a workspace for creating and testing aver constructs."""

    def __init__(self):
        self.current_domain = None
        self.current_adapter = None
        self.current_builder = None
        self.current_context = None  # a Context from the inner domain
        self.inner_trace = []


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
    getattr(wb.current_context.when, op.marker_name)(op.payload)


@adapter.handle(AverCore.call_through_proxy)
def call_through_proxy(wb: AverWorkbench, call: ProxyCall):
    """Call a marker through a specific proxy — may raise TypeError."""
    if wb.current_context is None:
        raise RuntimeError("No adapter created yet")
    proxy = getattr(wb.current_context, call.proxy_name)
    getattr(proxy, call.marker_name)(call.payload)


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
