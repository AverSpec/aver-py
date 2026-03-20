"""Tests for Protocol interface, unit() factory, and with_fixture()."""

from averspec.protocol import Protocol, unit, with_fixture


class TestProtocolInterface:
    def test_can_create_protocol_with_setup_and_teardown(self):
        calls = []

        class TestProto(Protocol):
            name = "test"

            def setup(self):
                calls.append("setup")
                return {"value": 42}

            def teardown(self, ctx):
                calls.append(f"teardown:{ctx['value']}")

        proto = TestProto()
        ctx = proto.setup()
        assert ctx == {"value": 42}

        proto.teardown(ctx)
        assert calls == ["setup", "teardown:42"]


class TestUnit:
    def test_creates_protocol_named_unit(self):
        proto = unit(lambda: {"count": 0})
        assert proto.name == "unit"

    def test_calls_factory_on_setup(self):
        proto = unit(lambda: {"count": 0})
        ctx = proto.setup()
        assert ctx == {"count": 0}

    def test_creates_fresh_context_each_setup(self):
        proto = unit(lambda: {"count": 0})
        ctx1 = proto.setup()
        ctx2 = proto.setup()
        assert ctx1 is not ctx2

    def test_teardown_is_noop(self):
        proto = unit(lambda: {})
        ctx = proto.setup()
        # Should not raise
        result = proto.teardown(ctx)
        assert result is None

    def test_defaults_name_to_unit(self):
        proto = unit(lambda: {"count": 0})
        assert proto.name == "unit"

    def test_uses_custom_name_when_provided(self):
        proto = unit(lambda: {"count": 0}, "in-memory")
        assert proto.name == "in-memory"


class TestWithFixture:
    def test_runs_before_hook(self):
        calls = []
        proto = unit(lambda: {"value": 1})

        wrapped = with_fixture(proto, before=lambda: calls.append("before"))
        ctx = wrapped.setup()
        assert calls == ["before"]
        assert ctx == {"value": 1}

    def test_runs_after_hook_on_teardown(self):
        calls = []
        proto = unit(lambda: {"value": 1})

        wrapped = with_fixture(proto, after=lambda: calls.append("after"))
        ctx = wrapped.setup()
        wrapped.teardown(ctx)
        assert calls == ["after"]

    def test_runs_after_setup_hook(self):
        calls = []
        proto = unit(lambda: {"value": 1})

        wrapped = with_fixture(
            proto,
            after_setup=lambda ctx: calls.append(f"after_setup:{ctx['value']}"),
        )
        ctx = wrapped.setup()
        assert calls == ["after_setup:1"]

    def test_preserves_protocol_name(self):
        proto = unit(lambda: {}, "custom-name")
        wrapped = with_fixture(proto, before=lambda: None)
        assert wrapped.name == "custom-name"
