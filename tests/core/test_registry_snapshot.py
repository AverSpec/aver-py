"""Tests for registry snapshot and restore."""

import pytest

from averspec import domain, action, implement, unit, define_config
from averspec.config import get_registry, snapshot_registry, restore_registry


@domain("SnapDomain")
class SnapDomain:
    do_thing = action()


def _make_adapter():
    proto = unit(lambda: None)
    builder = implement(SnapDomain, protocol=proto)

    @builder.handle(SnapDomain.do_thing)
    def handle(ctx):
        pass

    return builder.build()


@pytest.fixture(autouse=True)
def _clean_registry():
    """Reset registry before and after each test."""
    reg = get_registry()
    reg.reset()
    yield
    reg.reset()


class TestSnapshotCapturesCurrentState:
    def test_snapshot_captures_current_state(self):
        reg = get_registry()
        adapter = _make_adapter()
        reg.register_adapter(adapter)
        reg.teardown_failure_mode = "warn"

        snap = snapshot_registry()

        assert len(snap["adapters"]) == 1
        assert snap["adapters"][0] is adapter
        assert snap["mode"] == "warn"


class TestRestoreReturnsToPreviousState:
    def test_restore_returns_to_previous_state(self):
        reg = get_registry()

        # Take snapshot of empty registry
        snap = snapshot_registry()
        assert len(snap["adapters"]) == 0

        # Add an adapter
        adapter = _make_adapter()
        reg.register_adapter(adapter)
        assert len(reg._adapters) == 1

        # Restore to empty state
        restore_registry(snap)
        assert len(reg._adapters) == 0
        assert reg.teardown_failure_mode == "fail"


class TestRestoreClearsAdaptersAddedAfterSnapshot:
    def test_restore_clears_adapters_added_after_snapshot(self):
        reg = get_registry()

        # Register one adapter, snapshot
        adapter1 = _make_adapter()
        reg.register_adapter(adapter1)
        snap = snapshot_registry()

        # Register a second adapter
        adapter2 = _make_adapter()
        reg.register_adapter(adapter2)
        assert len(reg._adapters) == 2

        # Restore: only the first adapter should remain
        restore_registry(snap)
        assert len(reg._adapters) == 1
        assert reg._adapters[0] is adapter1


class TestSnapshotIsolatesFromMutations:
    def test_snapshot_isolates_from_mutations(self):
        reg = get_registry()
        adapter = _make_adapter()
        reg.register_adapter(adapter)

        snap = snapshot_registry()

        # Mutate the live registry
        reg._adapters.clear()
        reg.teardown_failure_mode = "warn"

        # Snapshot should be unaffected
        assert len(snap["adapters"]) == 1
        assert snap["mode"] == "fail"

        # Restore from snapshot brings back original state
        restore_registry(snap)
        assert len(reg._adapters) == 1
        assert reg.teardown_failure_mode == "fail"
