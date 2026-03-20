"""aver approve — run tests in approval mode."""

import os
import sys


def execute_approve(args, passthrough: list[str]) -> None:
    """Run pytest with AVER_APPROVE=1 set."""
    import pytest

    from averspec.cli.run import build_pytest_args, set_env_vars

    os.environ["AVER_APPROVE"] = "1"
    set_env_vars(args)
    pytest_args = build_pytest_args(args, passthrough)
    sys.exit(pytest.main(pytest_args))
