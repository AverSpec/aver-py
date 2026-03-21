"""Tests for telemetry mode resolution."""

import os
import pytest

from averspec.telemetry_mode import resolve_telemetry_mode


def test_default_mode_on_ci(monkeypatch):
    monkeypatch.setenv("CI", "true")
    monkeypatch.delenv("AVER_TELEMETRY_MODE", raising=False)
    assert resolve_telemetry_mode() == "fail"


def test_default_mode_locally(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("AVER_TELEMETRY_MODE", raising=False)
    assert resolve_telemetry_mode() == "warn"


def test_explicit_override():
    assert resolve_telemetry_mode("off") == "off"
    assert resolve_telemetry_mode("fail") == "fail"
    assert resolve_telemetry_mode("warn") == "warn"


def test_env_var_override(monkeypatch):
    monkeypatch.setenv("AVER_TELEMETRY_MODE", "off")
    monkeypatch.delenv("CI", raising=False)
    assert resolve_telemetry_mode() == "off"


def test_invalid_mode_raises():
    with pytest.raises(ValueError, match="Invalid telemetry mode"):
        resolve_telemetry_mode("invalid")


def test_invalid_env_var_raises(monkeypatch):
    monkeypatch.setenv("AVER_TELEMETRY_MODE", "bogus")
    with pytest.raises(ValueError, match="Invalid AVER_TELEMETRY_MODE"):
        resolve_telemetry_mode()
