"""Port of action-trace.spec.ts — trace recording across operations."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall, ProxyCall,
    TraceEntryCheck, TraceLengthCheck, FailingAssertionSpec,
)

s = suite(AverCore)


@s.test
def test_records_complete_trace_across_multiple_operations(ctx):
    """Execute action + query + assertion, verify trace has 3 entries with correct kinds."""
    ctx.given.define_domain(DomainSpec(
        name="trace-full",
        actions=["setup_data"],
        queries=["fetch_data"],
        assertions=["data_valid"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="setup_data", payload="seed"))
    ctx.when.call_operation(OperationCall(marker_name="fetch_data", payload="key"))
    ctx.when.call_operation(OperationCall(marker_name="data_valid", payload="check"))
    ctx.then.trace_has_length(TraceLengthCheck(expected=3))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=0, kind="action", category="when", status="pass"))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=1, kind="query", category="query", status="pass"))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=2, kind="assertion", category="then", status="pass"))


@s.test
def test_records_failure_status_when_assertion_fails(ctx):
    """Execute an action then a failing assertion, verify trace shows pass then fail."""
    ctx.given.define_domain(DomainSpec(
        name="trace-fail",
        actions=["prepare"],
        queries=[],
        assertions=["check_result"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.when.call_operation(OperationCall(marker_name="prepare", payload="data"))
    ctx.when.execute_failing_assertion(FailingAssertionSpec(
        marker_name="check_result", payload="bad",
    ))
    ctx.then.trace_has_length(TraceLengthCheck(expected=2))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=0, kind="action", category="when", status="pass"))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=1, kind="assertion", category="then", status="fail"))


@s.test
def test_records_categorized_trace_with_given_when_then(ctx):
    """Execute operations through different proxies, verify categories recorded."""
    ctx.given.define_domain(DomainSpec(
        name="trace-categorized",
        actions=["seed_state", "perform_action"],
        queries=[],
        assertions=["verify_outcome"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    # given proxy accepts actions
    ctx.when.call_through_proxy(ProxyCall(
        proxy_name="given", marker_name="seed_state", payload="initial",
    ))
    # when proxy accepts actions
    ctx.when.call_through_proxy(ProxyCall(
        proxy_name="when", marker_name="perform_action", payload="go",
    ))
    # then proxy accepts assertions
    ctx.when.call_through_proxy(ProxyCall(
        proxy_name="then", marker_name="verify_outcome", payload="ok",
    ))
    ctx.then.trace_has_length(TraceLengthCheck(expected=3))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=0, kind="action", category="given", status="pass"))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=1, kind="action", category="when", status="pass"))
    ctx.then.trace_entry_matches(TraceEntryCheck(index=2, kind="assertion", category="then", status="pass"))


@s.test
def test_trace_is_empty_before_any_operations(ctx):
    """Before any operations execute, the trace has zero entries."""
    ctx.given.define_domain(DomainSpec(
        name="trace-empty",
        actions=["noop"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.then.trace_has_length(TraceLengthCheck(expected=0))
