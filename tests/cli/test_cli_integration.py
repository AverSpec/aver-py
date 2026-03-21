"""Integration tests for CLI — test actual function execution, not just arg parsing."""

import os
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

import pytest

from averspec.cli import main
from averspec.cli.run import execute_run
from averspec.cli.scaffold import scaffold_domain


class TestAverRunExecutesPytest:
    def test_execute_run_calls_pytest_and_returns(self, tmp_path):
        """execute_run should invoke pytest.main and exit with its return code."""
        # Create a trivial passing test file
        test_file = tmp_path / "test_trivial.py"
        test_file.write_text("def test_passes():\n    assert True\n")

        args = Namespace(aver_adapter=None, aver_domain=None)

        with pytest.raises(SystemExit) as exc_info:
            execute_run(args, [str(test_file)])

        assert exc_info.value.code == 0


class TestAverInitCreatesFiles:
    def test_scaffold_creates_all_expected_files(self, tmp_path):
        """scaffold_domain should create domain, adapter, test, and conftest files."""
        created = scaffold_domain(
            snake_name="widget",
            class_name="Widget",
            domain_label="Widget",
            protocol="unit",
            base_dir=tmp_path,
        )

        assert (tmp_path / "domains" / "widget.py").exists()
        assert (tmp_path / "adapters" / "widget_unit.py").exists()
        assert (tmp_path / "tests" / "test_widget.py").exists()
        assert (tmp_path / "conftest.py").exists()
        assert len(created) == 4


class TestAverHelpExitsZero:
    def test_help_exits_zero(self):
        """main() with --help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            main(["--help"])

        assert exc_info.value.code == 0

    def test_run_help_exits_zero(self):
        """main() with run --help should not crash.

        run subparser uses add_help=False, so --help falls through to pytest.
        Verify it doesn't raise an unhandled exception.
        """
        # Since run's add_help=False, --help is a passthrough arg.
        # We just verify main doesn't raise before reaching pytest.
        # This will call sys.exit via pytest.main, so we catch SystemExit.
        with pytest.raises(SystemExit):
            main(["run", "--help"])
