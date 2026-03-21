"""Aver-py verifying its own coverage tracking."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, AdapterSpec, OperationCall, CoverageCheck,
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
