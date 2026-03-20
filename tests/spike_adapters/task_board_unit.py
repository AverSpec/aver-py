"""Spike adapter: sync unit adapter for task board."""

from averspec import implement, unit
from tests.spike_domains.task_board import (
    TaskBoard, CreateTaskPayload, MoveTaskPayload, TaskStatusPayload, Task,
)


class Board:
    def __init__(self):
        self.tasks: dict[str, str] = {}

    def create(self, title: str, status: str = "backlog"):
        self.tasks[title] = status

    def move(self, title: str, status: str):
        self.tasks[title] = status

    def details(self, title: str) -> Task | None:
        status = self.tasks.get(title)
        return Task(title=title, status=status) if status else None


adapter = implement(TaskBoard, protocol=unit(lambda: Board()))


@adapter.handle(TaskBoard.create_task)
def create_task(board: Board, p: CreateTaskPayload):
    board.create(p.title, p.status)


@adapter.handle(TaskBoard.move_task)
def move_task(board: Board, p: MoveTaskPayload):
    board.move(p.title, p.status)


@adapter.handle(TaskBoard.task_details)
def task_details(board: Board, title: str) -> Task | None:
    return board.details(title)


@adapter.handle(TaskBoard.task_in_status)
def task_in_status(board: Board, p: TaskStatusPayload):
    task = board.details(p.title)
    assert task is not None, f"Task '{p.title}' not found"
    assert task.status == p.status, f"Expected '{p.title}' in '{p.status}', got '{task.status}'"
