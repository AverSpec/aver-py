"""Tests for registry parent-chain adapter lookup."""

import pytest
from averspec.domain import domain, action, query, assertion
from averspec.adapter import implement
from averspec.protocol import unit
from averspec.config import get_registry


@domain("Animal")
class Animal:
    feed = action()
    weight = query(type(None), int)
    is_alive = assertion()


@domain("Unregistered")
class Unregistered:
    noop = action()


def make_adapter(domain_cls, protocol_name="unit"):
    proto = unit(lambda: None, protocol_name)
    builder = implement(domain_cls, protocol=proto)
    for marker_name, marker in domain_cls._aver_markers.items():
        @builder.handle(marker)
        def handler(ctx, payload=None, _name=marker_name):
            pass
    return builder.build()


class TestParentChainLookup:
    def setup_method(self):
        get_registry().reset()

    def test_exact_match_returns_adapter(self):
        adapter = make_adapter(Animal)
        get_registry().register_adapter(adapter)
        found = get_registry().find_adapters(Animal)
        assert len(found) == 1
        assert found[0] is adapter

    def test_walks_parent_when_no_exact_match(self):
        """Child domain finds adapter registered for parent."""
        Child = Animal.extend("ChildAnimal", actions={"pet": action()})
        parent_adapter = make_adapter(Animal)
        get_registry().register_adapter(parent_adapter)

        found = get_registry().find_adapters(Child)
        assert len(found) == 1
        assert found[0] is parent_adapter

    def test_multi_level_parent_chain(self):
        """Walks grandparent when parent has no adapter either."""
        Level1 = Animal.extend("Level1Animal", actions={"groom": action()})
        Level2 = Level1.extend("Level2Animal", assertions={"is_happy": assertion()})

        grandparent_adapter = make_adapter(Animal)
        get_registry().register_adapter(grandparent_adapter)

        found = get_registry().find_adapters(Level2)
        assert len(found) == 1
        assert found[0] is grandparent_adapter

    def test_prefers_exact_match_over_parent(self):
        """Exact match takes priority even when parent also has an adapter."""
        Child = Animal.extend("ExactChild", actions={"play": action()})
        parent_adapter = make_adapter(Animal)
        child_adapter = make_adapter(Child)
        get_registry().register_adapter(parent_adapter)
        get_registry().register_adapter(child_adapter)

        found = get_registry().find_adapters(Child)
        assert len(found) == 1
        assert found[0] is child_adapter

    def test_returns_empty_for_unregistered_domain(self):
        adapter = make_adapter(Animal)
        get_registry().register_adapter(adapter)
        found = get_registry().find_adapters(Unregistered)
        assert found == []

    def test_find_adapter_singular_returns_first(self):
        adapter = make_adapter(Animal, "proto-a")
        get_registry().register_adapter(adapter)
        result = get_registry().find_adapter(Animal)
        assert result is adapter

    def test_find_adapter_singular_returns_none_for_unregistered(self):
        result = get_registry().find_adapter(Unregistered)
        assert result is None

    def test_stops_at_first_parent_level_with_matches(self):
        """When parent has adapters, doesn't also check grandparent."""
        Level1 = Animal.extend("StopLevel1", actions={"scratch": action()})
        Level2 = Level1.extend("StopLevel2", assertions={"is_fed": assertion()})

        grandparent_adapter = make_adapter(Animal)
        parent_adapter = make_adapter(Level1)
        get_registry().register_adapter(grandparent_adapter)
        get_registry().register_adapter(parent_adapter)

        found = get_registry().find_adapters(Level2)
        assert len(found) == 1
        assert found[0] is parent_adapter
