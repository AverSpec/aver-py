"""Trace recording for test steps."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from averspec.telemetry_types import TelemetryMatchResult


@dataclass
class TraceEntry:
    kind: str          # "action", "query", "assertion"
    category: str      # "given", "when", "then", "query"
    name: str          # "task-board.create_task"
    payload: Any = None
    status: str = "pass"
    duration_ms: float = 0.0
    result: Any = None
    error: str | None = None
    telemetry: TelemetryMatchResult | None = None
