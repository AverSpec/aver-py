"""Tests that adapt() works identically to implement()."""

from averspec.domain import domain, action, query, assertion
from averspec.adapter import adapt, implement
from averspec.protocol import unit


@domain("Widget")
class Widget:
    create = action(dict)
    count = query(type(None), int)
    exists = assertion()


def _build_with(builder_fn):
    proto = unit(lambda: {"items": []})
    builder = builder_fn(Widget, protocol=proto)

    @builder.handle(Widget.create)
    def create(ctx, payload):
        ctx["items"].append(payload["name"])

    @builder.handle(Widget.count)
    def count(ctx):
        return len(ctx["items"])

    @builder.handle(Widget.exists)
    def exists(ctx):
        assert len(ctx["items"]) > 0

    return builder.build()


def test_adapt_is_same_function():
    assert adapt is implement


def test_adapt_builds_valid_adapter():
    adapter = _build_with(adapt)
    assert adapter.domain_name == "Widget"


def test_adapt_adapter_executes_handlers():
    adapter = _build_with(adapt)
    ctx = {"items": []}
    adapter.execute_sync("create", ctx, {"name": "bolt"})
    result = adapter.execute_sync("count", ctx)
    assert result == 1


def test_adapt_importable_from_top_level():
    from averspec import adapt as top_level_adapt
    assert top_level_adapt is implement
