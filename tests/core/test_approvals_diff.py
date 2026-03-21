"""Tests for approval diff and received file lifecycle."""

import os
from pathlib import Path

import pytest

from averspec.approvals import approve


class TestDiffFileWrittenOnMismatch:
    def test_diff_file_written_on_mismatch(self, tmp_path, monkeypatch):
        """approve() should write a .diff.txt when the value differs from the baseline."""
        # Ensure auto-approve is off so mismatches raise
        monkeypatch.delenv("AVER_APPROVE", raising=False)

        name = "snapshot"
        test_name = "test_diff_check"
        approvals_dir = tmp_path / "__approvals__" / test_name

        # Create initial approved baseline by writing the file directly
        approvals_dir.mkdir(parents=True, exist_ok=True)
        import json
        (approvals_dir / f"{name}.approved.json").write_text(
            json.dumps({"count": 1}, indent=2, sort_keys=True), encoding="utf-8"
        )

        # Now change the value and verify mismatch produces a diff
        with pytest.raises(AssertionError, match="Approval mismatch"):
            approve(
                {"count": 99},
                name=name,
                test_name=test_name,
                file_path=str(tmp_path / "fake_test.py"),
            )

        diff_file = approvals_dir / f"{name}.diff.txt"
        received_file = approvals_dir / f"{name}.received.json"

        assert diff_file.exists(), "diff file should be written on mismatch"
        assert received_file.exists(), "received file should be written on mismatch"

        diff_content = diff_file.read_text()
        assert "approved" in diff_content
        assert "received" in diff_content


class TestDiffAndReceivedCleanedOnPass:
    def test_diff_and_received_cleaned_on_pass(self, tmp_path, monkeypatch):
        """After a mismatch, re-approving with the correct value should clean up stale files."""
        # Ensure auto-approve is off so mismatches raise
        monkeypatch.delenv("AVER_APPROVE", raising=False)

        name = "snapshot"
        test_name = "test_cleanup_check"
        approvals_dir = tmp_path / "__approvals__" / test_name

        # Create initial baseline by writing the file directly
        approvals_dir.mkdir(parents=True, exist_ok=True)
        import json
        approved_text = json.dumps({"status": "ok"}, indent=2, sort_keys=True)
        (approvals_dir / f"{name}.approved.json").write_text(approved_text, encoding="utf-8")

        # Cause a mismatch to create .received and .diff files
        with pytest.raises(AssertionError):
            approve(
                {"status": "changed"},
                name=name,
                test_name=test_name,
                file_path=str(tmp_path / "fake_test.py"),
            )

        diff_file = approvals_dir / f"{name}.diff.txt"
        received_file = approvals_dir / f"{name}.received.json"
        assert diff_file.exists()
        assert received_file.exists()

        # Now re-approve with the original (correct) value
        approve(
            {"status": "ok"},
            name=name,
            test_name=test_name,
            file_path=str(tmp_path / "fake_test.py"),
        )

        assert not diff_file.exists(), ".diff.txt should be cleaned up on pass"
        assert not received_file.exists(), ".received file should be cleaned up on pass"
