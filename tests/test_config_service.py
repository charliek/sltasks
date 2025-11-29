"""Tests for ConfigService."""

import pytest
from pathlib import Path

from kosmos.services import ConfigService


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    """Create a temporary task directory."""
    task_root = tmp_path / ".tasks"
    task_root.mkdir()
    return task_root


class TestConfigServiceLoading:
    """Tests for ConfigService file loading."""

    def test_default_on_missing_file(self, task_dir: Path):
        """Missing sltasks.yml returns default config."""
        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert config.board.column_ids == ["todo", "in_progress", "done"]
        assert not service.has_config_error

    def test_load_valid_two_column_config(self, task_dir: Path):
        """Valid 2-column config loads correctly."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: done
      title: "Done"
"""
        )

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 2
        assert config.board.column_ids == ["backlog", "done"]
        assert not service.has_config_error

    def test_load_valid_five_column_config(self, task_dir: Path):
        """Valid 5-column config loads correctly."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
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

        service = ConfigService(task_dir)
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

    def test_get_board_config_convenience(self, task_dir: Path):
        """get_board_config returns board config directly."""
        service = ConfigService(task_dir)
        board_config = service.get_board_config()

        assert board_config.column_ids == ["todo", "in_progress", "done"]


class TestConfigServiceFallback:
    """Tests for ConfigService fallback behavior."""

    def test_fallback_on_empty_file(self, task_dir: Path):
        """Empty file falls back to defaults."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text("")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error
        assert "empty" in service.config_error.lower()

    def test_fallback_on_invalid_yaml(self, task_dir: Path):
        """Invalid YAML falls back to defaults."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text("invalid: yaml: syntax: :")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error
        assert "yaml" in service.config_error.lower()

    def test_fallback_on_validation_error_too_few_columns(self, task_dir: Path):
        """Too few columns falls back to defaults."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
board:
  columns:
    - id: only
      title: "Only Column"
"""
        )

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_fallback_on_validation_error_too_many_columns(self, task_dir: Path):
        """Too many columns falls back to defaults."""
        columns_yaml = "\n".join(
            [f"    - id: col{i}\n      title: 'Column {i}'" for i in range(7)]
        )
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            f"""
version: 1
board:
  columns:
{columns_yaml}
"""
        )

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_fallback_on_duplicate_ids(self, task_dir: Path):
        """Duplicate IDs falls back to defaults."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
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

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_fallback_on_archived_column_id(self, task_dir: Path):
        """'archived' as column ID falls back to defaults."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
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

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert "archived" not in config.board.column_ids
        assert service.has_config_error


class TestConfigServiceCaching:
    """Tests for ConfigService caching behavior."""

    def test_config_is_cached(self, task_dir: Path):
        """Config is cached between calls."""
        service = ConfigService(task_dir)

        config1 = service.get_config()
        config2 = service.get_config()

        assert config1 is config2

    def test_reload_clears_cache(self, task_dir: Path):
        """reload() clears cached config."""
        service = ConfigService(task_dir)

        config1 = service.get_config()
        service.reload()
        config2 = service.get_config()

        assert config1 is not config2

    def test_reload_picks_up_new_config(self, task_dir: Path):
        """reload() picks up changes to config file."""
        service = ConfigService(task_dir)

        # First load - defaults
        config1 = service.get_config()
        assert len(config1.board.columns) == 3

        # Create config file
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
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

    def test_reload_clears_error(self, task_dir: Path):
        """reload() clears previous error state."""
        # Create invalid config (only one column - validation error)
        config_file = task_dir / "sltasks.yml"
        config_file.write_text(
            """
version: 1
board:
  columns:
    - id: only
      title: "Only"
"""
        )

        service = ConfigService(task_dir)
        service.get_config()
        assert service.has_config_error

        # Fix config
        config_file.write_text(
            """
version: 1
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

    def test_config_file_is_directory(self, task_dir: Path):
        """Config path being a directory falls back to defaults."""
        config_path = task_dir / "sltasks.yml"
        config_path.mkdir()  # Create as directory instead of file

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_whitespace_only_file(self, task_dir: Path):
        """Whitespace-only file falls back to defaults."""
        config_file = task_dir / "sltasks.yml"
        config_file.write_text("   \n\n   \n")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error
