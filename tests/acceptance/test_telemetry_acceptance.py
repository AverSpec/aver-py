"""Aver-py verifying its own telemetry verification through itself."""

import os
from unittest.mock import patch

from averspec import suite
from tests.acceptance.domain import (
    AverCore, TelemetryDomainSpec, TelemetryAdapterSpec,
    OperationCall, TelemetrySpanCheck,
)

s = suite(AverCore)


@s.test
def test_telemetry_span_matched_on_action(ctx):
    """Define a domain with telemetry, execute action, verify span matched."""
    with patch.dict(os.environ, {"AVER_TELEMETRY_MODE": "warn"}):
        ctx.given.define_telemetry_domain(TelemetryDomainSpec(
            name="tel-match",
            actions=["create_order"],
            span_names=["order.create"],
        ))
        ctx.given.create_telemetry_adapter(TelemetryAdapterSpec())
        ctx.when.call_telemetry_operation(OperationCall(
            marker_name="create_order", payload="order-1",
        ))
        ctx.then.telemetry_span_matched(TelemetrySpanCheck(
            index=0,
            expected_span="order.create",
            matched=True,
        ))


@s.test
def test_multiple_telemetry_spans_matched(ctx):
    """Define a domain with multiple telemetry actions, verify each matches."""
    with patch.dict(os.environ, {"AVER_TELEMETRY_MODE": "warn"}):
        ctx.given.define_telemetry_domain(TelemetryDomainSpec(
            name="tel-multi",
            actions=["start_flow", "complete_flow"],
            span_names=["flow.start", "flow.complete"],
        ))
        ctx.given.create_telemetry_adapter(TelemetryAdapterSpec())
        ctx.when.call_telemetry_operation(OperationCall(
            marker_name="start_flow", payload="flow-1",
        ))
        ctx.when.call_telemetry_operation(OperationCall(
            marker_name="complete_flow", payload="flow-1",
        ))
        ctx.then.telemetry_span_matched(TelemetrySpanCheck(
            index=0, expected_span="flow.start", matched=True,
        ))
        ctx.then.telemetry_span_matched(TelemetrySpanCheck(
            index=1, expected_span="flow.complete", matched=True,
        ))
