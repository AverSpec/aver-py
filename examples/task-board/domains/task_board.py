"""Task board domain vocabulary."""

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
class TaskCountPayload:
    status: str
    count: int


@dataclass
class Task:
    id: str
    title: str
    status: str


@domain("task-board")
class TaskBoard:
    create_task = action(CreateTaskPayload)
    move_task = action(MoveTaskPayload)
    delete_task = action(str)
    task_details = query(str, Task | None)
    tasks_by_status = query(str, list)
    task_in_status = assertion(TaskStatusPayload)
    task_count = assertion(TaskCountPayload)
    task_not_found = assertion(str)
