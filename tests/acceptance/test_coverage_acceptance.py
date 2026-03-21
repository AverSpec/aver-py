"""Aver-py verifying its own coverage tracking."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall, CoverageCheck,
    CoverageBreakdownCheck,
)

s = suite(AverCore)


@s.test
def test_empty_domain_has_full_coverage(ctx):
    """A domain with no markers reports 100% coverage."""
    ctx.given.define_domain_for_coverage(DomainSpec(
        name="coverage-empty",
        actions=[],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter_for_coverage(AdapterSpec())
    ctx.then.coverage_is(CoverageCheck(expected_percentage=100))


@s.test
def test_partial_coverage_reports_correct_percentage(ctx):
    """Calling 1 of 2 markers gives 50% coverage."""
    ctx.given.define_domain_for_coverage(DomainSpec(
        name="coverage-partial",
        actions=["step_one", "step_two"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter_for_coverage(AdapterSpec())
    ctx.when.call_coverage_operation(OperationCall(marker_name="step_one", payload="go"))
    ctx.then.coverage_is(CoverageCheck(expected_percentage=50))


@s.test
def test_full_coverage_after_calling_all_markers(ctx):
    """Calling all markers gives 100% coverage."""
    ctx.given.define_domain_for_coverage(DomainSpec(
        name="coverage-full",
        actions=["act"],
        queries=["ask"],
        assertions=["check"],
    ))
    ctx.given.create_adapter_for_coverage(AdapterSpec())
    ctx.when.call_coverage_operation(OperationCall(marker_name="act", payload="go"))
    ctx.when.call_coverage_operation(OperationCall(marker_name="ask", payload="what"))
    ctx.when.call_coverage_operation(OperationCall(marker_name="check", payload="ok"))
    ctx.then.coverage_is(CoverageCheck(expected_percentage=100))


@s.test
def test_does_not_double_count_repeated_calls(ctx):
    """Calling the same operation twice still counts as one covered operation."""
    ctx.given.define_domain_for_coverage(DomainSpec(
        name="coverage-dedup",
        actions=["submit"],
        queries=["total"],
        assertions=["valid"],
    ))
    ctx.given.create_adapter_for_coverage(AdapterSpec())
    ctx.when.call_coverage_operation(OperationCall(marker_name="submit", payload="first"))
    ctx.when.call_coverage_operation(OperationCall(marker_name="submit", payload="second"))
    ctx.when.call_coverage_operation(OperationCall(marker_name="total", payload="check"))
    # 2 of 3 operations covered (submit + total, valid uncalled) = 67%
    ctx.then.coverage_is(CoverageCheck(expected_percentage=67))


@s.test
def test_reports_per_kind_breakdown(ctx):
    """Coverage detail includes per-kind counts: actions called vs total."""
    ctx.given.define_domain_for_coverage(DomainSpec(
        name="coverage-breakdown",
        actions=["a1", "a2"],
        queries=["q1"],
        assertions=["c1"],
    ))
    ctx.given.create_adapter_for_coverage(AdapterSpec())
    ctx.when.call_coverage_operation(OperationCall(marker_name="a1", payload="go"))
    ctx.then.coverage_breakdown_matches(CoverageBreakdownCheck(
        actions_called=1,
        actions_total=2,
        queries_called=0,
        queries_total=1,
        assertions_called=0,
        assertions_total=1,
    ))
