"""FastAPI task board application."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.board import Board


class CreateTaskBody(BaseModel):
    title: str
    status: str = "backlog"


class UpdateTaskBody(BaseModel):
    status: str


def create_app() -> FastAPI:
    app = FastAPI()
    board = Board()

    @app.post("/tasks", status_code=201)
    def create_task(body: CreateTaskBody):
        task = board.create(body.title, body.status)
        return asdict(task)

    @app.patch("/tasks/{title}")
    def update_task(title: str, body: UpdateTaskBody):
        try:
            task = board.move(title, body.status)
        except ValueError:
            raise HTTPException(status_code=404, detail=f'Task "{title}" not found')
        return asdict(task)

    @app.delete("/tasks/{title}", status_code=204)
    def delete_task(title: str):
        try:
            board.delete(title)
        except ValueError:
            raise HTTPException(status_code=404, detail=f'Task "{title}" not found')

    @app.get("/tasks/{title}")
    def get_task(title: str):
        task = board.get(title)
        if task is None:
            raise HTTPException(status_code=404, detail="Not found")
        return asdict(task)

    @app.get("/tasks")
    def list_tasks(status: str = "backlog"):
        tasks = board.list_by_status(status)
        return [asdict(t) for t in tasks]

    return app
