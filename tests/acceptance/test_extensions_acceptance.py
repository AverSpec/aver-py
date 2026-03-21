"""Aver-py verifying domain extensions through itself."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, ExtensionSpec, ExtensionMarkerCheck,
)

s = suite(AverCore)


@s.test
def test_extension_inherits_parent_markers(ctx):
    """An extended domain carries parent markers plus new ones."""
    ctx.given.define_domain(DomainSpec(
        name="ext-parent",
        actions=["base_action"],
        queries=["base_query"],
        assertions=["base_check"],
    ))
    ctx.when.extend_domain(ExtensionSpec(
        child_name="ext-child",
        new_actions=["child_action"],
        new_queries=[],
        new_assertions=["child_check"],
    ))
    ctx.then.extension_has_markers(ExtensionMarkerCheck(
        parent_marker_names=["base_action", "base_query", "base_check"],
        child_marker_names=["child_action", "child_check"],
    ))


@s.test
def test_extension_with_only_new_actions(ctx):
    """Extend a domain with only new actions, no new queries or assertions."""
    ctx.given.define_domain(DomainSpec(
        name="ext-action-only",
        actions=["original"],
        queries=[],
        assertions=[],
    ))
    ctx.when.extend_domain(ExtensionSpec(
        child_name="ext-action-child",
        new_actions=["added_one", "added_two"],
        new_queries=[],
        new_assertions=[],
    ))
    markers = ctx.query.get_extension_markers()
    names = {m.name for m in markers}
    assert names == {"original", "added_one", "added_two"}


@s.test
def test_extension_preserves_marker_count(ctx):
    """Extended domain marker count = parent markers + new markers."""
    ctx.given.define_domain(DomainSpec(
        name="ext-count",
        actions=["a1"],
        queries=["q1"],
        assertions=["c1"],
    ))
    ctx.when.extend_domain(ExtensionSpec(
        child_name="ext-count-child",
        new_actions=["a2"],
        new_queries=["q2"],
        new_assertions=["c2"],
    ))
    markers = ctx.query.get_extension_markers()
    assert len(markers) == 6
