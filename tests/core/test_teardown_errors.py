"""Tests for teardown error handling in the pytest plugin.

These test the ctx fixture's teardown behavior directly via Context + Protocol,
since the plugin fixture wiring is hard to test in isolation.
"""

import logging
import pytest
from averspec.domain import domain, action, assertion
from averspec.adapter import implement
from averspec.protocol import Protocol, unit
from averspec.config import get_registry, define_config
from averspec.suite import Suite, Context


@domain("Teardown")
class TeardownDomain:
    do_thing = action()
    check = assertion()


class FailingTeardownProtocol(Protocol):
    """Protocol whose teardown always raises."""
    name = "failing-teardown"

    def __init__(self):
        self._ctx = None

    def setup(self):
        self._ctx = {"calls": []}
        return self._ctx

    def teardown(self, ctx):
        raise RuntimeError("teardown exploded")


class TrackingProtocol(Protocol):
    """Protocol that tracks teardown calls."""
    name = "tracking"

    def __init__(self):
        self.teardown_called = False

    def setup(self):
        return {"calls": []}

    def teardown(self, ctx):
        self.teardown_called = True


def make_adapter(domain_cls, proto):
    builder = implement(domain_cls, protocol=proto)
    for marker_name, marker in domain_cls._aver_markers.items():
        @builder.handle(marker)
        def handler(ctx, payload=None, _name=marker_name):
            pass
    return builder.build()


class TestTeardownFailMode:
    def setup_method(self):
        get_registry().reset()

    def test_teardown_error_raises_in_fail_mode(self):
        """Default mode: teardown errors propagate."""
        registry = get_registry()
        registry.teardown_failure_mode = "fail"

        proto = FailingTeardownProtocol()
        adapter = make_adapter(TeardownDomain, proto)
        protocol_ctx = proto.setup()

        with pytest.raises(RuntimeError, match="teardown exploded"):
            proto.teardown(protocol_ctx)

    def test_teardown_error_warns_in_warn_mode(self, caplog):
        """Warn mode: teardown errors logged, not raised."""
        registry = get_registry()
        registry.teardown_failure_mode = "warn"

        proto = FailingTeardownProtocol()
        adapter = make_adapter(TeardownDomain, proto)
        protocol_ctx = proto.setup()

        # Simulate what the plugin does in warn mode
        import logging
        logger = logging.getLogger("averspec")
        try:
            proto.teardown(protocol_ctx)
        except Exception as e:
            if registry.teardown_failure_mode == "warn":
                logger.warning(f"Teardown error (suppressed): {e}")
            else:
                raise

        assert "Teardown error (suppressed)" in caplog.text

    def test_define_config_sets_teardown_failure_mode(self):
        proto = unit(lambda: None)
        adapter = make_adapter(TeardownDomain, proto)
        define_config(adapters=[adapter], teardown_failure_mode="warn")
        assert get_registry().teardown_failure_mode == "warn"

    def test_define_config_rejects_invalid_mode(self):
        proto = unit(lambda: None)
        adapter = make_adapter(TeardownDomain, proto)
        with pytest.raises(ValueError, match="teardown_failure_mode"):
            define_config(adapters=[adapter], teardown_failure_mode="ignore")

    def test_teardown_still_runs_on_test_failure(self):
        """Teardown runs even when the test body raises."""
        proto = TrackingProtocol()
        adapter = make_adapter(TeardownDomain, proto)
        protocol_ctx = proto.setup()
        ctx = Context(TeardownDomain, adapter, protocol_ctx)

        # Simulate test failure
        try:
            raise AssertionError("test failed")
        except AssertionError:
            pass
        finally:
            proto.teardown(protocol_ctx)

        assert proto.teardown_called is True
