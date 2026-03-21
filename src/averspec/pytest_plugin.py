"""pytest plugin for aver — auto-discovered via entry point."""

from __future__ import annotations

import logging
import os
import sys

import pytest

from averspec.config import get_registry
from averspec.suite import Suite, Context
from averspec.protocol import TestMetadata, TestCompletion, Attachment
from averspec.trace_format import format_trace

logger = logging.getLogger("averspec")


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
    """Test context fixture — provides given/when/then/query proxies.

    Lifecycle:
      1. protocol.setup()
      2. protocol.on_test_start(ctx, meta)
      3. yield test_ctx  (test body runs)
      4. If failed: protocol.on_test_fail(ctx, meta) -> attachments
      5. protocol.on_test_end(ctx, completion)
      6. protocol.teardown(ctx)
      7. If failed: enhance error with trace
      8. Teardown errors: obey teardown_failure_mode ("fail" or "warn")
    """
    aver_suite: Suite = request.function._aver_suite
    protocol = _aver_adapter.protocol
    protocol_ctx = protocol.setup()
    test_ctx = Context(aver_suite.domain_cls, _aver_adapter, protocol_ctx)

    meta = TestMetadata(
        test_name=request.node.name,
        domain_name=aver_suite.domain_cls._aver_domain_name,
        adapter_name=_aver_adapter.name,
    )

    # on_test_start
    protocol.on_test_start(protocol_ctx, meta)

    yield test_ctx

    # Determine if the test failed
    test_failed = False
    test_error = None
    # Check if there's an exception from the test body
    exc_info = sys.exc_info()
    if exc_info[1] is not None:
        test_failed = True
        test_error = str(exc_info[1])

    attachments: list[Attachment] = []

    completion = TestCompletion(
        test_name=meta.test_name,
        domain_name=meta.domain_name,
        adapter_name=meta.adapter_name,
        status="fail" if test_failed else "pass",
        error=test_error,
        trace=test_ctx.trace(),
        attachments=attachments,
    )

    # on_test_fail
    if test_failed:
        try:
            attachments.extend(protocol.on_test_fail(protocol_ctx, completion))
            completion.attachments = attachments
        except Exception:
            pass  # Don't mask the original error

    # on_test_end
    try:
        protocol.on_test_end(protocol_ctx, completion)
    except Exception:
        pass  # Don't mask the original error

    # teardown
    registry = get_registry()
    teardown_mode = registry.teardown_failure_mode
    try:
        protocol.teardown(protocol_ctx)
    except Exception as teardown_err:
        if teardown_mode == "warn":
            logger.warning(
                f"Teardown error (suppressed): {teardown_err}"
            )
        else:
            raise

    # Error enhancement: append trace to the error message
    if test_failed and test_ctx.trace():
        trace_text = format_trace(test_ctx.trace())
        # Re-raise with enhanced message by modifying the exception args
        exc = exc_info[1]
        if exc is not None and hasattr(exc, "args") and exc.args:
            original_msg = str(exc.args[0])
            enhanced = f"{original_msg}\n\nTrace:\n{trace_text}"
            exc.args = (enhanced,) + exc.args[1:]
