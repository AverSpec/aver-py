"""Tests for aver telemetry diagnose and verify commands."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from averspec.cli.telemetry_cmd import execute_diagnose, execute_verify, _resolve_source


class TestDiagnose:
    def test_prints_mode_and_ci(self, capsys):
        with patch.dict(os.environ, {}, clear=True):
            execute_diagnose()
        out = capsys.readouterr().out
        assert "Telemetry mode: warn" in out
        assert "CI detected: False" in out
        assert "OTLP receiver port 4318:" in out

    def test_prints_ci_mode_when_ci_set(self, capsys):
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            execute_diagnose()
        out = capsys.readouterr().out
        assert "Telemetry mode: fail" in out
        assert "CI detected: True" in out

    def test_prints_env_source(self, capsys):
        with patch.dict(os.environ, {"AVER_TELEMETRY_MODE": "off"}, clear=True):
            execute_diagnose()
        out = capsys.readouterr().out
        assert "Telemetry mode: off (source: env)" in out


class TestResolveSource:
    def test_env_source(self):
        with patch.dict(os.environ, {"AVER_TELEMETRY_MODE": "fail"}, clear=True):
            assert _resolve_source() == "env"

    def test_ci_default_source(self):
        with patch.dict(os.environ, {"CI": "true"}, clear=True):
            assert _resolve_source() == "CI default"

    def test_default_source(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _resolve_source() == "default"


class TestVerify:
    def _write_contract(self, tmp_path: Path, domain_name: str = "test-domain") -> Path:
        """Write a minimal contract file."""
        domain_dir = tmp_path / "contracts" / domain_name
        domain_dir.mkdir(parents=True)
        contract = {
            "version": 1,
            "domain": domain_name,
            "testName": "test_create_order",
            "extractedAt": "2026-01-01T00:00:00Z",
            "entry": {
                "testName": "test_create_order",
                "spans": [
                    {
                        "name": "order.create",
                        "attributes": {
                            "order.id": {"kind": "literal", "value": "order-1"},
                        },
                    }
                ],
            },
        }
        file_path = domain_dir / "test-create-order.contract.json"
        file_path.write_text(json.dumps(contract), encoding="utf-8")
        return tmp_path / "contracts"

    def _write_traces(self, tmp_path: Path, *, matching: bool = True) -> Path:
        """Write trace data."""
        traces_dir = tmp_path / "traces"
        traces_dir.mkdir(parents=True)
        spans = []
        if matching:
            spans.append({
                "name": "order.create",
                "attributes": {"order.id": "order-1"},
                "spanId": "span-001",
            })
        traces = [{"traceId": "trace-001", "spans": spans}]
        file_path = traces_dir / "traces.json"
        file_path.write_text(json.dumps(traces), encoding="utf-8")
        return file_path

    def test_verify_passes_on_matching_traces(self, tmp_path, capsys):
        contract_dir = self._write_contract(tmp_path)
        traces_file = self._write_traces(tmp_path, matching=True)

        args = _make_verify_args(
            contract=str(contract_dir),
            traces=str(traces_file),
            verbose=False,
        )

        with _catch_exit() as exit_code:
            execute_verify(args)

        assert exit_code.value == 0
        out = capsys.readouterr().out
        assert "All contracts verified" in out

    def test_verify_fails_on_missing_span(self, tmp_path, capsys):
        contract_dir = self._write_contract(tmp_path)
        traces_file = self._write_traces(tmp_path, matching=False)

        args = _make_verify_args(
            contract=str(contract_dir),
            traces=str(traces_file),
            verbose=False,
        )

        with _catch_exit() as exit_code:
            execute_verify(args)

        assert exit_code.value == 1
        out = capsys.readouterr().out
        assert "violation" in out.lower()

    def test_verify_verbose_shows_details(self, tmp_path, capsys):
        contract_dir = self._write_contract(tmp_path)
        traces_file = self._write_traces(tmp_path, matching=False)

        args = _make_verify_args(
            contract=str(contract_dir),
            traces=str(traces_file),
            verbose=True,
        )

        with _catch_exit() as exit_code:
            execute_verify(args)

        assert exit_code.value == 1
        out = capsys.readouterr().out
        # Verbose output includes specific violation info
        assert "no-matching-traces" in out or "order.create" in out


# --- Helpers ---

class _ExitCode:
    """Mutable container for captured exit code."""
    value: int = 0


class _catch_exit:
    """Context manager that captures SystemExit."""
    def __init__(self):
        self._code = _ExitCode()

    def __enter__(self):
        return self._code

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is SystemExit:
            self._code.value = exc_val.code if exc_val.code is not None else 0
            return True  # suppress
        return False


class _Namespace:
    """Simple namespace for args."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_verify_args(*, contract: str, traces: str, verbose: bool):
    return _Namespace(contract=contract, traces=traces, verbose=verbose)
