"""Trace formatting for error output."""

from __future__ import annotations

import json
from typing import Any

from averspec.trace import TraceEntry


def _category_label(entry: TraceEntry) -> str:
    """Return a padded label from category or kind."""
    if entry.category:
        return entry.category.upper().ljust(6)
    # Fallback to kind-based labels
    mapping = {
        "action": "ACT   ",
        "query": "QUERY ",
        "assertion": "ASSERT",
    }
    return mapping.get(entry.kind, entry.kind.upper().ljust(6))


def _serialize_payload(payload: Any) -> str | None:
    """Serialize payload to JSON string, or None if no payload."""
    if payload is None:
        return None
    try:
        return json.dumps(payload)
    except (TypeError, ValueError):
        return "[unserializable]"


def format_trace(entries: list[TraceEntry]) -> str:
    """Format trace entries for human-readable error output.

    Format per line:
        [PASS] WHEN   domain.operation(payload)  3ms
        [FAIL] THEN   domain.assertion(payload)  1ms -- error message
    """
    lines: list[str] = []

    for entry in entries:
        icon = "[PASS]" if entry.status == "pass" else "[FAIL]"
        label = _category_label(entry)

        payload_str = ""
        raw = _serialize_payload(entry.payload)
        if raw is not None:
            if entry.status == "fail" or len(raw) <= 60:
                payload_str = raw
            else:
                payload_str = raw[:57] + "..."

        duration_str = ""
        if entry.duration_ms:
            # Format as integer if whole number, otherwise keep decimal
            ms = entry.duration_ms
            if ms == int(ms):
                duration_str = f"  {int(ms)}ms"
            else:
                duration_str = f"  {ms}ms"

        error_str = ""
        if entry.status == "fail" and entry.error:
            error_str = f" -- {entry.error}"

        line = f"  {icon} {label} {entry.name}({payload_str}){duration_str}{error_str}"
        lines.append(line)

        # Telemetry info
        if entry.telemetry is not None:
            telem = entry.telemetry
            if telem.matched and telem.matched_span:
                attrs_str = ""
                if telem.expected.attributes:
                    attrs_str = f" {json.dumps(telem.expected.attributes)}"
                lines.append(f"         \u2713 telemetry: {telem.expected.span}{attrs_str}")
            else:
                lines.append(
                    f"         \u26a0 telemetry: expected span '{telem.expected.span}' not found"
                )

    return "\n".join(lines)
