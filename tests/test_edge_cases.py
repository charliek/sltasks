"""Edge case tests for Phase 6 - config errors and unknown states."""

import pytest
from pathlib import Path

from sltasks.models import Board, BoardConfig, ColumnConfig, Task
from sltasks.models.task import STATE_ARCHIVED
from sltasks.repositories import FilesystemRepository
from sltasks.services import ConfigService, FilterService, TaskService, BoardService


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    """Create a temporary task directory."""
    task_root = tmp_path / ".tasks"
    task_root.mkdir()
    return task_root


class TestInvalidConfig:
    """Test handling of invalid sltasks.yml files."""

    def test_empty_yaml_file(self, task_dir: Path):
        """Empty file uses defaults."""
        (task_dir / "sltasks.yml").write_text("")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error
        assert "empty" in service.config_error.lower()

    def test_invalid_yaml_syntax(self, task_dir: Path):
        """Syntax errors fall back to defaults."""
        (task_dir / "sltasks.yml").write_text("invalid: yaml: syntax:")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_missing_columns_uses_defaults(self, task_dir: Path):
        """Missing columns key uses defaults via Pydantic."""
        (task_dir / "sltasks.yml").write_text("version: 1\n")

        service = ConfigService(task_dir)
        config = service.get_config()

        # Pydantic uses defaults when board is missing
        assert len(config.board.columns) == 3

    def test_too_few_columns(self, task_dir: Path):
        """Single column fails validation."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: only
      title: "Only Column"
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3  # Default
        assert service.has_config_error

    def test_too_many_columns(self, task_dir: Path):
        """More than 6 columns fails validation."""
        columns = "\n".join([
            f"    - id: col{i}\n      title: 'Column {i}'"
            for i in range(7)
        ])
        (task_dir / "sltasks.yml").write_text(f"""
version: 1
board:
  columns:
{columns}
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3  # Default
        assert service.has_config_error

    def test_duplicate_column_ids(self, task_dir: Path):
        """Duplicate IDs fail validation."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: todo
      title: "Also To Do"
    - id: done
      title: "Done"
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3  # Default
        assert service.has_config_error

    def test_archived_as_column_id(self, task_dir: Path):
        """Using 'archived' as column ID fails."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: archived
      title: "Archive"
    - id: done
      title: "Done"
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert "archived" not in [c.id for c in config.board.columns]
        assert service.has_config_error


class TestUnknownStates:
    """Test handling of tasks with unknown states."""

    def test_unknown_state_in_first_column(self):
        """Tasks with unknown states go to first column."""
        config = BoardConfig.default()
        tasks = [
            Task(filename="task.md", state="weird_state"),
        ]

        board = Board.from_tasks(tasks, config)

        assert len(board.get_column("todo")) == 1
        assert board.get_column("todo")[0].state == "weird_state"

    def test_multiple_unknown_states(self):
        """Multiple unknown states all go to first column."""
        config = BoardConfig.default()
        tasks = [
            Task(filename="task1.md", state="weird"),
            Task(filename="task2.md", state="strange"),
            Task(filename="task3.md", state="todo"),
        ]

        board = Board.from_tasks(tasks, config)

        # 2 unknown + 1 todo = 3 in first column
        assert len(board.get_column("todo")) == 3

    def test_archived_always_works(self, task_dir: Path):
        """Archived state always valid even with custom config."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: done
      title: "Done"
""")
        (task_dir / "task.md").write_text("---\nstate: archived\n---\n")

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        tasks = repo.get_all()

        config = config_service.get_board_config()
        board = Board.from_tasks(tasks, config)

        assert len(board.get_column(STATE_ARCHIVED)) == 1
        assert len(board.get_column("backlog")) == 0


class TestConfigReload:
    """Test config reload behavior."""

    def test_reload_clears_cache(self, task_dir: Path):
        """Reload clears cached config."""
        service = ConfigService(task_dir)

        config1 = service.get_config()
        assert len(config1.board.columns) == 3

        # Add custom config
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: a
      title: "A"
    - id: b
      title: "B"
""")

        # Still cached
        config2 = service.get_config()
        assert config1 is config2

        # After reload
        service.reload()
        config3 = service.get_config()
        assert len(config3.board.columns) == 2


class TestFullWorkflow:
    """Integration tests for complete workflows."""

    def test_create_move_archive_workflow(self, task_dir: Path):
        """Test creating, moving, and archiving a task."""
        # Setup custom config
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: active
      title: "Active"
    - id: done
      title: "Done"
""")

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        task_service = TaskService(repo, config_service)
        board_service = BoardService(repo, config_service)

        # Create task - should be in first column
        task = task_service.create_task("Test Task")
        assert task.state == "backlog"

        # Move right
        task = board_service.move_task_right(task.filename)
        assert task.state == "active"

        # Move right again
        task = board_service.move_task_right(task.filename)
        assert task.state == "done"

        # Can't move right anymore (at last column) - returns task unchanged
        result = board_service.move_task_right(task.filename)
        assert result.state == "done"  # Still at done

        # Archive
        task = board_service.archive_task(task.filename)
        assert task.state == "archived"

        # Unarchive goes to first column
        task = board_service.unarchive_task(task.filename)
        assert task.state == "backlog"

    def test_filter_custom_states(self, task_dir: Path):
        """Test filtering by custom state names."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: idea
      title: "Ideas"
    - id: planned
      title: "Planned"
    - id: shipped
      title: "Shipped"
""")
        (task_dir / "task1.md").write_text("---\nstate: idea\n---\n")
        (task_dir / "task2.md").write_text("---\nstate: planned\n---\n")
        (task_dir / "task3.md").write_text("---\nstate: shipped\n---\n")

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        filter_service = FilterService()

        tasks = repo.get_all()
        filter_obj = filter_service.parse("state:planned")
        filtered = filter_service.apply(tasks, filter_obj)

        assert len(filtered) == 1
        assert filtered[0].state == "planned"
