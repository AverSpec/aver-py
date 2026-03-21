"""Telemetry verification mode resolution."""

from __future__ import annotations

import os
from typing import Literal

TelemetryMode = Literal["warn", "fail", "off"]

_VALID_MODES: set[str] = {"warn", "fail", "off"}


def resolve_telemetry_mode(override: TelemetryMode | None = None) -> TelemetryMode:
    """Resolve the telemetry verification mode.

    Priority:
    1. Explicit override parameter
    2. AVER_TELEMETRY_MODE env var
    3. Default: "fail" if CI env var is set, "warn" otherwise
    """
    if override is not None:
        if override not in _VALID_MODES:
            raise ValueError(
                f"Invalid telemetry mode '{override}'. "
                f"Valid values: {', '.join(sorted(_VALID_MODES))}"
            )
        return override

    env_mode = os.environ.get("AVER_TELEMETRY_MODE")
    if env_mode is not None:
        if env_mode not in _VALID_MODES:
            raise ValueError(
                f"Invalid AVER_TELEMETRY_MODE '{env_mode}'. "
                f"Valid values: {', '.join(sorted(_VALID_MODES))}"
            )
        return env_mode  # type: ignore[return-value]

    # Default: fail on CI, warn locally
    if os.environ.get("CI"):
        return "fail"
    return "warn"
