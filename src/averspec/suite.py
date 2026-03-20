"""Suite, Context, and narrative proxies."""

from __future__ import annotations

import time
from typing import Any, Callable

from averspec.adapter import Adapter
from averspec.domain import Marker, MarkerKind
from averspec.trace import TraceEntry


class NarrativeProxy:
    """Provides ctx.when.create_task(payload) style access."""

    def __init__(
        self,
        domain_cls: type,
        adapter: Adapter,
        protocol_ctx: Any,
        trace: list[TraceEntry],
        category: str,
        allowed_kinds: set[MarkerKind],
    ):
        self._domain = domain_cls
        self._adapter = adapter
        self._ctx = protocol_ctx
        self._trace = trace
        self._category = category
        self._allowed_kinds = allowed_kinds

    def __getattr__(self, name: str) -> Callable:
        markers = self._domain._aver_markers
        marker = markers.get(name)

        if marker is None:
            raise AttributeError(
                f"Domain '{self._domain._aver_domain_name}' has no marker '{name}'"
            )

        if marker.kind not in self._allowed_kinds:
            kind_names = ", ".join(k.value for k in self._allowed_kinds)
            raise TypeError(
                f"ctx.{self._category}.{name} — '{name}' is a {marker.kind.value}, "
                f"but ctx.{self._category} only accepts {kind_names}"
            )

        def invoke(payload=None):
            start = time.perf_counter()
            try:
                result = self._adapter.execute_sync(marker.name, self._ctx, payload)
                elapsed = time.perf_counter() - start
                self._trace.append(
                    TraceEntry(
                        kind=marker.kind.value,
                        category=self._category,
                        name=f"{self._domain._aver_domain_name}.{marker.name}",
                        payload=payload,
                        status="pass",
                        duration_ms=elapsed * 1000,
                        result=result,
                    )
                )
                return result
            except Exception as e:
                elapsed = time.perf_counter() - start
                self._trace.append(
                    TraceEntry(
                        kind=marker.kind.value,
                        category=self._category,
                        name=f"{self._domain._aver_domain_name}.{marker.name}",
                        payload=payload,
                        status="fail",
                        duration_ms=elapsed * 1000,
                        error=str(e),
                    )
                )
                raise

        return invoke


class Context:
    """Test context with narrative proxies, injected into test functions."""

    def __init__(self, domain_cls: type, adapter: Adapter, protocol_ctx: Any):
        self._trace_entries: list[TraceEntry] = []
        self._adapter = adapter
        self._protocol_ctx = protocol_ctx

        self.given = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "given", {MarkerKind.ACTION, MarkerKind.ASSERTION},
        )
        self.when = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "when", {MarkerKind.ACTION},
        )
        self.then = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "then", {MarkerKind.ASSERTION},
        )
        self.query = NarrativeProxy(
            domain_cls, adapter, protocol_ctx, self._trace_entries,
            "query", {MarkerKind.QUERY},
        )

    def trace(self) -> list[TraceEntry]:
        return list(self._trace_entries)


class Suite:
    """Test suite for a domain. Provides @s.test decorator."""

    def __init__(self, domain_cls: type):
        if not getattr(domain_cls, "_aver_is_domain", False):
            raise TypeError(
                f"{domain_cls.__name__} is not a domain. Decorate it with @domain first."
            )
        self.domain_cls = domain_cls

    def test(self, fn: Callable) -> Callable:
        """Decorator that marks a test function for aver collection."""
        if not fn.__name__.startswith("test_"):
            raise ValueError(
                f"@s.test function must start with 'test_', got '{fn.__name__}'. "
                f"Rename to 'test_{fn.__name__}' for pytest collection."
            )
        fn._aver_suite = self
        return fn


def suite(domain_cls: type) -> Suite:
    """Create a test suite for a domain."""
    return Suite(domain_cls)
