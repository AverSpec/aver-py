"""Aver tests itself.

These tests use aver-py's own @s.test, suite(), and narrative proxies
to verify the framework's behavior. The AverCore domain describes what
the framework does; the adapter exercises the real public API.
"""

from averspec import suite
from tests.dogfood.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall, ProxyCall,
    MarkerCheck, TraceCheck, ProxyRestrictionCheck, CompletenessCheck,
)

s = suite(AverCore)


# --- Domain creation ---

@s.test
def test_domain_collects_markers(ctx):
    ctx.given.define_domain(DomainSpec(
        name="test-domain",
        actions=["do_thing"],
        queries=["get_thing"],
        assertions=["check_thing"],
    ))
    ctx.then.domain_has_marker(MarkerCheck(name="do_thing", kind="action"))
    ctx.then.domain_has_marker(MarkerCheck(name="get_thing", kind="query"))
    ctx.then.domain_has_marker(MarkerCheck(name="check_thing", kind="assertion"))


@s.test
def test_domain_markers_queryable(ctx):
    ctx.given.define_domain(DomainSpec(
        name="queryable",
        actions=["create", "update"],
        queries=[],
        assertions=["exists"],
    ))
    markers = ctx.query.get_markers()
    names = {m.name for m in markers}
    assert names == {"create", "update", "exists"}


# --- Adapter completeness ---

@s.test
def test_complete_adapter_builds(ctx):
    ctx.given.define_domain(DomainSpec(
        name="complete",
        actions=["act_a"],
        queries=["query_a"],
        assertions=["assert_a"],
    ))
    ctx.when.create_adapter(AdapterSpec(protocol_name="unit"))
    ctx.then.adapter_is_complete(CompletenessCheck(missing=[]))


@s.test
def test_incomplete_adapter_reports_missing(ctx):
    ctx.given.define_domain(DomainSpec(
        name="incomplete",
        actions=["act_a", "act_b"],
        queries=[],
        assertions=["assert_a"],
    ))
    ctx.when.create_adapter(AdapterSpec(protocol_name="unit"))
    ctx.then.adapter_is_complete(CompletenessCheck(missing=["act_b"]))


# --- Dispatch and trace ---

@s.test
def test_action_dispatch_records_trace(ctx):
    ctx.given.define_domain(DomainSpec(
        name="traced",
        actions=["do_thing"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="do_thing", payload="hello"))
    ctx.then.trace_has_entry(TraceCheck(index=0, category="when", status="pass"))


@s.test
def test_multiple_operations_build_trace(ctx):
    ctx.given.define_domain(DomainSpec(
        name="multi-trace",
        actions=["step_one", "step_two"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="step_one"))
    ctx.when.call_operation(OperationCall(marker_name="step_two"))
    trace = ctx.query.get_trace()
    assert len(trace) == 2
    assert trace[0].name == "multi-trace.step_one"
    assert trace[1].name == "multi-trace.step_two"


# --- Proxy restrictions ---

@s.test
def test_when_rejects_assertions(ctx):
    ctx.given.define_domain(DomainSpec(
        name="proxy-test",
        actions=["do_thing"],
        queries=[],
        assertions=["check_thing"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.then.proxy_rejects_wrong_kind(ProxyRestrictionCheck(
        proxy_name="when",
        marker_name="check_thing",
    ))


@s.test
def test_then_rejects_actions(ctx):
    ctx.given.define_domain(DomainSpec(
        name="proxy-test-2",
        actions=["do_thing"],
        queries=[],
        assertions=["check_thing"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.then.proxy_rejects_wrong_kind(ProxyRestrictionCheck(
        proxy_name="then",
        marker_name="do_thing",
    ))


@s.test
def test_query_rejects_actions(ctx):
    ctx.given.define_domain(DomainSpec(
        name="proxy-test-3",
        actions=["do_thing"],
        queries=["get_thing"],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.then.proxy_rejects_wrong_kind(ProxyRestrictionCheck(
        proxy_name="query",
        marker_name="do_thing",
    ))
