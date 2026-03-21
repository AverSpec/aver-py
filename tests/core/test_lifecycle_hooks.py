"""Tests for protocol lifecycle hooks: on_test_start, on_test_end, on_test_fail."""

import pytest
from averspec.domain import domain, action, assertion
from averspec.adapter import implement
from averspec.protocol import Protocol, TestMetadata, TestCompletion, Attachment
from averspec.suite import Context


@domain("Lifecycle")
class LifecycleDomain:
    do_thing = action()
    check = assertion()


class LifecycleProtocol(Protocol):
    """Protocol that records lifecycle hook calls."""
    name = "lifecycle"

    def __init__(self):
        self.calls: list[str] = []
        self.last_start_meta: TestMetadata | None = None
        self.last_end_meta: TestCompletion | None = None
        self.last_fail_meta: TestCompletion | None = None
        self.fail_attachments: list[Attachment] = []

    def setup(self):
        return {"log": self.calls}

    def teardown(self, ctx):
        self.calls.append("teardown")

    def on_test_start(self, ctx, meta: TestMetadata):
        self.calls.append("on_test_start")
        self.last_start_meta = meta

    def on_test_end(self, ctx, meta: TestCompletion):
        self.calls.append("on_test_end")
        self.last_end_meta = meta

    def on_test_fail(self, ctx, meta: TestCompletion) -> list[Attachment]:
        self.calls.append("on_test_fail")
        self.last_fail_meta = meta
        return self.fail_attachments


def make_adapter(proto):
    builder = implement(LifecycleDomain, protocol=proto)

    @builder.handle(LifecycleDomain.do_thing)
    def do_thing(ctx, payload=None):
        ctx["log"].append("do_thing")

    @builder.handle(LifecycleDomain.check)
    def check(ctx, payload=None):
        ctx["log"].append("check")

    return builder.build()


class TestLifecycleHooks:
    def test_on_test_start_called_with_metadata(self):
        proto = LifecycleProtocol()
        adapter = make_adapter(proto)
        protocol_ctx = proto.setup()

        meta = TestMetadata(
            test_name="test_example",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
        )
        proto.on_test_start(protocol_ctx, meta)

        assert "on_test_start" in proto.calls
        assert proto.last_start_meta is meta
        assert proto.last_start_meta.test_name == "test_example"
        assert proto.last_start_meta.domain_name == "Lifecycle"

    def test_on_test_end_called_on_pass(self):
        proto = LifecycleProtocol()
        adapter = make_adapter(proto)
        protocol_ctx = proto.setup()

        completion = TestCompletion(
            test_name="test_pass",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
            status="pass",
        )
        proto.on_test_end(protocol_ctx, completion)

        assert "on_test_end" in proto.calls
        assert proto.last_end_meta.status == "pass"

    def test_on_test_end_called_on_fail(self):
        proto = LifecycleProtocol()
        adapter = make_adapter(proto)
        protocol_ctx = proto.setup()

        completion = TestCompletion(
            test_name="test_fail",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
            status="fail",
            error="boom",
        )
        proto.on_test_end(protocol_ctx, completion)

        assert "on_test_end" in proto.calls
        assert proto.last_end_meta.status == "fail"
        assert proto.last_end_meta.error == "boom"

    def test_on_test_fail_returns_attachments(self):
        proto = LifecycleProtocol()
        proto.fail_attachments = [
            Attachment(name="screenshot", path="/tmp/shot.png", mime="image/png"),
        ]
        adapter = make_adapter(proto)
        protocol_ctx = proto.setup()

        completion = TestCompletion(
            test_name="test_with_artifacts",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
            status="fail",
            error="assertion failed",
        )
        attachments = proto.on_test_fail(protocol_ctx, completion)

        assert len(attachments) == 1
        assert attachments[0].name == "screenshot"
        assert attachments[0].path == "/tmp/shot.png"
        assert attachments[0].mime == "image/png"

    def test_lifecycle_order_on_pass(self):
        """on_test_start -> body -> on_test_end -> teardown."""
        proto = LifecycleProtocol()
        adapter = make_adapter(proto)
        protocol_ctx = proto.setup()
        ctx = Context(LifecycleDomain, adapter, protocol_ctx)

        meta = TestMetadata(
            test_name="test_order",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
        )

        proto.on_test_start(protocol_ctx, meta)
        ctx.when.do_thing()  # body
        completion = TestCompletion(
            test_name="test_order",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
            status="pass",
            trace=ctx.trace(),
        )
        proto.on_test_end(protocol_ctx, completion)
        proto.teardown(protocol_ctx)

        assert proto.calls == ["on_test_start", "do_thing", "on_test_end", "teardown"]

    def test_lifecycle_order_on_fail(self):
        """on_test_start -> body -> on_test_fail -> on_test_end -> teardown."""
        proto = LifecycleProtocol()
        adapter = make_adapter(proto)
        protocol_ctx = proto.setup()

        meta = TestMetadata(
            test_name="test_fail_order",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
        )

        proto.on_test_start(protocol_ctx, meta)
        proto.calls.append("body_failed")  # simulate body
        completion = TestCompletion(
            test_name="test_fail_order",
            domain_name="Lifecycle",
            adapter_name="lifecycle",
            status="fail",
            error="boom",
        )
        proto.on_test_fail(protocol_ctx, completion)
        proto.on_test_end(protocol_ctx, completion)
        proto.teardown(protocol_ctx)

        assert proto.calls == [
            "on_test_start", "body_failed",
            "on_test_fail", "on_test_end", "teardown",
        ]
