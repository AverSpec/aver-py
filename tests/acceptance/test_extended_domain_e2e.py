"""Extended domain end-to-end in suite.

Verify that an extended domain can be implemented with an adapter,
used in a suite, dispatch operations, and record trace.
"""

from averspec import suite
from tests.acceptance.domain import (
    AverCore, BuildExtendedSuiteSpec, CallExtendedOperationSpec,
    ExtendedSuiteMarkerCountCheck,
)

s = suite(AverCore)


@s.test
def test_extended_domain_end_to_end_in_suite(ctx):
    """Extended domain can be implemented and dispatched through a suite."""
    ctx.given.build_extended_suite(BuildExtendedSuiteSpec(
        parent_actions=["create_task", "delete_task"],
        child_actions=["show_spinner", "hide_spinner"],
    ))
    ctx.then.extended_suite_marker_count_is(ExtendedSuiteMarkerCountCheck(expected=4))
    ctx.when.call_extended_operation(CallExtendedOperationSpec(marker_name="create_task"))
    ctx.when.call_extended_operation(CallExtendedOperationSpec(marker_name="show_spinner"))
