"""Port of adapter-dispatch.spec.ts — suite proxy dispatches operations correctly."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall,
    TraceEntryCheck, TraceLengthCheck, QueryResultCheck,
    FailingAssertionSpec,
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
