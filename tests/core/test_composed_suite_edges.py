"""Edge-case tests for composed suites."""

import pytest

from averspec import domain, action, query, assertion, implement
from averspec.suite import ComposedSuite


# --- Domains for these tests ---

@domain("Alpha")
class Alpha:
    do_thing = action()


@domain("Beta")
class Beta:
    do_other = action()


class _TrackingProto:
    """Protocol that tracks setup/teardown calls."""

    def __init__(self, label: str, setup_log: list, teardown_log: list, *, fail_setup: bool = False):
        self.name = label
        self._label = label
        self._setup_log = setup_log
        self._teardown_log = teardown_log
        self._fail_setup = fail_setup

    def setup(self):
        self._setup_log.append(f"setup:{self._label}")
        if self._fail_setup:
            raise RuntimeError(f"setup failed: {self._label}")
        return {"label": self._label}

    def teardown(self, ctx):
        self._teardown_log.append(f"teardown:{self._label}")


def _build_adapter(domain_cls, proto):
    builder = implement(domain_cls, protocol=proto)
    for marker in domain_cls._aver_markers.values():
        @builder.handle(marker)
        def _noop(ctx, payload=None):
            pass
    return builder.build()


class TestPartialSetupFailure:
    def test_tears_down_already_setup_domains(self):
        """If the second domain's setup() raises, the first should still be torn down."""
        setup_log: list[str] = []
        teardown_log: list[str] = []

        proto_a = _TrackingProto("alpha", setup_log, teardown_log)
        proto_b = _TrackingProto("beta", setup_log, teardown_log, fail_setup=True)

        adapter_a = _build_adapter(Alpha, proto_a)
        adapter_b = _build_adapter(Beta, proto_b)

        cs = ComposedSuite({
            "alpha": (Alpha, adapter_a),
            "beta": (Beta, adapter_b),
        })

        with pytest.raises(RuntimeError, match="setup failed: beta"):
            cs.run_test(lambda ctx: None)

        assert "setup:alpha" in setup_log
        assert "setup:beta" in setup_log
        assert "teardown:alpha" in teardown_log
        # beta never completed setup, so it should NOT be torn down
        assert "teardown:beta" not in teardown_log


class TestTraceDomainPrefix:
    def test_trace_entries_carry_domain_prefix(self):
        """Trace entry names should be prefixed with the domain name."""
        setup_log: list[str] = []
        teardown_log: list[str] = []

        proto_a = _TrackingProto("alpha", setup_log, teardown_log)
        proto_b = _TrackingProto("beta", setup_log, teardown_log)

        adapter_a = _build_adapter(Alpha, proto_a)
        adapter_b = _build_adapter(Beta, proto_b)

        cs = ComposedSuite({
            "alpha": (Alpha, adapter_a),
            "beta": (Beta, adapter_b),
        })

        traces = []

        def body(ctx):
            ctx.alpha.when.do_thing()
            ctx.beta.when.do_other()
            traces.extend(ctx.trace())

        cs.run_test(body)

        assert len(traces) == 2
        assert traces[0].name == "Alpha.do_thing"
        assert traces[1].name == "Beta.do_other"
