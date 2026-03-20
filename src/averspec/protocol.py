"""Protocol interface and built-in unit protocol."""

from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

Ctx = TypeVar("Ctx")


class Protocol(Generic[Ctx]):
    """Base protocol. Subclass or use unit() factory."""

    name: str = "unknown"

    def setup(self) -> Ctx:
        raise NotImplementedError

    def teardown(self, ctx: Ctx) -> None:
        pass


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
    """Wrap a protocol with setup/teardown hooks."""

    class WrappedProtocol(Protocol):
        name = protocol.name

        def setup(self):
            if before:
                before()
            ctx = protocol.setup()
            if after_setup:
                after_setup(ctx)
            return ctx

        def teardown(self, ctx):
            protocol.teardown(ctx)
            if after:
                after()

    return WrappedProtocol()
