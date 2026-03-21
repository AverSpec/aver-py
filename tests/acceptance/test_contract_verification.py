"""Contract verification acceptance tests: extract, write, read, verify."""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, ContractDomainSpec, ContractTraceSpec,
)

s = suite(AverCore)


@s.test
def test_extract_contract_from_passing_test_with_static_telemetry(ctx):
    """Extract a contract from a test with static telemetry, verify it round-trips."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-static",
        actions=["login"],
        span_names=["auth.login"],
        span_attributes=[{"user.role": "admin"}],
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[{"name": "auth.login", "attributes": {"user.role": "admin"}}],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[{"name": "auth.login", "attributes": {"user.role": "admin"}, "trace_id": "t1", "span_id": "s1"}],
    ))
    ctx.then.contract_passes()


@s.test
def test_extract_contract_from_parameterized_telemetry(ctx):
    """Extract a contract with correlated bindings from parameterized telemetry."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-param",
        actions=["signup"],
        span_names=["user.signup"],
        span_attributes=[{"user.email": "$email"}],
        parameterized=True,
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[{"name": "user.signup", "attributes": {"user.email": "alice@test.com"}}],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    # Verify with matching production traces
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[{"name": "user.signup", "attributes": {"user.email": "bob@test.com"}, "trace_id": "t1", "span_id": "s1"}],
    ))
    # Correlated bindings match any consistent value, so this should pass
    ctx.then.contract_passes()


@s.test
def test_verify_passes_on_matching_production_traces(ctx):
    """A contract verified against matching traces produces no violations."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-match",
        actions=["checkout"],
        span_names=["order.checkout"],
        span_attributes=[{"amount": 100}],
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[{"name": "order.checkout", "attributes": {"amount": 100}}],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[{"name": "order.checkout", "attributes": {"amount": 100}, "trace_id": "t1", "span_id": "s1"}],
    ))
    ctx.then.contract_passes()
    violations = ctx.query.get_contract_violations()
    assert violations == 0


@s.test
def test_verify_fails_on_missing_span(ctx):
    """Verification fails when a required span is absent from production traces."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-missing",
        actions=["start", "charge"],
        span_names=["checkout.start", "payment.charge"],
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[
            {"name": "checkout.start"},
            {"name": "payment.charge"},
        ],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    # Production only has the first span
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[{"name": "checkout.start", "trace_id": "t1", "span_id": "s1"}],
    ))
    ctx.then.contract_has_violations()
    ctx.then.violation_includes("missing-span")


@s.test
def test_verify_fails_on_literal_attribute_mismatch(ctx):
    """Verification fails when a literal attribute value drifts."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-literal",
        actions=["cancel"],
        span_names=["order.cancel"],
        span_attributes=[{"order.status": "cancelled"}],
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[{"name": "order.cancel", "attributes": {"order.status": "cancelled"}}],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    # Production has a different spelling
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[{"name": "order.cancel", "attributes": {"order.status": "canceled"}, "trace_id": "t1", "span_id": "s1"}],
    ))
    ctx.then.contract_has_violations()
    ctx.then.violation_includes("literal-mismatch")


@s.test
def test_verify_fails_on_correlation_violation(ctx):
    """Verification fails when a correlated symbol has divergent values."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-corr",
        actions=["login", "session"],
        span_names=["auth.login", "auth.session"],
        span_attributes=[{"user.email": "$email"}, {"user.email": "$email"}],
        parameterized=True,
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[
            {"name": "auth.login", "attributes": {"user.email": "alice@co.com"}},
            {"name": "auth.session", "attributes": {"user.email": "alice@co.com"}},
        ],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    # Production: same symbol maps to different values
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[
            {"name": "auth.login", "attributes": {"user.email": "alice@co.com"}, "trace_id": "t1", "span_id": "s1"},
            {"name": "auth.session", "attributes": {"user.email": "bob@co.com"}, "trace_id": "t1", "span_id": "s2"},
        ],
    ))
    ctx.then.contract_has_violations()
    ctx.then.violation_includes("correlation-violation")


@s.test
def test_contract_write_and_read_round_trip(ctx):
    """Write a contract, read it back, verify structure is preserved."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-roundtrip",
        actions=["op_one"],
        span_names=["service.op_one"],
        span_attributes=[{"key": "value"}],
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[{"name": "service.op_one", "attributes": {"key": "value"}}],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    # Verify with exactly matching traces: the round-trip is intact
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[{"name": "service.op_one", "attributes": {"key": "value"}, "trace_id": "t1", "span_id": "s1"}],
    ))
    ctx.then.contract_passes()


@s.test
def test_no_matching_traces_produces_violation(ctx):
    """When production traces have no matching anchor span, a violation is reported."""
    ctx.given.setup_contract_workbench()
    ctx.given.define_contract_domain(ContractDomainSpec(
        domain_name="cv-no-match",
        actions=["expected_op"],
        span_names=["expected.span"],
    ))
    ctx.given.create_contract_adapter(ContractTraceSpec(
        spans=[{"name": "expected.span"}],
    ))
    ctx.when.run_contract_operations()
    ctx.when.extract_and_write_contract()
    # Production traces have completely different spans
    ctx.when.load_and_verify_contract(ContractTraceSpec(
        spans=[{"name": "unrelated.span", "trace_id": "t1", "span_id": "s1"}],
    ))
    ctx.then.contract_has_violations()
    ctx.then.violation_includes("no-matching-traces")
