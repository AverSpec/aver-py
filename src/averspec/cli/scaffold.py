"""File generation helpers for aver init."""

from __future__ import annotations

import os
from pathlib import Path


def _domain_template(class_name: str, domain_label: str) -> str:
    return f'''from averspec import domain, action, query, assertion


@domain("{domain_label}")
class {class_name}:
    create = action()
    get_count = query(type(None), int)
    exists = assertion()
'''


def _adapter_template(
    class_name: str,
    snake_name: str,
    protocol: str,
) -> str:
    domain_import = f"from domains.{snake_name} import {class_name}"

    if protocol == "unit":
        return f'''{domain_import}
from averspec import implement, unit


adapter = implement({class_name}, protocol=unit(lambda: None))


@adapter.handle({class_name}.create)
def handle_create(ctx):
    pass


@adapter.handle({class_name}.get_count)
def handle_get_count(ctx):
    return 0


@adapter.handle({class_name}.exists)
def handle_exists(ctx):
    pass
'''

    elif protocol == "http":
        return f'''{domain_import}
from averspec import implement, Protocol


class HttpProtocol(Protocol):
    name = "http"

    def setup(self):
        # Return your HTTP client / base URL here
        return {{"base_url": "http://localhost:8000"}}

    def teardown(self, ctx):
        pass


adapter = implement({class_name}, protocol=HttpProtocol())


@adapter.handle({class_name}.create)
def handle_create(ctx):
    pass


@adapter.handle({class_name}.get_count)
def handle_get_count(ctx):
    return 0


@adapter.handle({class_name}.exists)
def handle_exists(ctx):
    pass
'''

    else:  # playwright
        return f'''{domain_import}
from averspec import implement, Protocol


class PlaywrightProtocol(Protocol):
    name = "playwright"

    def setup(self):
        # Return your page / browser context here
        return None

    def teardown(self, ctx):
        pass


adapter = implement({class_name}, protocol=PlaywrightProtocol())


@adapter.handle({class_name}.create)
def handle_create(ctx):
    pass


@adapter.handle({class_name}.get_count)
def handle_get_count(ctx):
    return 0


@adapter.handle({class_name}.exists)
def handle_exists(ctx):
    pass
'''


def _test_template(class_name: str, snake_name: str) -> str:
    return f'''from averspec import suite
from domains.{snake_name} import {class_name}

s = suite({class_name})


@s.test
def test_can_create(ctx):
    ctx.when.create()
    ctx.then.exists()
'''


def _conftest_entry(snake_name: str, protocol: str) -> str:
    return f"""from averspec import define_config
from adapters.{snake_name}_{protocol} import adapter

define_config(adapters=[adapter])
"""


def scaffold_domain(
    *,
    snake_name: str,
    class_name: str,
    domain_label: str,
    protocol: str,
    base_dir: str | Path | None = None,
) -> list[str]:
    """Generate domain, adapter, test, and conftest files.

    Returns list of created file paths (relative to base_dir).
    """
    base = Path(base_dir) if base_dir else Path.cwd()
    created: list[str] = []

    files: dict[Path, str] = {
        base / "domains" / f"{snake_name}.py": _domain_template(class_name, domain_label),
        base / "adapters" / f"{snake_name}_{protocol}.py": _adapter_template(
            class_name, snake_name, protocol,
        ),
        base / "tests" / f"test_{snake_name}.py": _test_template(class_name, snake_name),
    }

    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        created.append(str(path.relative_to(base)))

    # conftest.py: create if missing, append if exists
    conftest_path = base / "conftest.py"
    entry = _conftest_entry(snake_name, protocol)

    if conftest_path.exists():
        existing = conftest_path.read_text()
        # Don't duplicate if already imported
        adapter_import = f"from adapters.{snake_name}_{protocol} import adapter"
        if adapter_import not in existing:
            # Append the adapter to an existing define_config call or add new block
            with open(conftest_path, "a") as f:
                f.write("\n" + entry)
            created.append("conftest.py (appended)")
    else:
        conftest_path.write_text(entry)
        created.append("conftest.py")

    return created
