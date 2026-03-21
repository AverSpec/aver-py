"""Tests for error enhancement with formatted trace."""

import pytest
from averspec.domain import domain, action, assertion
from averspec.adapter import implement
from averspec.protocol import unit
from averspec.suite import Context
from averspec.trace_format import format_trace


@domain("Enhanced")
class EnhancedDomain:
    setup_data = action(dict)
    verify = assertion(dict)


def _make_adapter():
    proto = unit(lambda: {})
    builder = implement(EnhancedDomain, protocol=proto)

    @builder.handle(EnhancedDomain.setup_data)
    def setup_data(ctx, payload):
        pass

    @builder.handle(EnhancedDomain.verify)
    def verify(ctx, payload=None):
        raise AssertionError("expected 42, got 0")

    return builder.build(), proto


class TestErrorEnhancement:
    def test_trace_appended_to_assertion_error(self):
        """When an assertion fails, the trace should be available for enhancement."""
        adapter, proto = _make_adapter()
        protocol_ctx = proto.setup()
        ctx = Context(EnhancedDomain, adapter, protocol_ctx)

        ctx.when.setup_data({"key": "value"})

        with pytest.raises(AssertionError, match="expected 42"):
            ctx.then.verify()

        # After failure, trace has both steps
        trace = ctx.trace()
        assert len(trace) == 2
        assert trace[0].status == "pass"
        assert trace[1].status == "fail"

        # Format the trace as the plugin would
        trace_text = format_trace(trace)
        assert "Enhanced.setup_data" in trace_text
        assert "Enhanced.verify" in trace_text
        assert "[FAIL]" in trace_text

    def test_enhancement_includes_trace_steps(self):
        """The formatted trace includes all steps leading up to failure."""
        adapter, proto = _make_adapter()
        protocol_ctx = proto.setup()
        ctx = Context(EnhancedDomain, adapter, protocol_ctx)

        ctx.when.setup_data({"a": 1})
        ctx.when.setup_data({"b": 2})

        with pytest.raises(AssertionError):
            ctx.then.verify()

        trace = ctx.trace()
        trace_text = format_trace(trace)

        # All three steps present
        lines = trace_text.strip().split("\n")
        assert len(lines) == 3
        assert "[PASS]" in lines[0]
        assert "[PASS]" in lines[1]
        assert "[FAIL]" in lines[2]

    def test_no_enhancement_when_trace_empty(self):
        """If no steps were executed, there's no trace to append."""
        adapter, proto = _make_adapter()
        protocol_ctx = proto.setup()
        ctx = Context(EnhancedDomain, adapter, protocol_ctx)

        with pytest.raises(AssertionError, match="expected 42"):
            ctx.then.verify()

        trace = ctx.trace()
        # Only the failing step
        assert len(trace) == 1
        trace_text = format_trace(trace)
        assert "[FAIL]" in trace_text
