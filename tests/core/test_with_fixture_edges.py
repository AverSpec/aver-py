"""Tests for with_fixture edge cases."""

import pytest

from averspec.protocol import Protocol, with_fixture, TelemetryCollector


class FakeCollector(TelemetryCollector):
    def get_spans(self):
        return []

    def reset(self):
        pass


class FakeProtocol(Protocol):
    name = "fake"

    def __init__(self):
        self.telemetry = FakeCollector()
        self.custom_ext = "some_extension"

    def setup(self):
        return {"value": 42}

    def teardown(self, ctx):
        pass


class BareProtocol(Protocol):
    """Protocol with no optional hooks, no telemetry."""
    name = "bare"

    def setup(self):
        return None

    def teardown(self, ctx):
        pass


class ThrowingProtocol(Protocol):
    name = "throwing"

    def setup(self):
        return None

    def teardown(self, ctx):
        raise RuntimeError("teardown boom")


def test_extensions_passed_through():
    """with_fixture passes through protocol extensions like telemetry."""
    proto = FakeProtocol()
    wrapped = with_fixture(proto, before=lambda: None)

    assert wrapped.telemetry is not None
    assert isinstance(wrapped.telemetry, FakeCollector)


def test_after_runs_even_if_teardown_throws():
    """after() hook runs even when teardown raises an exception."""
    calls = []
    proto = ThrowingProtocol()
    wrapped = with_fixture(proto, after=lambda: calls.append("after"))

    ctx = wrapped.setup()
    with pytest.raises(RuntimeError, match="teardown boom"):
        wrapped.teardown(ctx)

    assert "after" in calls


def test_protocol_without_hooks_works():
    """Bare protocol without telemetry or extensions works fine."""
    calls = []
    proto = BareProtocol()
    wrapped = with_fixture(
        proto,
        before=lambda: calls.append("before"),
        after=lambda: calls.append("after"),
    )

    ctx = wrapped.setup()
    wrapped.teardown(ctx)

    assert calls == ["before", "after"]


def test_after_setup_receives_correct_context():
    """afterSetup hook gets the context returned by setup."""
    received = {}
    proto = FakeProtocol()
    wrapped = with_fixture(
        proto,
        after_setup=lambda ctx: received.update(ctx),
    )

    ctx = wrapped.setup()
    assert received == {"value": 42}
    assert ctx == {"value": 42}


def test_full_lifecycle_order():
    """before -> setup -> afterSetup -> teardown -> after."""
    calls = []
    proto = FakeProtocol()
    original_setup = proto.setup
    original_teardown = proto.teardown

    class TrackingProtocol(Protocol):
        name = "tracking"
        telemetry = proto.telemetry

        def setup(self):
            calls.append("setup")
            return original_setup()

        def teardown(self, ctx):
            calls.append("teardown")
            original_teardown(ctx)

    wrapped = with_fixture(
        TrackingProtocol(),
        before=lambda: calls.append("before"),
        after_setup=lambda ctx: calls.append("afterSetup"),
        after=lambda: calls.append("after"),
    )

    ctx = wrapped.setup()
    wrapped.teardown(ctx)

    assert calls == ["before", "setup", "afterSetup", "teardown", "after"]
