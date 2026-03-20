"""Spike domain: task board."""

from dataclasses import dataclass
from averspec import domain, action, query, assertion


@dataclass
class CreateTaskPayload:
    title: str
    status: str = "backlog"


@dataclass
class MoveTaskPayload:
    title: str
    status: str


@dataclass
class TaskStatusPayload:
    title: str
    status: str


@dataclass
class Task:
    title: str
    status: str


@domain("task-board")
class TaskBoard:
    create_task = action(CreateTaskPayload)
    move_task = action(MoveTaskPayload)
    task_details = query(str, Task)
    task_in_status = assertion(TaskStatusPayload)
