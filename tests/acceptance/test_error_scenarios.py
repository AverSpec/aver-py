"""Error scenario acceptance tests.

Verify that aver-py raises clear, specific errors when the framework
is used incorrectly: missing markers, wrong proxy kinds, incomplete adapters.
"""

import pytest

from averspec import suite
from tests.acceptance.domain import (
    AverCore, DomainSpec, AdapterSpec,
    ProxyRestrictionCheck, CompletenessCheck,
)

s = suite(AverCore)


@s.test
def test_missing_marker_raises_attribute_error(ctx):
    ctx.given.define_domain(DomainSpec(
        name="err-missing",
        actions=["real_action"],
        queries=[],
        assertions=[],
    ))
    ctx.given.create_adapter(AdapterSpec())

    # Reach into the workbench to access the inner domain's context,
    # then attempt to call a marker that does not exist.
    wb = ctx._protocol_ctx
    with pytest.raises(AttributeError, match="no marker 'nonexistent_marker'"):
        wb.current_context.when.nonexistent_marker("payload")


@s.test
def test_wrong_proxy_raises_type_error(ctx):
    ctx.given.define_domain(DomainSpec(
        name="err-wrong-proxy",
        actions=["do_thing"],
        queries=[],
        assertions=["verify_thing"],
    ))
    ctx.given.create_adapter(AdapterSpec())
    ctx.then.proxy_rejects_wrong_kind(ProxyRestrictionCheck(
        proxy_name="when",
        marker_name="verify_thing",
    ))


@s.test
def test_incomplete_adapter_detected(ctx):
    ctx.given.define_domain(DomainSpec(
        name="err-incomplete",
        actions=["handle_this", "handle_that"],
        queries=["fetch_status"],
        assertions=["status_is_ok"],
    ))
    ctx.when.create_adapter(AdapterSpec())
    ctx.then.adapter_is_complete(CompletenessCheck(
        missing=["handle_that", "fetch_status"],
    ))
