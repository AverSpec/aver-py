"""pytest plugin for aver — auto-discovered via entry point."""

from __future__ import annotations

import os

import pytest

from averspec.config import get_registry
from averspec.suite import Suite, Context


def pytest_generate_tests(metafunc):
    """Parameterize @s.test functions by adapter."""
    suite: Suite | None = getattr(metafunc.function, "_aver_suite", None)
    if suite is None:
        return

    registry = get_registry()
    adapters = registry.find_adapters(suite.domain_cls)

    # Filter by AVER_ADAPTER env var
    adapter_filter = os.environ.get("AVER_ADAPTER")
    if adapter_filter:
        adapters = [a for a in adapters if a.name == adapter_filter]

    # Filter by AVER_DOMAIN env var
    domain_filter = os.environ.get("AVER_DOMAIN")
    if domain_filter and suite.domain_cls._aver_domain_name != domain_filter:
        # Skip this test entirely — domain doesn't match
        metafunc.parametrize("_aver_adapter", [], ids=[])
        return

    if not adapters:
        pytest.fail(
            f"No adapters registered for domain '{suite.domain_cls._aver_domain_name}'. "
            f"Did you call define_config(adapters=[...]) in conftest.py?"
        )

    metafunc.parametrize(
        "_aver_adapter",
        adapters,
        ids=[a.name for a in adapters],
        indirect=True,
    )


@pytest.fixture
def _aver_adapter(request):
    """Indirect fixture that provides the current adapter."""
    return request.param


@pytest.fixture
def ctx(_aver_adapter, request):
    """Test context fixture — provides given/when/then/query proxies."""
    suite: Suite = request.function._aver_suite
    protocol_ctx = _aver_adapter.protocol.setup()
    test_ctx = Context(suite.domain_cls, _aver_adapter, protocol_ctx)
    yield test_ctx
    _aver_adapter.protocol.teardown(protocol_ctx)
