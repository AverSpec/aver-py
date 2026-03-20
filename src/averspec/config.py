"""Global configuration and adapter registry."""

from __future__ import annotations

from typing import Any

from averspec.adapter import Adapter, AdapterBuilder, AdapterError


class _Registry:
    def __init__(self):
        self._adapters: list[Adapter] = []

    def register_adapter(self, adapter: Adapter) -> None:
        self._adapters.append(adapter)

    def find_adapters(self, domain_cls: type) -> list[Adapter]:
        return [a for a in self._adapters if a.domain_cls is domain_cls]

    def reset(self):
        self._adapters.clear()


_registry = _Registry()


def get_registry() -> _Registry:
    return _registry


def define_config(*, adapters: list[AdapterBuilder | Adapter], **kwargs) -> None:
    """Register adapters. Validates completeness for any AdapterBuilder."""
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
