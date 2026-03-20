"""Tests for Suite, Context, and narrative proxies.

Ported from packages/core/test/core/suite.spec.ts — tests framework
internals directly via Context, not through the pytest plugin.
"""

import pytest
from averspec.domain import domain, action, query, assertion, MarkerKind
from averspec.adapter import implement, Adapter
from averspec.protocol import unit
from averspec.suite import Suite, Context, NarrativeProxy
from averspec.trace import TraceEntry


# ---------------------------------------------------------------------------
# Inline domain + adapter factories
# ---------------------------------------------------------------------------

@domain("Cart")
class Cart:
    add_item = action(dict)
    total = query(type(None), int)
    is_empty = assertion()


def _make_cart_adapter():
    """Build a Cart adapter backed by a dict context."""
    proto = unit(lambda: {"calls": []})
    builder = implement(Cart, protocol=proto)

    @builder.handle(Cart.add_item)
    def add_item(ctx, payload):
        ctx["calls"].append(f"add:{payload['name']}")

    @builder.handle(Cart.total)
    def total(ctx):
        return 42

    @builder.handle(Cart.is_empty)
    def is_empty(ctx):
        pass

    return builder.build(), proto


@domain("Fail")
class FailDomain:
    check = assertion()


def _make_fail_adapter():
    proto = unit(lambda: {})
    builder = implement(FailDomain, protocol=proto)

    @builder.handle(FailDomain.check)
    def check(ctx):
        raise RuntimeError("boom")

    return builder.build(), proto


@domain("Filter")
class FilterDomain:
    items_by_status = query(dict, list)


def _make_filter_adapter():
    items = {"active": ["a", "b"], "done": ["c"]}
    proto = unit(lambda: {})
    builder = implement(FilterDomain, protocol=proto)

    @builder.handle(FilterDomain.items_by_status)
    def items_by_status(ctx, payload):
        return items.get(payload["status"], [])

    return builder.build(), proto


@domain("ActionOnly")
class ActionOnlyDomain:
    fire = action()
    fired = assertion()


def _make_action_only_adapter():
    state = {"fired": False}
    proto = unit(lambda: state)
    builder = implement(ActionOnlyDomain, protocol=proto)

    @builder.handle(ActionOnlyDomain.fire)
    def fire(ctx):
        ctx["fired"] = True

    @builder.handle(ActionOnlyDomain.fired)
    def fired(ctx):
        if not ctx["fired"]:
            raise AssertionError("fire() was not called")

    return builder.build(), proto


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(domain_cls, adapter, proto):
    """Set up protocol and return a fresh Context."""
    protocol_ctx = proto.setup()
    return Context(domain_cls, adapter, protocol_ctx), protocol_ctx


# ---------------------------------------------------------------------------
# Suite creation
# ---------------------------------------------------------------------------

class TestSuiteCreation:
    def test_suite_requires_domain_class(self):
        with pytest.raises(TypeError, match="not a domain"):
            Suite(object)

    def test_suite_accepts_domain_class(self):
        s = Suite(Cart)
        assert s.domain_cls is Cart

    def test_suite_test_decorator_requires_test_prefix(self):
        s = Suite(Cart)
        with pytest.raises(ValueError, match="must start with 'test_'"):
            @s.test
            def bad_name(ctx):
                pass

    def test_suite_test_decorator_marks_function(self):
        s = Suite(Cart)

        @s.test
        def test_something(ctx):
            pass

        assert test_something._aver_suite is s


# ---------------------------------------------------------------------------
# Dispatching through Context proxies
# ---------------------------------------------------------------------------

class TestDispatch:
    def test_dispatches_actions_through_when(self):
        adapter, proto = _make_cart_adapter()
        ctx, protocol_ctx = _ctx(Cart, adapter, proto)

        ctx.when.add_item({"name": "Widget"})
        assert "add:Widget" in protocol_ctx["calls"]

    def test_dispatches_actions_through_given(self):
        adapter, proto = _make_cart_adapter()
        ctx, protocol_ctx = _ctx(Cart, adapter, proto)

        ctx.given.add_item({"name": "Setup"})
        assert "add:Setup" in protocol_ctx["calls"]

    def test_dispatches_queries(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        result = ctx.query.total()
        assert result == 42

    def test_dispatches_assertions_through_then(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        # Should not raise
        ctx.then.is_empty()

    def test_dispatches_parameterized_queries(self):
        adapter, proto = _make_filter_adapter()
        ctx, _ = _ctx(FilterDomain, adapter, proto)

        result = ctx.query.items_by_status({"status": "active"})
        assert result == ["a", "b"]

    def test_domain_without_queries_works(self):
        adapter, proto = _make_action_only_adapter()
        ctx, protocol_ctx = _ctx(ActionOnlyDomain, adapter, proto)

        ctx.when.fire()
        ctx.then.fired()
        assert protocol_ctx["fired"] is True


# ---------------------------------------------------------------------------
# Narrative proxy restrictions
# ---------------------------------------------------------------------------

class TestProxyRestrictions:
    def test_when_rejects_assertions(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(TypeError, match="only accepts action"):
            ctx.when.is_empty()

    def test_when_rejects_queries(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(TypeError, match="only accepts action"):
            ctx.when.total()

    def test_then_rejects_actions(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(TypeError, match="only accepts assertion"):
            ctx.then.add_item({"name": "X"})

    def test_then_rejects_queries(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(TypeError, match="only accepts assertion"):
            ctx.then.total()

    def test_query_rejects_actions(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(TypeError, match="only accepts query"):
            ctx.query.add_item({"name": "X"})

    def test_query_rejects_assertions(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(TypeError, match="only accepts query"):
            ctx.query.is_empty()

    def test_given_accepts_actions(self):
        adapter, proto = _make_cart_adapter()
        ctx, protocol_ctx = _ctx(Cart, adapter, proto)

        ctx.given.add_item({"name": "OK"})
        assert "add:OK" in protocol_ctx["calls"]

    def test_given_accepts_assertions(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        # Assertions allowed on given (precondition checks)
        ctx.given.is_empty()

    def test_given_rejects_queries(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(TypeError, match="only accepts"):
            ctx.given.total()

    def test_missing_marker_raises_attribute_error(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        with pytest.raises(AttributeError, match="has no marker 'nonexistent'"):
            ctx.when.nonexistent()


# ---------------------------------------------------------------------------
# Trace recording
# ---------------------------------------------------------------------------

class TestTraceRecording:
    def test_records_action_trace(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        ctx.when.add_item({"name": "A"})
        ctx.query.total()
        ctx.then.is_empty()

        trace = ctx.trace()
        assert len(trace) == 3

        assert trace[0].kind == "action"
        assert trace[0].category == "when"
        assert trace[0].name == "Cart.add_item"
        assert trace[0].payload == {"name": "A"}
        assert trace[0].status == "pass"

        assert trace[1].kind == "query"
        assert trace[1].category == "query"
        assert trace[1].name == "Cart.total"
        assert trace[1].status == "pass"
        assert trace[1].result == 42

        assert trace[2].kind == "assertion"
        assert trace[2].category == "then"
        assert trace[2].name == "Cart.is_empty"
        assert trace[2].status == "pass"

    def test_records_failure_in_trace(self):
        adapter, proto = _make_fail_adapter()
        ctx, _ = _ctx(FailDomain, adapter, proto)

        with pytest.raises(RuntimeError, match="boom"):
            ctx.then.check()

        trace = ctx.trace()
        assert len(trace) == 1
        assert trace[0].kind == "assertion"
        assert trace[0].name == "Fail.check"
        assert trace[0].status == "fail"
        assert "boom" in trace[0].error

    def test_trace_returns_copy(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        ctx.when.add_item({"name": "A"})
        t1 = ctx.trace()
        t2 = ctx.trace()
        assert t1 is not t2
        assert t1 == t2

    def test_trace_records_duration(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        ctx.when.add_item({"name": "A"})

        trace = ctx.trace()
        assert trace[0].duration_ms >= 0

    def test_given_when_then_categories_correct(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        ctx.given.add_item({"name": "Setup"})
        ctx.when.add_item({"name": "Trigger"})
        ctx.then.is_empty()

        trace = ctx.trace()
        assert len(trace) == 3
        assert trace[0].category == "given"
        assert trace[0].name == "Cart.add_item"
        assert trace[0].payload == {"name": "Setup"}

        assert trace[1].category == "when"
        assert trace[1].name == "Cart.add_item"
        assert trace[1].payload == {"name": "Trigger"}

        assert trace[2].category == "then"
        assert trace[2].name == "Cart.is_empty"

    def test_parameterized_query_recorded_in_trace(self):
        adapter, proto = _make_filter_adapter()
        ctx, _ = _ctx(FilterDomain, adapter, proto)

        ctx.query.items_by_status({"status": "active"})

        trace = ctx.trace()
        assert len(trace) == 1
        assert trace[0].kind == "query"
        assert trace[0].name == "Filter.items_by_status"
        assert trace[0].payload == {"status": "active"}
        assert trace[0].status == "pass"

    def test_empty_trace_before_any_calls(self):
        adapter, proto = _make_cart_adapter()
        ctx, _ = _ctx(Cart, adapter, proto)

        assert ctx.trace() == []
