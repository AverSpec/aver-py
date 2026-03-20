"""Tests for the approval testing module."""

import json
import os
from pathlib import Path

import pytest

from averspec.approvals import approve, characterize, _safe_name, _serialize, _apply_scrubbers


class TestSerialize:
    def test_string_passthrough(self):
        text, ext = _serialize("hello world")
        assert text == "hello world"
        assert ext == "txt"

    def test_dict_to_json(self):
        text, ext = _serialize({"b": 2, "a": 1})
        assert ext == "json"
        parsed = json.loads(text)
        assert parsed == {"a": 1, "b": 2}
        # Sorted keys
        assert text.index('"a"') < text.index('"b"')

    def test_list_to_json(self):
        text, ext = _serialize([1, 2, 3])
        assert ext == "json"
        assert json.loads(text) == [1, 2, 3]

    def test_custom_serializer(self):
        text, ext = _serialize(42, serializer=lambda v: f"value={v}")
        assert text == "value=42"
        assert ext == "txt"


class TestScrubbers:
    def test_single_scrubber(self):
        scrub = [{"pattern": r"\d{4}-\d{2}-\d{2}", "replacement": "<DATE>"}]
        result = _apply_scrubbers("Created on 2026-03-20", scrub)
        assert result == "Created on <DATE>"

    def test_multiple_scrubbers(self):
        import re
        scrub = [
            {"pattern": re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"), "replacement": "<UUID>"},
            {"pattern": r"\d+ms", "replacement": "<TIMING>"},
        ]
        result = _apply_scrubbers(
            "id=550e8400-e29b-41d4-a716-446655440000 took 42ms", scrub
        )
        assert result == "id=<UUID> took <TIMING>"


class TestApproveBaseline:
    def test_creates_baseline_with_auto_approve(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AVER_APPROVE", "1")
        approve(
            "hello baseline",
            name="greeting",
            test_name="test_creates_baseline",
            file_path=str(tmp_path / "test_fake.py"),
        )
        baseline = tmp_path / "__approvals__" / "test_creates_baseline" / "greeting.approved.txt"
        assert baseline.exists()
        assert baseline.read_text() == "hello baseline"

    def test_fails_without_baseline(self, tmp_path):
        with pytest.raises(AssertionError, match="No approved baseline"):
            approve(
                "something",
                name="missing",
                test_name="test_no_baseline",
                file_path=str(tmp_path / "test_fake.py"),
            )

    def test_matches_existing_baseline(self, tmp_path):
        # Manually create a baseline
        base = tmp_path / "__approvals__" / "test_match" / "data.approved.txt"
        base.parent.mkdir(parents=True)
        base.write_text("exact match")

        # Should not raise
        approve(
            "exact match",
            name="data",
            test_name="test_match",
            file_path=str(tmp_path / "test_fake.py"),
        )

    def test_mismatch_raises(self, tmp_path):
        base = tmp_path / "__approvals__" / "test_mismatch" / "output.approved.txt"
        base.parent.mkdir(parents=True)
        base.write_text("original")

        with pytest.raises(AssertionError, match="Approval mismatch"):
            approve(
                "changed",
                name="output",
                test_name="test_mismatch",
                file_path=str(tmp_path / "test_fake.py"),
            )

        received = tmp_path / "__approvals__" / "test_mismatch" / "output.received.txt"
        diff = tmp_path / "__approvals__" / "test_mismatch" / "output.diff.txt"
        assert received.exists()
        assert received.read_text() == "changed"
        assert diff.exists()

    def test_mismatch_updates_with_auto_approve(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AVER_APPROVE", "1")
        base = tmp_path / "__approvals__" / "test_update" / "val.approved.txt"
        base.parent.mkdir(parents=True)
        base.write_text("old")

        approve(
            "new",
            name="val",
            test_name="test_update",
            file_path=str(tmp_path / "test_fake.py"),
        )
        assert base.read_text() == "new"


class TestApproveJSON:
    def test_dict_creates_json_baseline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AVER_APPROVE", "1")
        approve(
            {"status": "ok", "count": 3},
            name="response",
            test_name="test_json",
            file_path=str(tmp_path / "test_fake.py"),
        )
        baseline = tmp_path / "__approvals__" / "test_json" / "response.approved.json"
        assert baseline.exists()
        parsed = json.loads(baseline.read_text())
        assert parsed == {"count": 3, "status": "ok"}


class TestScrubberIntegration:
    def test_scrubber_applied_before_comparison(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AVER_APPROVE", "1")
        scrub = [{"pattern": r"\d+", "replacement": "<NUM>"}]

        # First run: create baseline with scrubbed content
        approve(
            "item 42 costs 100",
            name="scrubbed",
            scrub=scrub,
            test_name="test_scrub",
            file_path=str(tmp_path / "test_fake.py"),
        )
        baseline = tmp_path / "__approvals__" / "test_scrub" / "scrubbed.approved.txt"
        assert baseline.read_text() == "item <NUM> costs <NUM>"

        # Second run with different numbers: should still match
        monkeypatch.delenv("AVER_APPROVE")
        approve(
            "item 99 costs 200",
            name="scrubbed",
            scrub=scrub,
            test_name="test_scrub",
            file_path=str(tmp_path / "test_fake.py"),
        )


class TestCharacterizeAlias:
    def test_characterize_is_approve(self):
        assert characterize is approve

    def test_characterize_callable(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AVER_APPROVE", "1")
        characterize(
            "aliased",
            name="alias_test",
            test_name="test_alias",
            file_path=str(tmp_path / "test_fake.py"),
        )
        baseline = tmp_path / "__approvals__" / "test_alias" / "alias_test.approved.txt"
        assert baseline.exists()


class TestVisualApprove:
    def test_visual_requires_source(self, tmp_path):
        with pytest.raises(ValueError, match="screenshot_path or screenshotter"):
            approve.visual(
                "snap",
                test_name="test_vis",
                file_path=str(tmp_path / "test_fake.py"),
            )

    def test_visual_from_screenshot_path(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AVER_APPROVE", "1")

        # Create a fake screenshot
        img_path = tmp_path / "screenshot.png"
        img_path.write_bytes(b"\x89PNG fake image data")

        approve.visual(
            "snap",
            screenshot_path=str(img_path),
            test_name="test_visual_snap",
            file_path=str(tmp_path / "test_fake.py"),
        )

        baseline = tmp_path / "__approvals__" / "test_visual_snap" / "snap.approved.png"
        assert baseline.exists()
