"""Retry utility for eventually-consistent assertions."""

from __future__ import annotations

import time


def eventually(
    fn,
    *,
    timeout: float = 5.0,
    interval: float = 0.1,
) -> None:
    """Call fn repeatedly until it passes or timeout is reached.

    Args:
        fn: A callable that raises on failure.
        timeout: Maximum seconds to retry (default 5.0).
        interval: Seconds between retries (default 0.1).

    Raises:
        TimeoutError: With the last failure as __cause__.
    """
    start = time.monotonic()
    last_error: BaseException | None = None
    retries = 0

    while time.monotonic() - start < timeout:
        try:
            fn()
            return
        except Exception as e:
            last_error = e
            retries += 1
            time.sleep(interval)

    # One final attempt after timeout
    try:
        fn()
        return
    except Exception as e:
        last_error = e
        retries += 1

    timeout_ms = int(timeout * 1000)
    last_message = str(last_error)
    error = TimeoutError(
        f"Timed out after {timeout_ms}ms ({retries} retries). Last failure: {last_message}"
    )
    error.__cause__ = last_error
    raise error
