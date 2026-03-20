"""Tests for aver init — scaffold file generation."""

from pathlib import Path

from averspec.cli.init_cmd import _to_snake_case, _to_class_name
from averspec.cli.scaffold import scaffold_domain


class TestNameConversion:
    def test_simple_name(self):
        assert _to_snake_case("task board") == "task_board"

    def test_hyphenated(self):
        assert _to_snake_case("task-board") == "task_board"

    def test_camel_case(self):
        assert _to_snake_case("TaskBoard") == "task_board"

    def test_already_snake(self):
        assert _to_snake_case("task_board") == "task_board"

    def test_mixed(self):
        assert _to_snake_case("My API Client") == "my_api_client"

    def test_class_name_from_snake(self):
        assert _to_class_name("task_board") == "TaskBoard"

    def test_class_name_single_word(self):
        assert _to_class_name("checkout") == "Checkout"


class TestScaffoldDomain:
    def test_creates_domain_file(self, tmp_path):
        scaffold_domain(
            snake_name="task_board",
            class_name="TaskBoard",
            domain_label="Task Board",
            protocol="unit",
            base_dir=tmp_path,
        )

        domain_file = tmp_path / "domains" / "task_board.py"
        assert domain_file.exists()
        content = domain_file.read_text()
        assert '@domain("Task Board")' in content
        assert "class TaskBoard:" in content
        assert "create = action()" in content
        assert "get_count = query(type(None), int)" in content
        assert "exists = assertion()" in content

    def test_creates_adapter_file_unit(self, tmp_path):
        scaffold_domain(
            snake_name="task_board",
            class_name="TaskBoard",
            domain_label="Task Board",
            protocol="unit",
            base_dir=tmp_path,
        )

        adapter_file = tmp_path / "adapters" / "task_board_unit.py"
        assert adapter_file.exists()
        content = adapter_file.read_text()
        assert "from domains.task_board import TaskBoard" in content
        assert "implement(TaskBoard, protocol=unit(lambda: None))" in content
        assert "@adapter.handle(TaskBoard.create)" in content

    def test_creates_adapter_file_http(self, tmp_path):
        scaffold_domain(
            snake_name="checkout",
            class_name="Checkout",
            domain_label="Checkout",
            protocol="http",
            base_dir=tmp_path,
        )

        adapter_file = tmp_path / "adapters" / "checkout_http.py"
        assert adapter_file.exists()
        content = adapter_file.read_text()
        assert "class HttpProtocol(Protocol):" in content
        assert "from domains.checkout import Checkout" in content

    def test_creates_adapter_file_playwright(self, tmp_path):
        scaffold_domain(
            snake_name="checkout",
            class_name="Checkout",
            domain_label="Checkout",
            protocol="playwright",
            base_dir=tmp_path,
        )

        adapter_file = tmp_path / "adapters" / "checkout_playwright.py"
        assert adapter_file.exists()
        content = adapter_file.read_text()
        assert "class PlaywrightProtocol(Protocol):" in content

    def test_creates_test_file(self, tmp_path):
        scaffold_domain(
            snake_name="task_board",
            class_name="TaskBoard",
            domain_label="Task Board",
            protocol="unit",
            base_dir=tmp_path,
        )

        test_file = tmp_path / "tests" / "test_task_board.py"
        assert test_file.exists()
        content = test_file.read_text()
        assert "s = suite(TaskBoard)" in content
        assert "@s.test" in content
        assert "def test_can_create(ctx):" in content
        assert "ctx.when.create()" in content
        assert "ctx.then.exists()" in content

    def test_creates_conftest(self, tmp_path):
        scaffold_domain(
            snake_name="task_board",
            class_name="TaskBoard",
            domain_label="Task Board",
            protocol="unit",
            base_dir=tmp_path,
        )

        conftest = tmp_path / "conftest.py"
        assert conftest.exists()
        content = conftest.read_text()
        assert "define_config(adapters=[adapter])" in content
        assert "from adapters.task_board_unit import adapter" in content

    def test_appends_to_existing_conftest(self, tmp_path):
        conftest = tmp_path / "conftest.py"
        conftest.write_text("# existing config\n")

        scaffold_domain(
            snake_name="checkout",
            class_name="Checkout",
            domain_label="Checkout",
            protocol="http",
            base_dir=tmp_path,
        )

        content = conftest.read_text()
        assert "# existing config" in content
        assert "from adapters.checkout_http import adapter" in content

    def test_does_not_duplicate_conftest_import(self, tmp_path):
        conftest = tmp_path / "conftest.py"
        conftest.write_text("from adapters.task_board_unit import adapter\n")

        scaffold_domain(
            snake_name="task_board",
            class_name="TaskBoard",
            domain_label="Task Board",
            protocol="unit",
            base_dir=tmp_path,
        )

        content = conftest.read_text()
        # Should appear exactly once
        assert content.count("from adapters.task_board_unit import adapter") == 1

    def test_returns_created_paths(self, tmp_path):
        result = scaffold_domain(
            snake_name="task_board",
            class_name="TaskBoard",
            domain_label="Task Board",
            protocol="unit",
            base_dir=tmp_path,
        )

        assert "domains/task_board.py" in result
        assert "adapters/task_board_unit.py" in result
        assert "tests/test_task_board.py" in result
        assert "conftest.py" in result

    def test_creates_directories(self, tmp_path):
        scaffold_domain(
            snake_name="task_board",
            class_name="TaskBoard",
            domain_label="Task Board",
            protocol="unit",
            base_dir=tmp_path,
        )

        assert (tmp_path / "domains").is_dir()
        assert (tmp_path / "adapters").is_dir()
        assert (tmp_path / "tests").is_dir()
