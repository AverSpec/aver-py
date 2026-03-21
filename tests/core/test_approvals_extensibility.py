"""Tests for approvals extensibility: comparators, serializers, cleanup."""

import os
from pathlib import Path

from averspec.approvals import (
    approve,
    register_serializer,
    _get_serializer_registry,
    _safe_name,
)


def test_custom_comparator_ignores_whitespace(tmp_path, monkeypatch):
    """Custom comparator that strips whitespace before comparing."""
    monkeypatch.setenv("AVER_APPROVE", "1")

    # Create baseline with trailing whitespace
    approve(
        "hello world  ",
        name="cmp",
        test_name="test_custom_comparator_ignores_whitespace",
        file_path=str(tmp_path / "fake_test.py"),
    )

    monkeypatch.delenv("AVER_APPROVE")

    # Now compare with different whitespace using custom comparator
    def ws_comparator(approved, received):
        return {"equal": approved.strip() == received.strip()}

    approve(
        "hello world",
        name="cmp",
        comparator=ws_comparator,
        test_name="test_custom_comparator_ignores_whitespace",
        file_path=str(tmp_path / "fake_test.py"),
    )


def test_custom_serializer_registered(tmp_path, monkeypatch):
    """Register a custom serializer and use it by name."""

    class CsvSerializer:
        name = "csv"
        file_extension = "csv"

        def serialize(self, value):
            # value is a list of dicts
            if not value:
                return ""
            headers = list(value[0].keys())
            lines = [",".join(headers)]
            for row in value:
                lines.append(",".join(str(row[h]) for h in headers))
            return "\n".join(lines)

        def normalize(self, text):
            return text

    register_serializer("csv", CsvSerializer())

    monkeypatch.setenv("AVER_APPROVE", "1")

    data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
    approve(
        data,
        name="people",
        serializer="csv",
        test_name="test_custom_serializer_registered",
        file_path=str(tmp_path / "fake_test.py"),
    )

    # Verify file was written with .csv extension
    approvals_dir = tmp_path / "__approvals__" / "test_custom_serializer_registered"
    approved_file = approvals_dir / "people.approved.csv"
    assert approved_file.exists()
    content = approved_file.read_text()
    assert "Alice" in content
    assert "Bob" in content

    # Cleanup: remove from registry to not affect other tests
    del _get_serializer_registry()["csv"]


def test_serializer_auto_detect_json(tmp_path, monkeypatch):
    """Dicts auto-detect to json serializer."""
    monkeypatch.setenv("AVER_APPROVE", "1")

    approve(
        {"key": "value"},
        name="auto",
        test_name="test_serializer_auto_detect_json",
        file_path=str(tmp_path / "fake_test.py"),
    )

    approvals_dir = tmp_path / "__approvals__" / "test_serializer_auto_detect_json"
    assert (approvals_dir / "auto.approved.json").exists()


def test_serializer_auto_detect_text(tmp_path, monkeypatch):
    """Strings auto-detect to text serializer."""
    monkeypatch.setenv("AVER_APPROVE", "1")

    approve(
        "plain string",
        name="auto",
        test_name="test_serializer_auto_detect_text",
        file_path=str(tmp_path / "fake_test.py"),
    )

    approvals_dir = tmp_path / "__approvals__" / "test_serializer_auto_detect_text"
    assert (approvals_dir / "auto.approved.txt").exists()


def test_cleanup_received_diff_on_pass(tmp_path, monkeypatch):
    """When approval matches, leftover .received and .diff files are cleaned up."""
    monkeypatch.setenv("AVER_APPROVE", "1")

    approve(
        "stable content",
        name="cleanup",
        test_name="test_cleanup_received_diff_on_pass",
        file_path=str(tmp_path / "fake_test.py"),
    )

    monkeypatch.delenv("AVER_APPROVE")

    # Manually create stale .received and .diff files
    approvals_dir = tmp_path / "__approvals__" / "test_cleanup_received_diff_on_pass"
    received = approvals_dir / "cleanup.received.txt"
    diff = approvals_dir / "cleanup.diff.txt"
    received.write_text("old received content")
    diff.write_text("old diff content")

    assert received.exists()
    assert diff.exists()

    # Run approval again with matching content
    approve(
        "stable content",
        name="cleanup",
        test_name="test_cleanup_received_diff_on_pass",
        file_path=str(tmp_path / "fake_test.py"),
    )

    # Stale files should be gone
    assert not received.exists()
    assert not diff.exists()


def test_register_serializer_appears_in_registry():
    """register_serializer adds to the global registry."""

    class YamlSerializer:
        name = "yaml"
        file_extension = "yaml"

        def serialize(self, value):
            return str(value)

        def normalize(self, text):
            return text

    register_serializer("yaml", YamlSerializer())
    registry = _get_serializer_registry()
    assert "yaml" in registry
    assert registry["yaml"].file_extension == "yaml"

    # Cleanup
    del registry["yaml"]
