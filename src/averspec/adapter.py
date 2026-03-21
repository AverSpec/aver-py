"""Adapter builder pattern: implement() + @adapter.handle(marker)."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from averspec.domain import Marker, MarkerKind


class AdapterError(Exception):
    pass


class Adapter:
    """A bound adapter: domain + protocol + handlers."""

    def __init__(self, domain_cls: type, protocol: Any, handlers: dict[str, tuple[Callable, int]]):
        self.domain_cls = domain_cls
        self.protocol = protocol
        self.handlers = handlers

    @property
    def name(self) -> str:
        return self.protocol.name

    @property
    def domain_name(self) -> str:
        return self.domain_cls._aver_domain_name

    def execute_sync(self, marker_name: str, ctx: Any, payload: Any = None) -> Any:
        """Execute a handler, transparently handling async."""
        handler, param_count = self.handlers[marker_name]

        if param_count >= 2:
            result = handler(ctx, payload)
        else:
            result = handler(ctx)

        if inspect.isawaitable(result):
            return asyncio.run(result)

        return result


class AdapterBuilder:
    """Builder that collects @handle-decorated functions."""

    def __init__(self, domain_cls: type, protocol: Any):
        self.domain_cls = domain_cls
        self.protocol = protocol
        self._handlers: dict[str, Callable] = {}

    def handle(self, marker: Marker) -> Callable:
        """Decorator that registers a handler for a domain marker."""
        if not isinstance(marker, Marker):
            raise TypeError(
                f"@adapter.handle() expects a Marker, got {type(marker).__name__}. "
                f"Use @adapter.handle(MyDomain.some_action)"
            )
        if marker.name is None:
            raise AdapterError(
                "Marker has no name — was it defined on a @domain-decorated class?"
            )

        def decorator(fn: Callable) -> Callable:
            self._handlers[marker.name] = fn
            return fn

        return decorator

    def build(self) -> Adapter:
        """Validate completeness and return the Adapter."""
        domain_markers = self.domain_cls._aver_markers

        missing = set(domain_markers.keys()) - set(self._handlers.keys())
        if missing:
            raise AdapterError(
                f"Adapter for '{self.domain_cls._aver_domain_name}' is missing handlers for: "
                f"{', '.join(sorted(missing))}"
            )

        extra = set(self._handlers.keys()) - set(domain_markers.keys())
        if extra:
            raise AdapterError(
                f"Adapter for '{self.domain_cls._aver_domain_name}' has handlers "
                f"for markers not in domain: {', '.join(sorted(extra))}"
            )

        # Cache handler param counts at build time so execute_sync()
        # doesn't call inspect.signature() on every invocation.
        handlers_with_params: dict[str, tuple[Callable, int]] = {}
        for name, fn in self._handlers.items():
            sig = inspect.signature(fn)
            handlers_with_params[name] = (fn, len(sig.parameters))

        return Adapter(self.domain_cls, self.protocol, handlers_with_params)


def implement(domain_cls: type, *, protocol: Any) -> AdapterBuilder:
    """Create an adapter builder for a domain + protocol."""
    if not getattr(domain_cls, "_aver_is_domain", False):
        raise TypeError(
            f"{domain_cls.__name__} is not a domain. Decorate it with @domain first."
        )
    return AdapterBuilder(domain_cls, protocol)


adapt = implement
