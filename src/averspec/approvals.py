"""Approval testing for AverSpec."""

from __future__ import annotations

import inspect
import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Protocol as TypingProtocol, runtime_checkable


def _safe_name(name: str) -> str:
    """Convert a name to a filesystem-safe string."""
    return re.sub(r"[^\w\-.]", "_", name)


def _caller_info() -> tuple[str, str]:
    """Walk the stack to find the calling test file and function name."""
    for frame_info in inspect.stack():
        name = frame_info.function
        if name.startswith("test_"):
            return frame_info.filename, name
    # Fallback: use the immediate caller's caller
    frame = inspect.stack()[2]
    return frame.filename, frame.function


# --- Serializer Protocol and Registry ---


@runtime_checkable
class Serializer(TypingProtocol):
    """Protocol for custom serializers."""

    name: str
    file_extension: str

    def serialize(self, value: Any) -> str: ...

    def normalize(self, text: str) -> str:
        """Optional normalization before comparison."""
        ...


class _JsonSerializer:
    name = "json"
    file_extension = "json"

    def serialize(self, value: Any) -> str:
        return json.dumps(value, indent=2, sort_keys=True, default=str)

    def normalize(self, text: str) -> str:
        return text


class _TextSerializer:
    name = "text"
    file_extension = "txt"

    def serialize(self, value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    def normalize(self, text: str) -> str:
        return text


_serializer_registry: dict[str, Serializer] = {
    "json": _JsonSerializer(),
    "text": _TextSerializer(),
}


def register_serializer(name: str, serializer: Serializer) -> None:
    """Register a custom serializer by name."""
    _serializer_registry[name] = serializer


def _get_serializer_registry() -> dict[str, Serializer]:
    """Access the registry (for testing)."""
    return _serializer_registry


def _auto_detect_serializer(value: Any) -> Serializer:
    """Pick a serializer based on value type."""
    if isinstance(value, (dict, list)):
        return _serializer_registry["json"]
    return _serializer_registry["text"]


def _resolve_serializer(
    value: Any,
    serializer_arg: Callable | str | None,
) -> tuple[Serializer | None, Callable | None]:
    """Resolve serializer from argument.

    Returns (registry_serializer, legacy_callable).
    Only one will be non-None.
    """
    if serializer_arg is None:
        return _auto_detect_serializer(value), None
    if isinstance(serializer_arg, str):
        s = _serializer_registry.get(serializer_arg)
        if s is None:
            raise ValueError(
                f"Unknown serializer '{serializer_arg}'. "
                f"Registered: {list(_serializer_registry.keys())}"
            )
        return s, None
    # Legacy callable path
    return None, serializer_arg


def _serialize(value: Any, serializer: Callable | None = None) -> tuple[str, str]:
    """Serialize a value to text. Returns (text, extension)."""
    if serializer is not None:
        return serializer(value), "txt"
    if isinstance(value, str):
        return value, "txt"
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace"), "txt"
    # Dicts, lists, and other objects -> JSON
    return json.dumps(value, indent=2, sort_keys=True, default=str), "json"


def _apply_scrubbers(text: str, scrub: list[dict] | None) -> str:
    """Apply scrubber patterns sequentially."""
    if not scrub:
        return text
    for entry in scrub:
        pattern = entry["pattern"]
        replacement = entry["replacement"]
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        text = pattern.sub(replacement, text)
    return text


def _diff_text(expected: str, actual: str) -> str:
    """Produce a unified diff between expected and actual."""
    import difflib

    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)
    diff = difflib.unified_diff(
        expected_lines, actual_lines, fromfile="approved", tofile="received"
    )
    return "".join(diff)


def _compare_images(approved_path: Path, received_path: Path, threshold: float) -> bool:
    """Compare two images. Returns True if they match within threshold."""
    try:
        from PIL import Image

        img_a = Image.open(approved_path).convert("RGBA")
        img_b = Image.open(received_path).convert("RGBA")

        if img_a.size != img_b.size:
            return False

        pixels_a = img_a.load()
        pixels_b = img_b.load()
        w, h = img_a.size
        total = w * h
        diff_count = 0

        for y in range(h):
            for x in range(w):
                if pixels_a[x, y] != pixels_b[x, y]:
                    diff_count += 1

        return (diff_count / total) <= threshold

    except ImportError:
        # Fallback: byte comparison
        return approved_path.read_bytes() == received_path.read_bytes()


class _Approve:
    """Callable approve object with a .visual attribute."""

    def __call__(
        self,
        value: Any,
        *,
        name: str = "approval",
        serializer: Callable | str | None = None,
        comparator: Callable | None = None,
        scrub: list[dict] | None = None,
        test_name: str | None = None,
        file_path: str | None = None,
    ) -> None:
        auto_approve = os.environ.get("AVER_APPROVE") == "1"

        # Determine caller info
        if file_path is None or test_name is None:
            auto_file, auto_test = _caller_info()
            if file_path is None:
                file_path = auto_file
            if test_name is None:
                test_name = auto_test

        # Resolve serializer (registry or legacy callable)
        registry_ser, legacy_ser = _resolve_serializer(value, serializer)

        if registry_ser is not None:
            text = registry_ser.serialize(value)
            ext = registry_ser.file_extension
        else:
            text, ext = _serialize(value, legacy_ser)

        text = _apply_scrubbers(text, scrub)

        # Build paths
        base_dir = Path(file_path).parent / "__approvals__" / _safe_name(test_name)
        base_dir.mkdir(parents=True, exist_ok=True)

        safe = _safe_name(name)
        approved_path = base_dir / f"{safe}.approved.{ext}"
        received_path = base_dir / f"{safe}.received.{ext}"
        diff_path = base_dir / f"{safe}.diff.txt"

        if not approved_path.exists():
            if auto_approve:
                approved_path.write_text(text, encoding="utf-8")
                # Clean up any stale received/diff files
                received_path.unlink(missing_ok=True)
                diff_path.unlink(missing_ok=True)
                return
            raise AssertionError(
                f"No approved baseline at {approved_path}. "
                f"Run with AVER_APPROVE=1 to create it."
            )

        approved_text = approved_path.read_text(encoding="utf-8")

        # Compare using custom comparator or exact match
        if comparator is not None:
            result = comparator(approved_text, text)
            is_equal = result.get("equal", False) if isinstance(result, dict) else bool(result)
        else:
            is_equal = text == approved_text

        if is_equal:
            # Match: clean up any stale files
            received_path.unlink(missing_ok=True)
            diff_path.unlink(missing_ok=True)
            return

        # Mismatch
        if auto_approve:
            approved_path.write_text(text, encoding="utf-8")
            received_path.unlink(missing_ok=True)
            diff_path.unlink(missing_ok=True)
            return

        received_path.write_text(text, encoding="utf-8")
        diff_text = _diff_text(approved_text, text)
        diff_path.write_text(diff_text, encoding="utf-8")

        raise AssertionError(
            f"Approval mismatch for '{name}'.\n"
            f"  Approved: {approved_path}\n"
            f"  Received: {received_path}\n"
            f"  Diff:     {diff_path}\n"
            f"Run with AVER_APPROVE=1 to update the baseline."
        )

    def visual(
        self,
        name_or_opts: str | dict = "visual",
        *,
        region: str | None = None,
        threshold: float = 0.1,
        test_name: str | None = None,
        file_path: str | None = None,
        screenshot_path: str | None = None,
        screenshotter: Any = None,
    ) -> None:
        """Visual approval: compare screenshots pixel-by-pixel."""
        auto_approve = os.environ.get("AVER_APPROVE") == "1"

        if isinstance(name_or_opts, dict):
            opts = name_or_opts
            name = opts.get("name", "visual")
            region = opts.get("region", region)
            threshold = opts.get("threshold", threshold)
        else:
            name = name_or_opts

        # Determine caller info
        if file_path is None or test_name is None:
            auto_file, auto_test = _caller_info()
            if file_path is None:
                file_path = auto_file
            if test_name is None:
                test_name = auto_test

        # Build paths
        base_dir = Path(file_path).parent / "__approvals__" / _safe_name(test_name)
        base_dir.mkdir(parents=True, exist_ok=True)

        safe = _safe_name(name)
        approved_path = base_dir / f"{safe}.approved.png"
        received_path = base_dir / f"{safe}.received.png"

        # Capture screenshot
        if screenshot_path is not None:
            received_path = Path(screenshot_path)
            # Also write to standard received location for consistency
            import shutil

            shutil.copy2(screenshot_path, base_dir / f"{safe}.received.png")
            received_path = base_dir / f"{safe}.received.png"
        elif screenshotter is not None:
            screenshotter.capture(str(received_path), region=region)
        else:
            raise ValueError(
                "Either screenshot_path or screenshotter must be provided for visual approval."
            )

        if not approved_path.exists():
            if auto_approve:
                import shutil

                shutil.copy2(received_path, approved_path)
                received_path.unlink(missing_ok=True)
                return
            raise AssertionError(
                f"No approved baseline at {approved_path}. "
                f"Run with AVER_APPROVE=1 to create it."
            )

        # Compare
        match = _compare_images(approved_path, received_path, threshold)

        if match:
            received_path.unlink(missing_ok=True)
            return

        if auto_approve:
            import shutil

            shutil.copy2(received_path, approved_path)
            received_path.unlink(missing_ok=True)
            return

        raise AssertionError(
            f"Visual mismatch for '{name}'.\n"
            f"  Approved: {approved_path}\n"
            f"  Received: {received_path}\n"
            f"Run with AVER_APPROVE=1 to update the baseline."
        )


approve = _Approve()
characterize = approve
