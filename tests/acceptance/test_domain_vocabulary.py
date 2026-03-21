"""Port of domain-vocabulary.spec.ts — domain captures and reports markers."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, MarkerCheck, VocabularyCheck,
)

s = suite(AverCore)


@s.test
def test_captures_actions_queries_and_assertions(ctx):
    """Define a domain with multiple markers, verify all present with correct kinds."""
    ctx.given.define_domain(DomainSpec(
        name="vocab-full",
        actions=["create_item", "delete_item"],
        queries=["get_item"],
        assertions=["item_exists", "item_is_deleted"],
    ))
    ctx.then.domain_has_marker(MarkerCheck(name="create_item", kind="action"))
    ctx.then.domain_has_marker(MarkerCheck(name="delete_item", kind="action"))
    ctx.then.domain_has_marker(MarkerCheck(name="get_item", kind="query"))
    ctx.then.domain_has_marker(MarkerCheck(name="item_exists", kind="assertion"))
    ctx.then.domain_has_marker(MarkerCheck(name="item_is_deleted", kind="assertion"))
    ctx.then.has_vocabulary(VocabularyCheck(actions=2, queries=1, assertions=2))


@s.test
def test_allows_empty_vocabulary(ctx):
    """Define a domain with no markers, verify empty."""
    ctx.given.define_domain(DomainSpec(
        name="vocab-empty",
        actions=[],
        queries=[],
        assertions=[],
    ))
    ctx.then.has_vocabulary(VocabularyCheck(actions=0, queries=0, assertions=0))
    markers = ctx.query.get_markers()
    assert markers == []


@s.test
def test_markers_report_correct_kind(ctx):
    """Each marker reports its kind accurately through the query API."""
    ctx.given.define_domain(DomainSpec(
        name="vocab-kinds",
        actions=["do_thing"],
        queries=["get_thing"],
        assertions=["check_thing"],
    ))
    markers = ctx.query.get_markers()
    kinds_by_name = {m.name: m.kind for m in markers}
    assert kinds_by_name["do_thing"] == "action"
    assert kinds_by_name["get_thing"] == "query"
    assert kinds_by_name["check_thing"] == "assertion"
