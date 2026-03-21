"""HTTP adapter: tests against the FastAPI app via httpx ASGITransport."""

from urllib.parse import quote

import httpx

from averspec import implement, Protocol

from src.app import create_app
from domains.task_board import (
    TaskBoard,
    CreateTaskPayload,
    MoveTaskPayload,
    TaskStatusPayload,
    TaskCountPayload,
    Task,
)


class HttpProtocol(Protocol):
    name = "http"

    def setup(self):
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        client = httpx.AsyncClient(transport=transport, base_url="http://test")
        return client

    def teardown(self, client):
        # AsyncClient.aclose() is async; transport is already cleaned up
        # when the event loop closes, so this is safe to skip.
        pass


adapter = implement(TaskBoard, protocol=HttpProtocol())


@adapter.handle(TaskBoard.create_task)
async def create_task(client: httpx.AsyncClient, p: CreateTaskPayload):
    res = await client.post("/tasks", json={"title": p.title, "status": p.status})
    assert res.status_code == 201, f"Create failed: {res.status_code} {res.text}"


@adapter.handle(TaskBoard.move_task)
async def move_task(client: httpx.AsyncClient, p: MoveTaskPayload):
    res = await client.patch(f"/tasks/{quote(p.title, safe='')}", json={"status": p.status})
    assert res.status_code == 200, f"Move failed: {res.status_code} {res.text}"


@adapter.handle(TaskBoard.delete_task)
async def delete_task(client: httpx.AsyncClient, title: str):
    res = await client.delete(f"/tasks/{quote(title, safe='')}")
    assert res.status_code == 204, f"Delete failed: {res.status_code} {res.text}"


@adapter.handle(TaskBoard.task_details)
async def task_details(client: httpx.AsyncClient, title: str) -> Task | None:
    res = await client.get(f"/tasks/{quote(title, safe='')}")
    if res.status_code == 404:
        return None
    data = res.json()
    return Task(id=data["id"], title=data["title"], status=data["status"])


@adapter.handle(TaskBoard.tasks_by_status)
async def tasks_by_status(client: httpx.AsyncClient, status: str) -> list:
    res = await client.get(f"/tasks?status={quote(status, safe='')}")
    return [Task(id=d["id"], title=d["title"], status=d["status"]) for d in res.json()]


@adapter.handle(TaskBoard.task_in_status)
async def task_in_status(client: httpx.AsyncClient, p: TaskStatusPayload):
    res = await client.get(f"/tasks/{quote(p.title, safe='')}")
    assert res.status_code == 200, f"Task '{p.title}' not found (HTTP {res.status_code})"
    data = res.json()
    assert data["status"] == p.status, f"Expected '{p.title}' in '{p.status}', got '{data['status']}'"


@adapter.handle(TaskBoard.task_count)
async def task_count(client: httpx.AsyncClient, p: TaskCountPayload):
    res = await client.get(f"/tasks?status={quote(p.status, safe='')}")
    tasks = res.json()
    assert len(tasks) == p.count, f"Expected {p.count} tasks in '{p.status}', got {len(tasks)}"


@adapter.handle(TaskBoard.task_not_found)
async def task_not_found(client: httpx.AsyncClient, title: str):
    res = await client.get(f"/tasks/{quote(title, safe='')}")
    assert res.status_code == 404, f"Expected task '{title}' to not exist, got HTTP {res.status_code}"
