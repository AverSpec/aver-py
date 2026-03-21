"""Tests for domain extension edge cases: duplicate detection and cross-section names."""

import pytest
from averspec.domain import domain, action, query, assertion


@domain("EdgeBase")
class EdgeBase:
    do_a = action()
    get_x = query(type(None), int)
    check_a = assertion()


class TestDuplicateDetection:
    def test_duplicate_query_in_extension_raises(self):
        """Extending with a query name that exists in parent raises."""
        with pytest.raises(ValueError, match="collision"):
            EdgeBase.extend("BadQuery", queries={"get_x": query(type(None), str)})

    def test_duplicate_assertion_in_extension_raises(self):
        """Extending with an assertion name that exists in parent raises."""
        with pytest.raises(ValueError, match="collision"):
            EdgeBase.extend("BadAssertion", assertions={"check_a": assertion()})

    def test_multiple_duplicates_reported(self):
        """All colliding names appear in the error, not just the first."""
        with pytest.raises(ValueError, match="do_a.*check_a|check_a.*do_a"):
            EdgeBase.extend(
                "MultiDup",
                actions={"do_a": action()},
                assertions={"check_a": assertion()},
            )

    def test_cross_section_different_names_ok(self):
        """Different names in different sections don't collide."""
        Extended = EdgeBase.extend(
            "CrossSection",
            actions={"do_b": action()},
            queries={"get_y": query(type(None), int)},
            assertions={"check_b": assertion()},
        )
        markers = Extended._aver_markers
        # Parent markers inherited
        assert "do_a" in markers
        assert "get_x" in markers
        assert "check_a" in markers
        # New markers added
        assert "do_b" in markers
        assert "get_y" in markers
        assert "check_b" in markers
