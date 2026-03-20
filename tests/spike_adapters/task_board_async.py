"""Spike adapter: async adapter for task board — validates async handling."""

import asyncio
from averspec import implement, unit
from tests.spike_domains.task_board import (
    TaskBoard, CreateTaskPayload, MoveTaskPayload, TaskStatusPayload, Task,
)


class AsyncBoard:
    """Simulates an async data store."""

    def __init__(self):
        self.tasks: dict[str, str] = {}

    async def create(self, title: str, status: str = "backlog"):
        await asyncio.sleep(0.001)  # Simulate IO
        self.tasks[title] = status

    async def move(self, title: str, status: str):
        await asyncio.sleep(0.001)
        self.tasks[title] = status

    async def details(self, title: str) -> Task | None:
        await asyncio.sleep(0.001)
        status = self.tasks.get(title)
        return Task(title=title, status=status) if status else None


adapter = implement(TaskBoard, protocol=unit(lambda: AsyncBoard(), name="async"))


@adapter.handle(TaskBoard.create_task)
async def create_task(board: AsyncBoard, p: CreateTaskPayload):
    await board.create(p.title, p.status)


@adapter.handle(TaskBoard.move_task)
async def move_task(board: AsyncBoard, p: MoveTaskPayload):
    await board.move(p.title, p.status)


@adapter.handle(TaskBoard.task_details)
async def task_details(board: AsyncBoard, title: str) -> Task | None:
    return await board.details(title)


@adapter.handle(TaskBoard.task_in_status)
async def task_in_status(board: AsyncBoard, p: TaskStatusPayload):
    task = await board.details(p.title)
    assert task is not None, f"Task '{p.title}' not found"
    assert task.status == p.status, f"Expected '{p.title}' in '{p.status}', got '{task.status}'"
