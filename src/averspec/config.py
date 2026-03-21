"""Global configuration and adapter registry."""

from __future__ import annotations

from typing import Any

from averspec.adapter import Adapter, AdapterBuilder, AdapterError


class _Registry:
    def __init__(self):
        self._adapters: list[Adapter] = []
        self.teardown_failure_mode: str = "fail"

    def register_adapter(self, adapter: Adapter) -> None:
        self._adapters.append(adapter)

    def find_adapters(self, domain_cls: type) -> list[Adapter]:
        """Find all adapters for a domain, walking the parent chain if needed.

        Exact matches take priority. If none found, walk _aver_parent up
        the chain and stop at the first level with matches.
        """
        # Exact match first
        exact = [a for a in self._adapters if a.domain_cls is domain_cls]
        if exact:
            return exact

        # Walk parent chain
        current = getattr(domain_cls, "_aver_parent", None)
        while current is not None:
            parent_matches = [a for a in self._adapters if a.domain_cls is current]
            if parent_matches:
                return parent_matches
            current = getattr(current, "_aver_parent", None)

        return []

    def find_adapter(self, domain_cls: type) -> Adapter | None:
        """Find a single adapter for a domain, or None."""
        adapters = self.find_adapters(domain_cls)
        return adapters[0] if adapters else None

    def reset(self):
        self._adapters.clear()
        self.teardown_failure_mode = "fail"


_registry = _Registry()


def get_registry() -> _Registry:
    return _registry


def define_config(
    *,
    adapters: list[AdapterBuilder | Adapter],
    teardown_failure_mode: str = "fail",
    **kwargs,
) -> None:
    """Register adapters and configure global settings.

    teardown_failure_mode: "fail" (default) re-raises teardown errors;
                           "warn" logs a warning instead.
    """
    if teardown_failure_mode not in ("fail", "warn"):
        raise ValueError(
            f"teardown_failure_mode must be 'fail' or 'warn', got {teardown_failure_mode!r}"
        )
    _registry.teardown_failure_mode = teardown_failure_mode

    for adapter_or_builder in adapters:
        if isinstance(adapter_or_builder, AdapterBuilder):
            adapter = adapter_or_builder.build()
        elif isinstance(adapter_or_builder, Adapter):
            adapter = adapter_or_builder
        else:
            raise TypeError(
                f"Expected Adapter or AdapterBuilder, got {type(adapter_or_builder).__name__}"
            )
        _registry.register_adapter(adapter)
