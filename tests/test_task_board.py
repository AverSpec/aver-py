"""Spike tests: validates all four design spikes.

Spike 1: @domain decorator + markers — TaskBoard domain defined in spike_domains/
Spike 2: @adapter.handle builder — adapters defined in spike_adapters/
Spike 3: @s.test + pytest plugin — parameterized by adapter
Spike 4: Async handling — async adapter runs transparently in sync test
"""

from averspec import suite
from tests.spike_domains.task_board import (
    TaskBoard, CreateTaskPayload, MoveTaskPayload, TaskStatusPayload,
)

s = suite(TaskBoard)


@s.test
def test_create_task_in_backlog(ctx):
    """Test runs against both unit (sync) and async adapters transparently."""
    ctx.when.create_task(CreateTaskPayload(title="Fix bug"))
    ctx.then.task_in_status(TaskStatusPayload(title="Fix bug", status="backlog"))


@s.test
def test_move_task_through_workflow(ctx):
    ctx.given.create_task(CreateTaskPayload(title="Fix bug"))
    ctx.when.move_task(MoveTaskPayload(title="Fix bug", status="in-progress"))
    ctx.then.task_in_status(TaskStatusPayload(title="Fix bug", status="in-progress"))


@s.test
def test_query_returns_typed_result(ctx):
    ctx.when.create_task(CreateTaskPayload(title="Fix bug"))
    task = ctx.query.task_details("Fix bug")
    assert task is not None
    assert task.title == "Fix bug"
    assert task.status == "backlog"


@s.test
def test_trace_records_steps(ctx):
    ctx.when.create_task(CreateTaskPayload(title="Fix bug"))
    ctx.then.task_in_status(TaskStatusPayload(title="Fix bug", status="backlog"))
    steps = ctx.trace()
    assert len(steps) == 2
    assert steps[0].category == "when"
    assert steps[0].name == "task-board.create_task"
    assert steps[0].status == "pass"
    assert steps[1].category == "then"
    assert steps[1].name == "task-board.task_in_status"
    assert steps[1].status == "pass"
