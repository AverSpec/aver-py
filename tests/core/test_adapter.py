"""Tests for implement() and AdapterBuilder."""

import pytest
from averspec.domain import domain, action, query, assertion
from averspec.adapter import implement, AdapterError
from averspec.protocol import unit


@domain("Cart")
class Cart:
    add_item = action(dict)
    checkout = action()
    total = query(type(None), int)
    is_empty = assertion()
    has_total = assertion(dict)


@domain("NoQueries")
class NoQueries:
    do_thing = action()
    thing_done = assertion()


def make_cart_adapter():
    proto = unit(lambda: {"calls": []})
    builder = implement(Cart, protocol=proto)

    @builder.handle(Cart.add_item)
    def add_item(ctx, payload):
        ctx["calls"].append(f"add:{payload['name']}")

    @builder.handle(Cart.checkout)
    def checkout(ctx):
        ctx["calls"].append("checkout")

    @builder.handle(Cart.total)
    def total(ctx):
        return 99

    @builder.handle(Cart.is_empty)
    def is_empty(ctx):
        pass

    @builder.handle(Cart.has_total)
    def has_total(ctx, payload):
        pass

    return builder


class TestImplement:
    def test_creates_adapter_with_domain_and_protocol(self):
        builder = make_cart_adapter()
        adapter = builder.build()
        assert adapter.domain_cls is Cart
        assert adapter.protocol.name == "unit"

    def test_exposes_executable_handlers(self):
        builder = make_cart_adapter()
        adapter = builder.build()
        ctx = adapter.protocol.setup()

        adapter.execute_sync("add_item", ctx, {"name": "Widget"})
        assert ctx["calls"] == ["add:Widget"]

        result = adapter.execute_sync("total", ctx)
        assert result == 99

    def test_requires_domain_class(self):
        with pytest.raises(TypeError, match="not a domain"):
            implement(object, protocol=unit(lambda: None))

    def test_rejects_non_marker_in_handle(self):
        proto = unit(lambda: None)
        builder = implement(Cart, protocol=proto)
        with pytest.raises(TypeError, match="expects a Marker"):
            builder.handle("not a marker")

    def test_fails_build_with_missing_handlers(self):
        proto = unit(lambda: None)
        builder = implement(Cart, protocol=proto)

        @builder.handle(Cart.add_item)
        def add_item(ctx, payload):
            pass

        with pytest.raises(AdapterError, match="missing handlers"):
            builder.build()

    def test_fails_build_with_extra_handlers(self):
        proto = unit(lambda: None)
        builder = implement(Cart, protocol=proto)

        # Register all required handlers
        for marker_name in Cart._aver_markers:
            marker = Cart._aver_markers[marker_name]

            @builder.handle(marker)
            def handler(ctx, payload=None):
                pass

        # Sneak in an extra one by manipulating _handlers directly
        builder._handlers["nonexistent"] = lambda ctx: None

        with pytest.raises(AdapterError, match="not in domain"):
            builder.build()

    def test_domain_with_no_queries_builds_ok(self):
        proto = unit(lambda: {"calls": []})
        builder = implement(NoQueries, protocol=proto)

        @builder.handle(NoQueries.do_thing)
        def do_thing(ctx):
            ctx["calls"].append("do_thing")

        @builder.handle(NoQueries.thing_done)
        def thing_done(ctx):
            if "do_thing" not in ctx["calls"]:
                raise AssertionError("do_thing not called")

        adapter = builder.build()
        assert adapter.domain_cls is NoQueries

    def test_domain_with_no_queries_executes(self):
        proto = unit(lambda: {"calls": []})
        builder = implement(NoQueries, protocol=proto)

        @builder.handle(NoQueries.do_thing)
        def do_thing(ctx):
            ctx["calls"].append("do_thing")

        @builder.handle(NoQueries.thing_done)
        def thing_done(ctx):
            if "do_thing" not in ctx["calls"]:
                raise AssertionError("do_thing not called")

        adapter = builder.build()
        ctx = adapter.protocol.setup()
        adapter.execute_sync("do_thing", ctx)
        assert "do_thing" in ctx["calls"]
        # Should not raise
        adapter.execute_sync("thing_done", ctx)
