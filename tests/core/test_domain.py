"""Tests for @domain decorator and domain declaration."""

import pytest
from averspec.domain import domain, action, query, assertion, MarkerKind


@domain("ShoppingCart")
class Cart:
    add_item = action(dict)
    checkout = action()
    cart_total = query(type(None), int)
    has_total = assertion(dict)
    is_empty = assertion()


class TestDomain:
    def test_creates_domain_with_name(self):
        assert Cart._aver_domain_name == "ShoppingCart"

    def test_marks_class_as_domain(self):
        assert Cart._aver_is_domain is True

    def test_collects_markers(self):
        markers = Cart._aver_markers
        assert "add_item" in markers
        assert "checkout" in markers
        assert "cart_total" in markers
        assert "has_total" in markers
        assert "is_empty" in markers

    def test_markers_have_correct_kinds(self):
        markers = Cart._aver_markers
        assert markers["add_item"].kind == MarkerKind.ACTION
        assert markers["checkout"].kind == MarkerKind.ACTION
        assert markers["cart_total"].kind == MarkerKind.QUERY
        assert markers["has_total"].kind == MarkerKind.ASSERTION
        assert markers["is_empty"].kind == MarkerKind.ASSERTION

    def test_markers_have_names_set(self):
        markers = Cart._aver_markers
        assert markers["add_item"].name == "add_item"
        assert markers["checkout"].name == "checkout"

    def test_markers_have_domain_name_set(self):
        markers = Cart._aver_markers
        for marker in markers.values():
            assert marker.domain_name == "ShoppingCart"

    def test_allows_empty_domain(self):
        @domain("Empty")
        class EmptyDomain:
            pass

        assert EmptyDomain._aver_domain_name == "Empty"
        assert EmptyDomain._aver_markers == {}

    def test_exposes_marker_keys_for_enumeration(self):
        marker_names = set(Cart._aver_markers.keys())
        assert marker_names == {"add_item", "checkout", "cart_total", "has_total", "is_empty"}

    def test_prevents_instantiation(self):
        with pytest.raises(TypeError, match="domain declaration"):
            Cart()

    def test_prevents_domain_subclassing(self):
        with pytest.raises(TypeError, match="already is a domain"):
            @domain("Sub")
            class SubCart(Cart):
                extra = action()
