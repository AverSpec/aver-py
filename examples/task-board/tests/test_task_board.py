"""Task board acceptance tests."""

from averspec import suite

from domains.task_board import (
    TaskBoard,
    CreateTaskPayload,
    MoveTaskPayload,
    TaskStatusPayload,
    TaskCountPayload,
)

s = suite(TaskBoard)


@s.test
def test_create_task_in_backlog(ctx):
    ctx.when.create_task(CreateTaskPayload(title="Fix login bug"))
    ctx.then.task_in_status(TaskStatusPayload(title="Fix login bug", status="backlog"))
    ctx.then.task_count(TaskCountPayload(status="backlog", count=1))


@s.test
def test_move_task_through_workflow(ctx):
    ctx.given.create_task(CreateTaskPayload(title="Fix login bug"))
    ctx.when.move_task(MoveTaskPayload(title="Fix login bug", status="in-progress"))
    ctx.then.task_in_status(TaskStatusPayload(title="Fix login bug", status="in-progress"))
    ctx.then.task_count(TaskCountPayload(status="backlog", count=0))


@s.test
def test_delete_task(ctx):
    ctx.given.create_task(CreateTaskPayload(title="Stale task"))
    ctx.then.task_count(TaskCountPayload(status="backlog", count=1))
    ctx.when.delete_task("Stale task")
    ctx.then.task_not_found("Stale task")


@s.test
def test_track_full_task_lifecycle(ctx):
    ctx.given.create_task(CreateTaskPayload(title="Fix login bug"))
    ctx.when.move_task(MoveTaskPayload(title="Fix login bug", status="in-progress"))
    ctx.when.move_task(MoveTaskPayload(title="Fix login bug", status="done"))
    ctx.then.task_in_status(TaskStatusPayload(title="Fix login bug", status="done"))
    ctx.then.task_count(TaskCountPayload(status="done", count=1))
