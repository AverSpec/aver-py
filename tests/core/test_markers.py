"""Tests for domain marker factories: action(), query(), assertion()."""

from averspec.domain import action, query, assertion, MarkerKind


class TestAction:
    def test_creates_action_marker(self):
        marker = action()
        assert marker.kind == MarkerKind.ACTION

    def test_creates_action_marker_with_payload_type(self):
        marker = action(dict)
        assert marker.kind == MarkerKind.ACTION
        assert marker.payload_type is dict


class TestQuery:
    def test_creates_query_marker(self):
        marker = query(type(None), int)
        assert marker.kind == MarkerKind.QUERY

    def test_creates_query_marker_with_types(self):
        marker = query(str, int)
        assert marker.kind == MarkerKind.QUERY
        assert marker.payload_type is str
        assert marker.return_type is int


class TestAssertion:
    def test_creates_assertion_marker(self):
        marker = assertion()
        assert marker.kind == MarkerKind.ASSERTION

    def test_creates_assertion_marker_with_payload_type(self):
        marker = assertion(dict)
        assert marker.kind == MarkerKind.ASSERTION
        assert marker.payload_type is dict
