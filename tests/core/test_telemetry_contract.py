"""Tests for behavioral contract extraction and verification."""

from averspec.domain import domain, action, MarkerKind, Marker
from averspec.trace import TraceEntry
from averspec.telemetry_types import (
    TelemetryExpectation,
    TelemetryMatchResult,
    CollectedSpan,
)
from averspec.telemetry_contract import (
    extract_contract,
    BehavioralContract,
    ContractEntry,
    SpanExpectation,
    AttributeBinding,
    _FieldTracker,
)
from averspec.telemetry_verify import (
    verify_contract,
    ProductionTrace,
    ProductionSpan,
)


# --- Helpers ---


@domain("order-flow")
class OrderDomain:
    place_order = action(
        dict,
        telemetry=lambda p: TelemetryExpectation(
            span="order.placed",
            attributes={"order.id": p["order_id"]},
        ),
    )
    cancel_order = action(
        type(None),
        telemetry=TelemetryExpectation(
            span="order.cancelled",
            attributes={"order.status": "cancelled"},
        ),
    )


def _trace_entry_with_telemetry(
    marker_name: str,
    span_name: str,
    expected_attrs: dict,
    payload=None,
) -> TraceEntry:
    return TraceEntry(
        kind="action",
        category="when",
        name=f"order-flow.{marker_name}",
        payload=payload,
        telemetry=TelemetryMatchResult(
            expected=TelemetryExpectation(
                span=span_name,
                attributes=expected_attrs,
            ),
            matched=True,
            matched_span=CollectedSpan(
                trace_id="aaa",
                span_id="001",
                name=span_name,
                attributes=expected_attrs,
            ),
        ),
    )


# --- Contract extraction ---


def test_extract_contract_from_static_telemetry():
    trace = [
        _trace_entry_with_telemetry(
            "cancel_order", "order.cancelled",
            {"order.status": "cancelled"},
        ),
    ]

    contract = extract_contract(OrderDomain, [{"test_name": "cancel test", "trace": trace}])

    assert contract.domain == "order-flow"
    assert len(contract.entries) == 1
    assert contract.entries[0].test_name == "cancel test"
    assert len(contract.entries[0].spans) == 1

    span = contract.entries[0].spans[0]
    assert span.name == "order.cancelled"
    assert span.attributes["order.status"].kind == "literal"
    assert span.attributes["order.status"].value == "cancelled"


def test_extract_contract_from_parameterized_telemetry():
    payload = {"order_id": "ORD-42"}
    trace = [
        _trace_entry_with_telemetry(
            "place_order", "order.placed",
            {"order.id": "ORD-42"},
            payload=payload,
        ),
    ]

    contract = extract_contract(OrderDomain, [{"test_name": "place test", "trace": trace}])

    assert len(contract.entries) == 1
    span = contract.entries[0].spans[0]
    assert span.name == "order.placed"
    assert span.attributes["order.id"].kind == "correlated"
    assert span.attributes["order.id"].symbol == "$order_id"


def test_field_tracker_proxy():
    tracker = _FieldTracker()
    val = tracker.some_field
    assert val == "__aver_sentinel_some_field__"
    assert tracker._accessed == {"some_field": "__aver_sentinel_some_field__"}


# --- Contract verification ---


def test_verify_contract_passes_on_matching_traces():
    contract = BehavioralContract(
        domain="order-flow",
        entries=[ContractEntry(
            test_name="cancel sets status",
            spans=[SpanExpectation(
                name="order.cancelled",
                attributes={
                    "order.status": AttributeBinding(kind="literal", value="cancelled"),
                },
            )],
        )],
    )

    traces = [ProductionTrace(
        trace_id="t1",
        spans=[ProductionSpan(
            name="order.cancelled",
            attributes={"order.status": "cancelled"},
        )],
    )]

    report = verify_contract(contract, traces)
    assert report.total_violations == 0
    assert report.results[0].traces_matched == 1


def test_verify_contract_fails_on_missing_span():
    contract = BehavioralContract(
        domain="signup",
        entries=[ContractEntry(
            test_name="signup creates account",
            spans=[
                SpanExpectation(name="user.signup", attributes={}),
                SpanExpectation(name="account.created", attributes={}),
            ],
        )],
    )

    traces = [ProductionTrace(
        trace_id="t1",
        spans=[ProductionSpan(name="user.signup", attributes={})],
        # account.created is missing
    )]

    report = verify_contract(contract, traces)
    missing = [v for v in report.results[0].violations if v.kind == "missing-span"]
    assert len(missing) == 1
    assert missing[0].span_name == "account.created"


def test_verify_contract_fails_on_literal_mismatch():
    contract = BehavioralContract(
        domain="order-flow",
        entries=[ContractEntry(
            test_name="cancel sets status",
            spans=[SpanExpectation(
                name="order.cancelled",
                attributes={
                    "order.status": AttributeBinding(kind="literal", value="cancelled"),
                },
            )],
        )],
    )

    traces = [ProductionTrace(
        trace_id="t1",
        spans=[ProductionSpan(
            name="order.cancelled",
            attributes={"order.status": "pending"},
        )],
    )]

    report = verify_contract(contract, traces)
    assert report.total_violations == 1
    v = report.results[0].violations[0]
    assert v.kind == "literal-mismatch"
    assert v.expected == "cancelled"
    assert v.actual == "pending"


def test_verify_contract_fails_on_correlation_violation():
    contract = BehavioralContract(
        domain="signup",
        entries=[ContractEntry(
            test_name="signup flow",
            spans=[
                SpanExpectation(
                    name="user.signup",
                    attributes={
                        "user.email": AttributeBinding(kind="correlated", symbol="$email"),
                    },
                ),
                SpanExpectation(
                    name="account.created",
                    attributes={
                        "account.email": AttributeBinding(kind="correlated", symbol="$email"),
                    },
                ),
            ],
        )],
    )

    traces = [ProductionTrace(
        trace_id="t1",
        spans=[
            ProductionSpan(name="user.signup", attributes={"user.email": "jane@co.com"}),
            ProductionSpan(name="account.created", attributes={"account.email": "other@co.com"}),
        ],
    )]

    report = verify_contract(contract, traces)
    corr = [v for v in report.results[0].violations if v.kind == "correlation-violation"]
    assert len(corr) == 1
    assert corr[0].symbol == "$email"


def test_verify_contract_no_matching_traces():
    contract = BehavioralContract(
        domain="signup",
        entries=[ContractEntry(
            test_name="signup creates account",
            spans=[
                SpanExpectation(name="user.signup", attributes={}),
            ],
        )],
    )

    traces = [ProductionTrace(
        trace_id="unrelated",
        spans=[ProductionSpan(name="payment.process", attributes={"amount": 100})],
    )]

    report = verify_contract(contract, traces)
    assert report.results[0].traces_matched == 0
    assert report.total_violations == 1
    v = report.results[0].violations[0]
    assert v.kind == "no-matching-traces"
    assert v.anchor_span == "user.signup"
