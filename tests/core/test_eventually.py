"""Tests for the eventually() retry utility."""

import time

import pytest

from averspec import eventually


def test_resolves_immediately_when_fn_passes_first_try():
    calls = 0

    def fn():
        nonlocal calls
        calls += 1

    eventually(fn)
    assert calls == 1


def test_retries_until_fn_passes():
    calls = 0

    def fn():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise AssertionError("not yet")

    eventually(fn, interval=0.01)
    assert calls == 3


def test_times_out_with_last_failure_and_cause():
    calls = 0

    def fn():
        nonlocal calls
        calls += 1
        raise AssertionError(f"attempt {calls}")

    with pytest.raises(TimeoutError) as exc_info:
        eventually(fn, timeout=0.05, interval=0.01)

    err = exc_info.value
    assert "Timed out after 50ms" in str(err)
    assert "Last failure:" in str(err)
    assert "retries" in str(err)
    assert err.__cause__ is not None
    assert "attempt" in str(err.__cause__)


def test_respects_custom_timeout_and_interval():
    start = time.monotonic()

    with pytest.raises(TimeoutError):
        eventually(
            lambda: (_ for _ in ()).throw(AssertionError("fail")),
            timeout=0.1,
            interval=0.03,
        )

    elapsed = time.monotonic() - start
    assert elapsed >= 0.09
    assert elapsed < 0.5


def test_passes_on_eventual_success():
    """Retries a few times then succeeds."""
    calls = 0

    def fn():
        nonlocal calls
        calls += 1
        if calls < 2:
            raise ValueError("not yet")

    eventually(fn, interval=0.01)
    assert calls == 2
