"""Missing adapter error lists registered adapters.

Verify that when no adapter is found for a domain, the error
message lists what adapters ARE registered.
"""

from averspec import suite
from tests.acceptance.domain import AverCore, MissingAdapterErrorCheck

s = suite(AverCore)


@s.test
def test_missing_adapter_error_lists_registered(ctx):
    """Error message for missing adapter includes registered adapter names."""
    ctx.then.missing_adapter_error_lists_registered(MissingAdapterErrorCheck(
        domain_name="NonExistent",
        expected_registered=["alpha-domain", "beta-domain"],
    ))
