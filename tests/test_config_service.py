"""Tests for ConfigService."""

from pathlib import Path

import pytest

from sltasks.services import ConfigService


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    return project_root


class TestConfigServiceLoading:
    """Tests for ConfigService file loading."""

    def test_default_on_missing_file(self, project_dir: Path):
        """Missing sltasks.yml returns default config."""
        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert config.board.column_ids == ["todo", "in_progress", "done"]
        assert config.task_root == ".tasks"
        assert not service.has_config_error

    def test_task_root_property(self, project_dir: Path):
        """task_root property returns computed path."""
        service = ConfigService(project_dir)

        assert service.task_root == project_dir / ".tasks"

    def test_task_root_with_custom_value(self, project_dir: Path):
        """task_root property uses config value."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: my-custom-tasks
board:
  columns:
    - id: todo
      title: "To Do"
    - id: done
      title: "Done"
"""
        )

        service = ConfigService(project_dir)

        assert service.task_root == project_dir / "my-custom-tasks"

    def test_task_root_with_dot(self, project_dir: Path):
        """task_root '.' means same as project_root."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: "."
board:
  columns:
    - id: todo
      title: "To Do"
    - id: done
      title: "Done"
"""
        )

        service = ConfigService(project_dir)

        assert service.task_root == project_dir / "."
        assert service.task_root.resolve() == project_dir.resolve()

    def test_load_valid_two_column_config(self, project_dir: Path):
        """Valid 2-column config loads correctly."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: done
      title: "Done"
"""
        )

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 2
        assert config.board.column_ids == ["backlog", "done"]
        assert not service.has_config_error

    def test_load_valid_five_column_config(self, project_dir: Path):
        """Valid 5-column config loads correctly."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: todo
      title: "To Do"
    - id: in_progress
      title: "In Progress"
    - id: review
      title: "Review"
    - id: done
      title: "Done"
"""
        )

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 5
        assert config.board.column_ids == [
            "backlog",
            "todo",
            "in_progress",
            "review",
            "done",
        ]
        assert not service.has_config_error

    def test_get_board_config_convenience(self, project_dir: Path):
        """get_board_config returns board config directly."""
        service = ConfigService(project_dir)
        board_config = service.get_board_config()

        assert board_config.column_ids == ["todo", "in_progress", "done"]

    def test_load_config_with_aliases(self, project_dir: Path):
        """Config with status aliases loads correctly."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: todo
      title: "To Do"
      status_alias:
        - new
        - fresh
    - id: done
      title: "Done"
      status_alias:
        - completed
"""
        )

        service = ConfigService(project_dir)
        config = service.get_config()

        todo = next(c for c in config.board.columns if c.id == "todo")
        done = next(c for c in config.board.columns if c.id == "done")

        assert "new" in todo.status_alias
        assert "fresh" in todo.status_alias
        assert "completed" in done.status_alias
        assert not service.has_config_error


class TestConfigServiceFallback:
    """Tests for ConfigService fallback behavior."""

    def test_fallback_on_empty_file(self, project_dir: Path):
        """Empty file falls back to defaults."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text("")

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error
        assert "empty" in service.config_error.lower()

    def test_fallback_on_invalid_yaml(self, project_dir: Path):
        """Invalid YAML falls back to defaults."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text("invalid: yaml: syntax: :")

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error
        assert "yaml" in service.config_error.lower()

    def test_fallback_on_validation_error_too_few_columns(self, project_dir: Path):
        """Too few columns falls back to defaults."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: only
      title: "Only Column"
"""
        )

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_fallback_on_validation_error_too_many_columns(self, project_dir: Path):
        """Too many columns falls back to defaults."""
        columns_yaml = "\n".join([f"    - id: col{i}\n      title: 'Column {i}'" for i in range(7)])
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            f"""
version: 1
task_root: .tasks
board:
  columns:
{columns_yaml}
"""
        )

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_fallback_on_duplicate_ids(self, project_dir: Path):
        """Duplicate IDs falls back to defaults."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: todo
      title: "To Do"
    - id: todo
      title: "Also To Do"
    - id: done
      title: "Done"
"""
        )

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_fallback_on_archived_column_id(self, project_dir: Path):
        """'archived' as column ID falls back to defaults."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: todo
      title: "To Do"
    - id: archived
      title: "Archive"
    - id: done
      title: "Done"
"""
        )

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert "archived" not in config.board.column_ids
        assert service.has_config_error


class TestConfigServiceCaching:
    """Tests for ConfigService caching behavior."""

    def test_config_is_cached(self, project_dir: Path):
        """Config is cached between calls."""
        service = ConfigService(project_dir)

        config1 = service.get_config()
        config2 = service.get_config()

        assert config1 is config2

    def test_reload_clears_cache(self, project_dir: Path):
        """reload() clears cached config."""
        service = ConfigService(project_dir)

        config1 = service.get_config()
        service.reload()
        config2 = service.get_config()

        assert config1 is not config2

    def test_reload_picks_up_new_config(self, project_dir: Path):
        """reload() picks up changes to config file."""
        service = ConfigService(project_dir)

        # First load - defaults
        config1 = service.get_config()
        assert len(config1.board.columns) == 3

        # Create config file
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: a
      title: "A"
    - id: b
      title: "B"
"""
        )

        # Still cached
        config2 = service.get_config()
        assert len(config2.board.columns) == 3

        # After reload
        service.reload()
        config3 = service.get_config()
        assert len(config3.board.columns) == 2

    def test_reload_clears_error(self, project_dir: Path):
        """reload() clears previous error state."""
        # Create invalid config (only one column - validation error)
        config_file = project_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: only
      title: "Only"
"""
        )

        service = ConfigService(project_dir)
        service.get_config()
        assert service.has_config_error

        # Fix config
        config_file.write_text(
            """
version: 1
task_root: .tasks
board:
  columns:
    - id: todo
      title: "To Do"
    - id: done
      title: "Done"
"""
        )

        # Reload
        service.reload()
        service.get_config()
        assert not service.has_config_error


class TestConfigServiceEdgeCases:
    """Tests for ConfigService edge cases."""

    def test_nonexistent_directory(self, tmp_path: Path):
        """Nonexistent directory returns defaults."""
        nonexistent = tmp_path / "does_not_exist"
        service = ConfigService(nonexistent)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert not service.has_config_error

    def test_config_file_is_directory(self, project_dir: Path):
        """Config path being a directory falls back to defaults."""
        config_path = project_dir / "sltasks.yml"
        config_path.mkdir()  # Create as directory instead of file

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_whitespace_only_file(self, project_dir: Path):
        """Whitespace-only file falls back to defaults."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text("   \n\n   \n")

        service = ConfigService(project_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error


class TestConfigServiceBanner:
    """Tests for ConfigService.get_banner()."""

    def test_get_banner_returns_configured_value(self, project_dir: Path):
        """get_banner returns the configured banner value."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text("version: 1\nbanner: 'My Tasks'\n")

        service = ConfigService(project_dir)

        assert service.get_banner() == "My Tasks"

    def test_get_banner_returns_default_when_not_set(self, project_dir: Path):
        """get_banner returns 'sltasks' when banner not configured."""
        config_file = project_dir / "sltasks.yml"
        config_file.write_text("version: 1\n")

        service = ConfigService(project_dir)

        assert service.get_banner() == "sltasks"

    def test_get_banner_returns_default_for_missing_file(self, project_dir: Path):
        """get_banner returns 'sltasks' when no config file exists."""
        service = ConfigService(project_dir)

        assert service.get_banner() == "sltasks"
