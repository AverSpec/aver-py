"""aver run — execute tests via pytest."""

import os
import sys


def build_pytest_args(args, passthrough: list[str]) -> list[str]:
    """Build the argument list for pytest.main().

    Returns the list of args to pass to pytest.main().
    """
    return list(passthrough)


def set_env_vars(args) -> None:
    """Set Aver environment variables from parsed CLI flags."""
    if args.aver_adapter is not None:
        os.environ["AVER_ADAPTER"] = args.aver_adapter

    if args.aver_domain is not None:
        os.environ["AVER_DOMAIN"] = args.aver_domain

    if "AVER_AUTOLOAD_CONFIG" not in os.environ:
        os.environ["AVER_AUTOLOAD_CONFIG"] = "true"


def execute_run(args, passthrough: list[str]) -> None:
    """Run pytest with Aver environment configured."""
    import pytest

    set_env_vars(args)
    pytest_args = build_pytest_args(args, passthrough)
    sys.exit(pytest.main(pytest_args))
