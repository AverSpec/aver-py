"""Tests for vocabulary coverage tracking on Context."""

from averspec import domain, action, query, assertion, implement, unit
from averspec.suite import Context


@domain("Cart")
class Cart:
    add_item = action(dict)
    remove_item = action(dict)
    total = query(type(None), int)
    is_empty = assertion()


def _make_ctx(domain_cls):
    """Build a Context for a domain with no-op handlers."""
    markers = domain_cls._aver_markers
    proto = unit(lambda: {})
    builder = implement(domain_cls, protocol=proto)
    for name in markers:
        @builder.handle(markers[name])
        def handler(ctx, payload=None, _name=name):
            return None
    adapter = builder.build()
    protocol_ctx = proto.setup()
    return Context(domain_cls, adapter, protocol_ctx)


def test_100_percent_when_all_operations_called():
    ctx = _make_ctx(Cart)
    ctx.when.add_item({"name": "Widget"})
    ctx.when.remove_item({"name": "Widget"})
    ctx.query.total()
    ctx.then.is_empty()

    cov = ctx.get_coverage()
    assert cov["domain"] == "Cart"
    assert cov["percentage"] == 100
    assert set(cov["actions"]["called"]) == {"add_item", "remove_item"}
    assert cov["queries"]["called"] == ["total"]
    assert cov["assertions"]["called"] == ["is_empty"]


def test_0_percent_when_no_operations_called():
    ctx = _make_ctx(Cart)
    cov = ctx.get_coverage()
    assert cov["percentage"] == 0
    assert cov["actions"]["called"] == []


def test_partial_coverage():
    ctx = _make_ctx(Cart)
    ctx.when.add_item({"name": "Widget"})
    ctx.query.total()

    cov = ctx.get_coverage()
    # 2 of 4 = 50%
    assert cov["percentage"] == 50


def test_empty_domain_is_100_percent():
    @domain("Empty")
    class Empty:
        pass

    proto = unit(lambda: {})
    builder = implement(Empty, protocol=proto)
    adapter = builder.build()
    protocol_ctx = proto.setup()
    ctx = Context(Empty, adapter, protocol_ctx)

    cov = ctx.get_coverage()
    assert cov["percentage"] == 100


def test_does_not_double_count_repeated_calls():
    ctx = _make_ctx(Cart)
    ctx.when.add_item({"name": "A"})
    ctx.when.add_item({"name": "B"})
    ctx.query.total()

    cov = ctx.get_coverage()
    # 2 unique of 4 total = 50%
    assert cov["percentage"] == 50


def test_coverage_breakdown_per_kind():
    ctx = _make_ctx(Cart)
    ctx.when.add_item({"name": "Widget"})

    cov = ctx.get_coverage()
    assert cov["actions"]["total"] == ["add_item", "remove_item"]
    assert cov["actions"]["called"] == ["add_item"]
    assert cov["queries"]["total"] == ["total"]
    assert cov["queries"]["called"] == []
    assert cov["assertions"]["total"] == ["is_empty"]
    assert cov["assertions"]["called"] == []
