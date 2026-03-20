"""Tests for the adapter registry in config.py."""

import pytest
from averspec.domain import domain, action, query, assertion
from averspec.adapter import implement
from averspec.protocol import unit
from averspec.config import get_registry, define_config


@domain("Cart")
class Cart:
    add_item = action()
    total = query(type(None), int)
    is_empty = assertion()


@domain("Orders")
class Orders:
    place = action()
    order_list = query(type(None), list)
    has_order = assertion()


def make_adapter(domain_cls, protocol_name="unit"):
    proto = unit(lambda: None, protocol_name)
    builder = implement(domain_cls, protocol=proto)
    for marker_name, marker in domain_cls._aver_markers.items():
        @builder.handle(marker)
        def handler(ctx, payload=None, _name=marker_name):
            pass
    return builder.build()


class TestRegistry:
    def setup_method(self):
        get_registry().reset()

    def test_starts_empty(self):
        assert get_registry().find_adapters(Cart) == []

    def test_registers_an_adapter(self):
        adapter = make_adapter(Cart)
        get_registry().register_adapter(adapter)
        assert len(get_registry().find_adapters(Cart)) == 1

    def test_finds_adapters_by_domain(self):
        cart_adapter = make_adapter(Cart)
        orders_adapter = make_adapter(Orders)
        get_registry().register_adapter(cart_adapter)
        get_registry().register_adapter(orders_adapter)

        cart_adapters = get_registry().find_adapters(Cart)
        assert len(cart_adapters) == 1
        assert cart_adapters[0] is cart_adapter

    def test_returns_empty_for_unregistered_domain(self):
        adapter = make_adapter(Cart)
        get_registry().register_adapter(adapter)
        assert get_registry().find_adapters(Orders) == []

    def test_reset_clears_all_adapters(self):
        adapter = make_adapter(Cart)
        get_registry().register_adapter(adapter)
        get_registry().reset()
        assert get_registry().find_adapters(Cart) == []


class TestDefineConfig:
    def setup_method(self):
        get_registry().reset()

    def test_registers_adapter_builder(self):
        proto = unit(lambda: None)
        builder = implement(Cart, protocol=proto)
        for marker_name, marker in Cart._aver_markers.items():
            @builder.handle(marker)
            def handler(ctx, payload=None):
                pass

        define_config(adapters=[builder])
        assert len(get_registry().find_adapters(Cart)) == 1

    def test_registers_built_adapter(self):
        adapter = make_adapter(Cart)
        define_config(adapters=[adapter])
        assert len(get_registry().find_adapters(Cart)) == 1

    def test_rejects_invalid_type(self):
        with pytest.raises(TypeError, match="Expected Adapter or AdapterBuilder"):
            define_config(adapters=["not an adapter"])

    def test_registers_multiple_adapters(self):
        cart_adapter = make_adapter(Cart)
        orders_adapter = make_adapter(Orders)
        define_config(adapters=[cart_adapter, orders_adapter])
        assert len(get_registry().find_adapters(Cart)) == 1
        assert len(get_registry().find_adapters(Orders)) == 1
