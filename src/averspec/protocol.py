"""Protocol interface and built-in unit protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from averspec.telemetry_types import CollectedSpan
    from averspec.trace import TraceEntry

Ctx = TypeVar("Ctx")


@dataclass
class TestMetadata:
    test_name: str
    domain_name: str
    adapter_name: str


@dataclass
class Attachment:
    name: str
    path: str
    mime: str


@dataclass
class TestCompletion(TestMetadata):
    status: str = "pass"  # "pass" or "fail"
    error: str | None = None
    trace: list[TraceEntry] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)


class TelemetryCollector:
    """Interface for collecting telemetry spans during test execution."""

    def get_spans(self) -> list[CollectedSpan]:
        raise NotImplementedError

    def reset(self) -> None:
        raise NotImplementedError


class Protocol(Generic[Ctx]):
    """Base protocol. Subclass or use unit() factory."""

    name: str = "unknown"
    telemetry: TelemetryCollector | None = None

    def setup(self) -> Ctx:
        raise NotImplementedError

    def teardown(self, ctx: Ctx) -> None:
        pass

    def on_test_start(self, ctx: Ctx, meta: TestMetadata) -> None:
        """Called before the test body. Override to hook into test lifecycle."""
        pass

    def on_test_end(self, ctx: Ctx, meta: TestCompletion) -> None:
        """Called after the test body (pass or fail). Override to hook into test lifecycle."""
        pass

    def on_test_fail(self, ctx: Ctx, meta: TestCompletion) -> list[Attachment]:
        """Called on test failure. Override to collect artifacts. Returns attachments."""
        return []


class UnitProtocol(Protocol):
    """Built-in protocol for direct interface testing."""

    name = "unit"

    def __init__(self, factory: Callable, name: str = "unit"):
        self._factory = factory
        self.name = name

    def setup(self):
        return self._factory()

    def teardown(self, ctx) -> None:
        pass


def unit(factory: Callable, name: str = "unit") -> UnitProtocol:
    """Create a unit protocol that wraps a factory callable."""
    return UnitProtocol(factory, name)


def with_fixture(protocol: Protocol, *, before=None, after_setup=None, after=None) -> Protocol:
    """Wrap a protocol with setup/teardown hooks.

    - Passes through protocol extensions (telemetry, etc.)
    - Runs after() even if teardown() throws
    - Handles protocols without optional hooks gracefully
    """

    class WrappedProtocol(Protocol):
        name = protocol.name
        telemetry = getattr(protocol, "telemetry", None)

        def setup(self):
            if before:
                before()
            ctx = protocol.setup()
            if after_setup:
                after_setup(ctx)
            return ctx

        def teardown(self, ctx):
            try:
                protocol.teardown(ctx)
            finally:
                if after:
                    after()

        def on_test_start(self, ctx, meta):
            if hasattr(protocol, "on_test_start"):
                protocol.on_test_start(ctx, meta)

        def on_test_end(self, ctx, meta):
            if hasattr(protocol, "on_test_end"):
                protocol.on_test_end(ctx, meta)

        def on_test_fail(self, ctx, meta):
            if hasattr(protocol, "on_test_fail"):
                return protocol.on_test_fail(ctx, meta)
            return []

    wrapped = WrappedProtocol()

    # Pass through any extra attributes from the original protocol
    for attr in dir(protocol):
        if attr.startswith("_") or attr in ("name", "telemetry", "setup", "teardown",
                                             "on_test_start", "on_test_end", "on_test_fail"):
            continue
        if not hasattr(wrapped, attr):
            try:
                setattr(wrapped, attr, getattr(protocol, attr))
            except AttributeError:
                pass

    return wrapped
