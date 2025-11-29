"""Tests for generate command."""

import pytest
from pathlib import Path

from kosmos.cli.generate import run_generate, generate_config_yaml, CONFIG_FILE


class TestGenerateConfigYaml:
    """Tests for generate_config_yaml function."""

    def test_generates_valid_yaml(self):
        """Generated YAML is valid and parseable."""
        import yaml

        content = generate_config_yaml()
        # Should not raise
        parsed = yaml.safe_load(content)

        assert parsed["version"] == 1
        assert "board" in parsed
        assert "columns" in parsed["board"]

    def test_includes_header_comments(self):
        """Generated content includes helpful comments."""
        content = generate_config_yaml()

        assert "# Kosmos Board Configuration" in content
        assert "# Column constraints:" in content
        assert "# Example custom columns:" in content

    def test_matches_default_config(self):
        """Generated config matches SltasksConfig.default()."""
        import yaml
        from kosmos.models import SltasksConfig

        content = generate_config_yaml()
        parsed = yaml.safe_load(content)
        default = SltasksConfig.default()

        assert parsed["version"] == default.version
        assert len(parsed["board"]["columns"]) == len(default.board.columns)

        for i, col in enumerate(parsed["board"]["columns"]):
            assert col["id"] == default.board.columns[i].id
            assert col["title"] == default.board.columns[i].title


class TestRunGenerate:
    """Tests for run_generate function."""

    def test_creates_directory_and_file(self, tmp_path: Path):
        """Generate creates both directory and config."""
        task_root = tmp_path / ".tasks"

        exit_code = run_generate(task_root)

        assert exit_code == 0
        assert task_root.exists()
        assert (task_root / CONFIG_FILE).exists()

    def test_creates_file_in_existing_directory(self, tmp_path: Path):
        """Generate creates file when directory exists."""
        task_root = tmp_path / ".tasks"
        task_root.mkdir()

        exit_code = run_generate(task_root)

        assert exit_code == 0
        assert (task_root / CONFIG_FILE).exists()

    def test_skips_when_both_exist(self, tmp_path: Path):
        """Generate returns 1 when nothing to do."""
        task_root = tmp_path / ".tasks"
        task_root.mkdir()
        (task_root / CONFIG_FILE).write_text("existing")

        exit_code = run_generate(task_root)

        assert exit_code == 1
        # Should not overwrite
        assert (task_root / CONFIG_FILE).read_text() == "existing"

    def test_creates_file_when_only_dir_exists(self, tmp_path: Path):
        """Generate creates file and returns 0 when dir exists but file doesn't."""
        task_root = tmp_path / ".tasks"
        task_root.mkdir()

        exit_code = run_generate(task_root)

        assert exit_code == 0
        assert (task_root / CONFIG_FILE).exists()

    def test_nested_directory_creation(self, tmp_path: Path):
        """Generate creates nested directories."""
        task_root = tmp_path / "deep" / "nested" / ".tasks"

        exit_code = run_generate(task_root)

        assert exit_code == 0
        assert task_root.exists()
        assert (task_root / CONFIG_FILE).exists()

    def test_custom_task_root_path(self, tmp_path: Path):
        """Generate honors custom --task-root path."""
        custom_root = tmp_path / "my-project" / "tasks"

        exit_code = run_generate(custom_root)

        assert exit_code == 0
        assert custom_root.exists()
        assert (custom_root / CONFIG_FILE).exists()

    def test_generated_config_is_valid(self, tmp_path: Path):
        """Generated config can be loaded by ConfigService."""
        from kosmos.services import ConfigService

        task_root = tmp_path / ".tasks"
        run_generate(task_root)

        service = ConfigService(task_root)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert not service.has_config_error

    def test_generated_matches_model_default(self, tmp_path: Path):
        """Generated config matches SltasksConfig.default()."""
        from kosmos.services import ConfigService
        from kosmos.models import SltasksConfig

        task_root = tmp_path / ".tasks"
        run_generate(task_root)

        service = ConfigService(task_root)
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
        from kosmos.cli.output import success

        success("Test message")
        captured = capsys.readouterr()

        assert "Test message" in captured.out
        # Checkmark may or may not have color codes depending on TTY

    def test_info_prints_bullet(self, capsys):
        """info() prints message with bullet."""
        from kosmos.cli.output import info

        info("Info message")
        captured = capsys.readouterr()

        assert "Info message" in captured.out
