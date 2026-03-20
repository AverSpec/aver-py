"""Tests for TraceEntry structure and recording.

Ported from packages/core/test/core/trace-format.spec.ts — validates
TraceEntry dataclass fields and how entries are produced by NarrativeProxy.
"""

import pytest
from averspec.domain import domain, action, query, assertion
from averspec.adapter import implement
from averspec.protocol import unit
from averspec.suite import Context
from averspec.trace import TraceEntry


# ---------------------------------------------------------------------------
# Inline domain + adapter
# ---------------------------------------------------------------------------

@domain("Trace")
class TraceDomain:
    add_item = action(dict)
    checkout = action()
    total_charged = assertion(dict)
    get_val = query(type(None), int)


def _make_trace_adapter():
    proto = unit(lambda: {})
    builder = implement(TraceDomain, protocol=proto)

    @builder.handle(TraceDomain.add_item)
    def add_item(ctx, payload):
        pass

    @builder.handle(TraceDomain.checkout)
    def checkout(ctx):
        pass

    @builder.handle(TraceDomain.total_charged)
    def total_charged(ctx, payload):
        pass

    @builder.handle(TraceDomain.get_val)
    def get_val(ctx):
        return 99

    return builder.build(), proto


@domain("Boom")
class BoomDomain:
    setup = action()
    check = assertion()


def _make_boom_adapter():
    proto = unit(lambda: {})
    builder = implement(BoomDomain, protocol=proto)

    @builder.handle(BoomDomain.setup)
    def setup(ctx):
        pass

    @builder.handle(BoomDomain.check)
    def check(ctx):
        raise ValueError("boom")

    return builder.build(), proto


def _ctx(domain_cls, adapter, proto):
    protocol_ctx = proto.setup()
    return Context(domain_cls, adapter, protocol_ctx)


# ---------------------------------------------------------------------------
# TraceEntry dataclass structure
# ---------------------------------------------------------------------------

class TestTraceEntryStructure:
    def test_trace_entry_has_required_fields(self):
        entry = TraceEntry(
            kind="action",
            category="when",
            name="Cart.add_item",
            payload={"name": "Widget"},
            status="pass",
        )
        assert entry.kind == "action"
        assert entry.category == "when"
        assert entry.name == "Cart.add_item"
        assert entry.payload == {"name": "Widget"}
        assert entry.status == "pass"

    def test_trace_entry_defaults(self):
        entry = TraceEntry(kind="action", category="act", name="Cart.go")
        assert entry.payload is None
        assert entry.status == "pass"
        assert entry.duration_ms == 0.0
        assert entry.result is None
        assert entry.error is None

    def test_trace_entry_stores_result(self):
        entry = TraceEntry(
            kind="query",
            category="query",
            name="Cart.total",
            result=42,
        )
        assert entry.result == 42

    def test_trace_entry_stores_error(self):
        entry = TraceEntry(
            kind="assertion",
            category="then",
            name="Cart.check",
            status="fail",
            error="boom",
        )
        assert entry.error == "boom"
        assert entry.status == "fail"


# ---------------------------------------------------------------------------
# Category labels in recorded trace
# ---------------------------------------------------------------------------

class TestCategoryLabels:
    def test_given_when_then_categories(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.given.add_item({"name": "Widget"})
        ctx.when.checkout()
        ctx.then.total_charged({"amount": 35})

        trace = ctx.trace()
        assert len(trace) == 3
        assert trace[0].category == "given"
        assert trace[0].kind == "action"
        assert trace[0].name == "Trace.add_item"

        assert trace[1].category == "when"
        assert trace[1].kind == "action"
        assert trace[1].name == "Trace.checkout"

        assert trace[2].category == "then"
        assert trace[2].kind == "assertion"
        assert trace[2].name == "Trace.total_charged"

    def test_query_category(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.query.get_val()

        trace = ctx.trace()
        assert len(trace) == 1
        assert trace[0].category == "query"
        assert trace[0].kind == "query"


# ---------------------------------------------------------------------------
# Pass / fail status recording
# ---------------------------------------------------------------------------

class TestStatusRecording:
    def test_pass_status_on_success(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.given.add_item({"name": "Setup"})

        trace = ctx.trace()
        assert trace[0].status == "pass"

    def test_fail_status_on_error(self):
        adapter, proto = _make_boom_adapter()
        ctx = _ctx(BoomDomain, adapter, proto)

        ctx.given.setup()
        with pytest.raises(ValueError, match="boom"):
            ctx.then.check()

        trace = ctx.trace()
        assert len(trace) == 2
        assert trace[0].status == "pass"
        assert trace[1].status == "fail"
        assert "boom" in trace[1].error

    def test_error_field_only_set_on_failure(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.when.checkout()

        trace = ctx.trace()
        assert trace[0].error is None


# ---------------------------------------------------------------------------
# Duration tracking
# ---------------------------------------------------------------------------

class TestDurationTracking:
    def test_duration_is_non_negative(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.when.add_item({"name": "test"})

        trace = ctx.trace()
        assert trace[0].duration_ms >= 0

    def test_duration_recorded_on_failure(self):
        adapter, proto = _make_boom_adapter()
        ctx = _ctx(BoomDomain, adapter, proto)

        with pytest.raises(ValueError):
            ctx.then.check()

        trace = ctx.trace()
        assert trace[0].duration_ms >= 0


# ---------------------------------------------------------------------------
# Payload recording
# ---------------------------------------------------------------------------

class TestPayloadRecording:
    def test_records_payload(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.when.add_item({"name": "Widget"})

        trace = ctx.trace()
        assert trace[0].payload == {"name": "Widget"}

    def test_none_payload_when_no_args(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.when.checkout()

        trace = ctx.trace()
        assert trace[0].payload is None

    def test_result_recorded_for_queries(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        result = ctx.query.get_val()

        trace = ctx.trace()
        assert result == 99
        assert trace[0].result == 99

    def test_result_not_set_for_actions(self):
        adapter, proto = _make_trace_adapter()
        ctx = _ctx(TraceDomain, adapter, proto)

        ctx.when.checkout()

        trace = ctx.trace()
        assert trace[0].result is None
