"""Port of adapter-dispatch.spec.ts — suite proxy dispatches operations correctly."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall,
    TraceEntryCheck, TraceLengthCheck, QueryResultCheck,
    FailingAssertionSpec, ExtensionSpec,
)

s = suite(AverCore)


@s.test
def test_dispatches_actions_through_suite_proxy(ctx):
    """Execute an action through the suite, verify it lands in trace."""
    ctx.given.define_domain(DomainSpec(
        name="dispatch-action",
        actions=["submit_order"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="submit_order", payload="order-1"))
    ctx.then.trace_has_length(TraceLengthCheck(expected=1))
    ctx.then.trace_entry_matches(TraceEntryCheck(
        index=0, kind="action", category="when", status="pass",
    ))


@s.test
def test_dispatches_queries_and_returns_typed_results(ctx):
    """Execute a query, verify the result is returned correctly."""
    ctx.given.define_domain(DomainSpec(
        name="dispatch-query",
        actions=[],
        queries=["get_status"],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="get_status", payload="item-1"))
    ctx.then.query_returned_value(QueryResultCheck(
        marker_name="get_status", expected="result-get_status",
    ))
    ctx.then.trace_entry_matches(TraceEntryCheck(
        index=0, kind="query", category="query", status="pass",
    ))


@s.test
def test_dispatches_assertions_through_suite_proxy(ctx):
    """Execute an assertion through the suite, verify it lands in trace."""
    ctx.given.define_domain(DomainSpec(
        name="dispatch-assertion",
        actions=[],
        queries=[],
        assertions=["is_valid"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="is_valid", payload="check"))
    ctx.then.trace_has_length(TraceLengthCheck(expected=1))
    ctx.then.trace_entry_matches(TraceEntryCheck(
        index=0, kind="assertion", category="then", status="pass",
    ))


@s.test
def test_failing_assertion_with_no_prior_trace(ctx):
    """Execute only a failing assertion, verify it's in trace with fail status."""
    ctx.given.define_domain(DomainSpec(
        name="dispatch-fail-only",
        actions=[],
        queries=[],
        assertions=["must_pass"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.execute_failing_assertion(FailingAssertionSpec(
        marker_name="must_pass", payload="nope",
    ))
    ctx.then.trace_has_length(TraceLengthCheck(expected=1))
    ctx.then.trace_entry_matches(TraceEntryCheck(
        index=0, kind="assertion", category="then", status="fail",
    ))


@s.test
def test_multiple_adapters_registered_for_same_domain(ctx):
    """Register two adapters for the same domain, verify both are counted."""
    ctx.given.define_domain(DomainSpec(
        name="multi-adapter",
        actions=["do_work"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec(protocol_name="unit"))
    ctx.when.register_second_adapter(AdapterSpec(protocol_name="http"))
    ctx.then.adapter_count_is(2)


@s.test
def test_query_returns_typed_result_value(ctx):
    """Execute a query and verify the returned value matches expected type."""
    ctx.given.define_domain(DomainSpec(
        name="dispatch-typed-query",
        actions=[],
        queries=["get_count"],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="get_count", payload="x"))
    result = ctx.query.get_query_result("get_count")
    assert result == "result-get_count"
    assert isinstance(result, str)


@s.test
def test_parent_chain_lookup_finds_parent_adapter(ctx):
    """Extend a domain, register parent adapter, verify child resolves it."""
    ctx.given.define_domain(DomainSpec(
        name="parent-chain-dispatch",
        actions=["base_op"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.extend_domain(ExtensionSpec(
        child_name="child-chain-dispatch",
        new_actions=["child_op"],
        new_queries=[],
        new_assertions=[],
    ))
    # The extended domain should resolve the parent adapter through chain lookup
    ctx.then.has_parent_domain("parent-chain-dispatch")
