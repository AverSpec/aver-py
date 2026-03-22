# averspec

Domain-driven acceptance testing for Python.

Same test, every adapter. Define behavior once, verify it at unit, HTTP, and browser levels.

## Install

```bash
pip install averspec
```

## Quick Example

```python
from averspec import domain, action, assertion, implement, suite, unit

@domain("task-board")
class TaskBoard:
    create_task = action(dict)
    task_in_status = assertion(dict)

adapter = implement(TaskBoard, protocol=unit(lambda: {}))

@adapter.handle(TaskBoard.create_task)
def create_task(board, p):
    board[p["title"]] = p.get("status", "backlog")

@adapter.handle(TaskBoard.task_in_status)
def task_in_status(board, p):
    assert board.get(p["title"]) == p["status"]

s = suite(TaskBoard)

@s.test
def test_create_task(ctx):
    ctx.when.create_task({"title": "Fix bug"})
    ctx.then.task_in_status({"title": "Fix bug", "status": "backlog"})
```

## CLI

```bash
aver run                    # run all tests
aver run --adapter unit     # filter by adapter
aver run --domain task-board  # filter by domain
aver approve                # update approval baselines
aver init                   # scaffold a new domain
```

## Docs

[averspec.dev](https://averspec.dev) · [Architecture](https://github.com/AverSpec/aver) · [Example App](examples/task-board/)

## License

MIT
