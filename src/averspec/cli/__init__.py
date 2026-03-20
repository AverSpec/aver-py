"""AverSpec CLI — wraps pytest with domain-driven conventions."""

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    """Entry point for the `aver` command."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="aver",
        description="Domain-driven acceptance testing for Python",
    )
    subparsers = parser.add_subparsers(dest="command")

    # aver run
    run_parser = subparsers.add_parser(
        "run", help="Run tests via pytest", add_help=False,
    )
    run_parser.add_argument("--adapter", dest="aver_adapter", default=None)
    run_parser.add_argument("--domain", dest="aver_domain", default=None)

    # aver approve
    approve_parser = subparsers.add_parser(
        "approve", help="Run tests in approval mode", add_help=False,
    )
    approve_parser.add_argument("--adapter", dest="aver_adapter", default=None)
    approve_parser.add_argument("--domain", dest="aver_domain", default=None)

    # aver init
    subparsers.add_parser("init", help="Scaffold a new domain")

    # Parse only known args so pytest flags pass through
    args, remaining = parser.parse_known_args(argv)

    if args.command == "run":
        from averspec.cli.run import execute_run

        execute_run(args, remaining)

    elif args.command == "approve":
        from averspec.cli.approve import execute_approve

        execute_approve(args, remaining)

    elif args.command == "init":
        from averspec.cli.init_cmd import execute_init

        execute_init()

    else:
        parser.print_help()
        sys.exit(1)
