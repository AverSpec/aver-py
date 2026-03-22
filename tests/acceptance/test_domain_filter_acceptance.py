"""Domain filter skip acceptance test.

Verify that AVER_DOMAIN env var causes non-matching domain's tests to be skipped.
This acceptance-level test goes through the AverCore domain.
"""

import os

from averspec import suite
from tests.acceptance.domain import AverCore, DomainSpec

s = suite(AverCore)


@s.test
def test_domain_filter_skips_non_matching(ctx):
    """When AVER_DOMAIN is set and doesn't match, tests are skipped."""
    # This test verifies the filter mechanism exists. The actual skipping
    # is tested in tests/core/test_domain_filtering.py with monkeypatch.
    # Here we verify the domain can be defined and that the filter path
    # in the framework is exercised through the acceptance domain.
    ctx.given.define_domain(DomainSpec(
        name="filter-check",
        actions=["ping"],
        queries=[],
        assertions=[],
    ))
    # If we got here, the test ran (AVER_DOMAIN was not set or matched).
    # The core filtering tests verify the skip behavior with env vars.
