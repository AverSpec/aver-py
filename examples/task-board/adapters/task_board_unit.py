"""Unit adapter: tests against the Board class directly."""

from averspec import implement, unit

from src.board import Board
from domains.task_board import (
    TaskBoard,
    CreateTaskPayload,
    MoveTaskPayload,
    TaskStatusPayload,
    TaskCountPayload,
    Task,
)

adapter = implement(TaskBoard, protocol=unit(lambda: Board()))


@adapter.handle(TaskBoard.create_task)
def create_task(board: Board, p: CreateTaskPayload):
    board.create(p.title, p.status)


@adapter.handle(TaskBoard.move_task)
def move_task(board: Board, p: MoveTaskPayload):
    board.move(p.title, p.status)


@adapter.handle(TaskBoard.delete_task)
def delete_task(board: Board, title: str):
    board.delete(title)


@adapter.handle(TaskBoard.task_details)
def task_details(board: Board, title: str) -> Task | None:
    t = board.get(title)
    if t is None:
        return None
    return Task(id=t.id, title=t.title, status=t.status)


@adapter.handle(TaskBoard.tasks_by_status)
def tasks_by_status(board: Board, status: str) -> list:
    return [Task(id=t.id, title=t.title, status=t.status) for t in board.list_by_status(status)]


@adapter.handle(TaskBoard.task_in_status)
def task_in_status(board: Board, p: TaskStatusPayload):
    task = board.get(p.title)
    assert task is not None, f"Task '{p.title}' not found"
    assert task.status == p.status, f"Expected '{p.title}' in '{p.status}', got '{task.status}'"


@adapter.handle(TaskBoard.task_count)
def task_count(board: Board, p: TaskCountPayload):
    tasks = board.list_by_status(p.status)
    assert len(tasks) == p.count, f"Expected {p.count} tasks in '{p.status}', got {len(tasks)}"


@adapter.handle(TaskBoard.task_not_found)
def task_not_found(board: Board, title: str):
    task = board.get(title)
    assert task is None, f"Expected task '{title}' to not exist, but it does"
