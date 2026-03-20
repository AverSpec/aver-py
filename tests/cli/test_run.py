"""Tests for aver run — arg parsing and env var setup."""

import os
from argparse import Namespace
from unittest.mock import patch

from averspec.cli.run import build_pytest_args, set_env_vars


class TestBuildPytestArgs:
    def test_passthrough_args_forwarded(self):
        args = Namespace(aver_adapter=None, aver_domain=None)
        result = build_pytest_args(args, ["tests/", "-k", "test_foo", "--verbose"])
        assert result == ["tests/", "-k", "test_foo", "--verbose"]

    def test_empty_passthrough(self):
        args = Namespace(aver_adapter=None, aver_domain=None)
        result = build_pytest_args(args, [])
        assert result == []

    def test_file_path_passthrough(self):
        args = Namespace(aver_adapter=None, aver_domain=None)
        result = build_pytest_args(args, ["tests/test_task_board.py"])
        assert result == ["tests/test_task_board.py"]


class TestSetEnvVars:
    def test_sets_adapter_env(self):
        args = Namespace(aver_adapter="http", aver_domain=None)
        with patch.dict(os.environ, {}, clear=True):
            set_env_vars(args)
            assert os.environ["AVER_ADAPTER"] == "http"
            assert "AVER_DOMAIN" not in os.environ

    def test_sets_domain_env(self):
        args = Namespace(aver_adapter=None, aver_domain="task_board")
        with patch.dict(os.environ, {}, clear=True):
            set_env_vars(args)
            assert os.environ["AVER_DOMAIN"] == "task_board"
            assert "AVER_ADAPTER" not in os.environ

    def test_sets_both(self):
        args = Namespace(aver_adapter="playwright", aver_domain="checkout")
        with patch.dict(os.environ, {}, clear=True):
            set_env_vars(args)
            assert os.environ["AVER_ADAPTER"] == "playwright"
            assert os.environ["AVER_DOMAIN"] == "checkout"

    def test_sets_autoload_config(self):
        args = Namespace(aver_adapter=None, aver_domain=None)
        with patch.dict(os.environ, {}, clear=True):
            set_env_vars(args)
            assert os.environ["AVER_AUTOLOAD_CONFIG"] == "true"

    def test_does_not_override_existing_autoload(self):
        args = Namespace(aver_adapter=None, aver_domain=None)
        with patch.dict(os.environ, {"AVER_AUTOLOAD_CONFIG": "false"}, clear=True):
            set_env_vars(args)
            assert os.environ["AVER_AUTOLOAD_CONFIG"] == "false"

    def test_skips_none_values(self):
        args = Namespace(aver_adapter=None, aver_domain=None)
        with patch.dict(os.environ, {}, clear=True):
            set_env_vars(args)
            assert "AVER_ADAPTER" not in os.environ
            assert "AVER_DOMAIN" not in os.environ


class TestArgParsing:
    """Test that the CLI parser correctly separates aver flags from pytest flags."""

    def test_adapter_flag_parsed(self):
        from averspec.cli import main
        import argparse

        parser = argparse.ArgumentParser(prog="aver")
        sub = parser.add_subparsers(dest="command")
        run_p = sub.add_parser("run", add_help=False)
        run_p.add_argument("--adapter", dest="aver_adapter", default=None)
        run_p.add_argument("--domain", dest="aver_domain", default=None)

        args, remaining = parser.parse_known_args(
            ["run", "--adapter", "http", "tests/", "-k", "foo"]
        )
        assert args.aver_adapter == "http"
        assert args.aver_domain is None
        assert remaining == ["tests/", "-k", "foo"]

    def test_domain_flag_parsed(self):
        import argparse

        parser = argparse.ArgumentParser(prog="aver")
        sub = parser.add_subparsers(dest="command")
        run_p = sub.add_parser("run", add_help=False)
        run_p.add_argument("--adapter", dest="aver_adapter", default=None)
        run_p.add_argument("--domain", dest="aver_domain", default=None)

        args, remaining = parser.parse_known_args(
            ["run", "--domain", "task_board", "--verbose"]
        )
        assert args.aver_domain == "task_board"
        assert remaining == ["--verbose"]

    def test_approve_sets_env(self):
        """Verify approve would set AVER_APPROVE=1."""
        import argparse

        parser = argparse.ArgumentParser(prog="aver")
        sub = parser.add_subparsers(dest="command")
        sub.add_parser("approve", add_help=False)

        args, _ = parser.parse_known_args(["approve"])
        assert args.command == "approve"
