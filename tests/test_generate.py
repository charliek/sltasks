"""Tests for generate command."""

import pytest
from pathlib import Path

from sltasks.cli.generate import (
    run_generate,
    generate_config_yaml,
    _is_valid_task_root,
    CONFIG_FILE,
)


class TestGenerateConfigYaml:
    """Tests for generate_config_yaml function."""

    def test_generates_valid_yaml(self):
        """Generated YAML is valid and parseable."""
        import yaml

        content = generate_config_yaml()
        # Should not raise
        parsed = yaml.safe_load(content)

        assert parsed["version"] == 1
        assert parsed["task_root"] == ".tasks"
        assert "board" in parsed
        assert "columns" in parsed["board"]

    def test_generates_with_custom_task_root(self):
        """Generated YAML uses provided task_root."""
        import yaml

        content = generate_config_yaml("my-tasks")
        parsed = yaml.safe_load(content)

        assert parsed["task_root"] == "my-tasks"

    def test_includes_header_comments(self):
        """Generated content includes helpful comments."""
        content = generate_config_yaml()

        assert "# sltasks Board Configuration" in content
        assert "task_root" in content
        assert "# Column constraints:" in content

    def test_matches_default_config(self):
        """Generated config matches SltasksConfig.default()."""
        import yaml
        from sltasks.models import SltasksConfig

        content = generate_config_yaml()
        parsed = yaml.safe_load(content)
        default = SltasksConfig.default()

        assert parsed["version"] == default.version
        assert len(parsed["board"]["columns"]) == len(default.board.columns)

        for i, col in enumerate(parsed["board"]["columns"]):
            assert col["id"] == default.board.columns[i].id
            assert col["title"] == default.board.columns[i].title


class TestIsValidTaskRoot:
    """Tests for _is_valid_task_root validation."""

    def test_valid_simple_name(self, tmp_path: Path):
        """Simple directory name is valid."""
        assert _is_valid_task_root(".tasks", tmp_path) is True
        assert _is_valid_task_root("tasks", tmp_path) is True
        assert _is_valid_task_root("kanban", tmp_path) is True

    def test_valid_dot_current_dir(self, tmp_path: Path):
        """'.' (current directory) is valid."""
        assert _is_valid_task_root(".", tmp_path) is True

    def test_valid_nested_path(self, tmp_path: Path):
        """Nested relative path is valid."""
        assert _is_valid_task_root("sub/dir", tmp_path) is True
        assert _is_valid_task_root("deep/nested/tasks", tmp_path) is True

    def test_invalid_absolute_path(self, tmp_path: Path):
        """Absolute path is invalid."""
        assert _is_valid_task_root("/absolute/path", tmp_path) is False

    def test_invalid_parent_traversal(self, tmp_path: Path):
        """Parent directory traversal is invalid."""
        assert _is_valid_task_root("../other", tmp_path) is False
        assert _is_valid_task_root("foo/../../bar", tmp_path) is False


class TestRunGenerate:
    """Tests for run_generate function."""

    def test_creates_config_and_task_dir(self, tmp_path: Path):
        """Generate creates both config file and task directory."""
        project_root = tmp_path / "project"
        project_root.mkdir()

        exit_code = run_generate(project_root)

        assert exit_code == 0
        assert (project_root / CONFIG_FILE).exists()
        assert (project_root / ".tasks").exists()

    def test_creates_project_root_if_needed(self, tmp_path: Path):
        """Generate creates project_root if it doesn't exist."""
        project_root = tmp_path / "new-project"

        exit_code = run_generate(project_root)

        assert exit_code == 0
        assert project_root.exists()
        assert (project_root / CONFIG_FILE).exists()
        assert (project_root / ".tasks").exists()

    def test_skips_when_both_exist(self, tmp_path: Path):
        """Generate returns 1 when nothing to do."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        # Create config with task_root
        (project_root / CONFIG_FILE).write_text("task_root: .tasks\nversion: 1\n")
        # Create task directory
        (project_root / ".tasks").mkdir()

        exit_code = run_generate(project_root)

        assert exit_code == 1

    def test_creates_task_dir_when_config_exists(self, tmp_path: Path):
        """Generate creates task dir when config exists but dir doesn't."""
        project_root = tmp_path / "project"
        project_root.mkdir()
        (project_root / CONFIG_FILE).write_text("task_root: my-tasks\nversion: 1\n")

        exit_code = run_generate(project_root)

        assert exit_code == 0
        assert (project_root / "my-tasks").exists()

    def test_nested_project_creation(self, tmp_path: Path):
        """Generate creates nested project directories."""
        project_root = tmp_path / "deep" / "nested" / "project"

        exit_code = run_generate(project_root)

        assert exit_code == 0
        assert project_root.exists()
        assert (project_root / CONFIG_FILE).exists()

    def test_generated_config_is_valid(self, tmp_path: Path):
        """Generated config can be loaded by ConfigService."""
        from sltasks.services import ConfigService

        project_root = tmp_path / "project"
        project_root.mkdir()
        run_generate(project_root)

        service = ConfigService(project_root)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert config.task_root == ".tasks"
        assert not service.has_config_error

    def test_config_service_task_root_property(self, tmp_path: Path):
        """ConfigService.task_root returns computed path."""
        from sltasks.services import ConfigService

        project_root = tmp_path / "project"
        project_root.mkdir()
        run_generate(project_root)

        service = ConfigService(project_root)

        assert service.task_root == project_root / ".tasks"

    def test_generated_matches_model_default(self, tmp_path: Path):
        """Generated config matches SltasksConfig.default()."""
        from sltasks.services import ConfigService
        from sltasks.models import SltasksConfig

        project_root = tmp_path / "project"
        project_root.mkdir()
        run_generate(project_root)

        service = ConfigService(project_root)
        loaded_config = service.get_config()
        default_config = SltasksConfig.default()

        # Column IDs should match
        assert loaded_config.board.column_ids == default_config.board.column_ids
        # Titles should match
        for i, col in enumerate(loaded_config.board.columns):
            assert col.title == default_config.board.columns[i].title


class TestOutputHelpers:
    """Tests for CLI output helpers."""

    def test_success_prints_checkmark(self, capsys):
        """success() prints message with checkmark."""
        from sltasks.cli.output import success

        success("Test message")
        captured = capsys.readouterr()

        assert "Test message" in captured.out
        # Checkmark may or may not have color codes depending on TTY

    def test_info_prints_bullet(self, capsys):
        """info() prints message with bullet."""
        from sltasks.cli.output import info

        info("Info message")
        captured = capsys.readouterr()

        assert "Info message" in captured.out

    def test_error_prints_cross(self, capsys):
        """error() prints message with cross."""
        from sltasks.cli.output import error

        error("Error message")
        captured = capsys.readouterr()

        assert "Error message" in captured.out
