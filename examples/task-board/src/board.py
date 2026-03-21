"""In-memory task board."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    id: str
    title: str
    status: str


class Board:
    def __init__(self):
        self._tasks: list[Task] = []
        self._next_id = 1

    def create(self, title: str, status: str = "backlog") -> Task:
        task = Task(id=str(self._next_id), title=title, status=status)
        self._next_id += 1
        self._tasks.append(task)
        return task

    def move(self, title: str, status: str) -> Task:
        task = self._find(title)
        if task is None:
            raise ValueError(f'Task "{title}" not found')
        task.status = status
        return task

    def delete(self, title: str) -> None:
        task = self._find(title)
        if task is None:
            raise ValueError(f'Task "{title}" not found')
        self._tasks.remove(task)

    def get(self, title: str) -> Task | None:
        return self._find(title)

    def list_by_status(self, status: str) -> list[Task]:
        return [t for t in self._tasks if t.status == status]

    def _find(self, title: str) -> Task | None:
        for t in self._tasks:
            if t.title == title:
                return t
        return None
