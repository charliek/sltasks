"""Tests for sltasks_config models."""

import pytest
from pydantic import ValidationError

from sltasks.models import BoardConfig, ColumnConfig, SltasksConfig


class TestColumnConfig:
    """Tests for ColumnConfig model."""

    def test_valid_simple_id(self):
        """Simple lowercase ID is valid."""
        col = ColumnConfig(id="todo", title="To Do")
        assert col.id == "todo"
        assert col.title == "To Do"

    def test_valid_id_with_underscore(self):
        """ID with underscore is valid."""
        col = ColumnConfig(id="in_progress", title="In Progress")
        assert col.id == "in_progress"

    def test_valid_id_with_numbers(self):
        """ID with numbers (not at start) is valid."""
        col = ColumnConfig(id="stage2", title="Stage 2")
        assert col.id == "stage2"

    def test_invalid_id_uppercase(self):
        """Uppercase ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ColumnConfig(id="ToDo", title="To Do")
        assert "lowercase" in str(exc_info.value).lower()

    def test_invalid_id_starts_with_number(self):
        """ID starting with number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ColumnConfig(id="1st_column", title="First")
        assert "letter" in str(exc_info.value).lower()

    def test_invalid_id_with_hyphen(self):
        """ID with hyphen is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ColumnConfig(id="in-progress", title="In Progress")
        assert "alphanumeric" in str(exc_info.value).lower()

    def test_invalid_id_with_space(self):
        """ID with space is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ColumnConfig(id="to do", title="To Do")
        assert "alphanumeric" in str(exc_info.value).lower()

    def test_empty_id_rejected(self):
        """Empty ID is rejected."""
        with pytest.raises(ValidationError):
            ColumnConfig(id="", title="Empty")

    def test_empty_title_rejected(self):
        """Empty title is rejected."""
        with pytest.raises(ValidationError):
            ColumnConfig(id="todo", title="")


class TestBoardConfig:
    """Tests for BoardConfig model."""

    def test_default_has_three_columns(self):
        """Default config has 3 columns."""
        config = BoardConfig.default()
        assert len(config.columns) == 3
        assert config.column_ids == ["todo", "in_progress", "done"]

    def test_default_column_titles(self):
        """Default columns have expected titles."""
        config = BoardConfig.default()
        assert config.get_title("todo") == "To Do"
        assert config.get_title("in_progress") == "In Progress"
        assert config.get_title("done") == "Done"

    def test_min_columns_two(self):
        """Two columns is valid (minimum)."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="todo", title="To Do"),
                ColumnConfig(id="done", title="Done"),
            ]
        )
        assert len(config.columns) == 2

    def test_min_columns_one_fails(self):
        """Single column fails validation."""
        with pytest.raises(ValidationError):
            BoardConfig(columns=[ColumnConfig(id="only", title="Only")])

    def test_max_columns_six(self):
        """Six columns is valid (maximum)."""
        cols = [ColumnConfig(id=f"col{i}", title=f"Col {i}") for i in range(6)]
        config = BoardConfig(columns=cols)
        assert len(config.columns) == 6

    def test_max_columns_seven_fails(self):
        """Seven columns fails validation."""
        cols = [ColumnConfig(id=f"col{i}", title=f"Col {i}") for i in range(7)]
        with pytest.raises(ValidationError):
            BoardConfig(columns=cols)

    def test_unique_ids_required(self):
        """Duplicate IDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BoardConfig(
                columns=[
                    ColumnConfig(id="same", title="First"),
                    ColumnConfig(id="same", title="Second"),
                    ColumnConfig(id="done", title="Done"),
                ]
            )
        assert "unique" in str(exc_info.value).lower()

    def test_archived_reserved(self):
        """'archived' as column ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BoardConfig(
                columns=[
                    ColumnConfig(id="todo", title="To Do"),
                    ColumnConfig(id="archived", title="Archive"),
                    ColumnConfig(id="done", title="Done"),
                ]
            )
        assert "archived" in str(exc_info.value).lower()
        assert "reserved" in str(exc_info.value).lower()

    def test_get_title_known_column(self):
        """get_title returns correct title for known column."""
        config = BoardConfig.default()
        assert config.get_title("in_progress") == "In Progress"

    def test_get_title_unknown_column(self):
        """get_title returns formatted ID for unknown column."""
        config = BoardConfig.default()
        assert config.get_title("unknown_column") == "Unknown Column"

    def test_is_valid_status_column_id(self):
        """is_valid_status returns True for configured column."""
        config = BoardConfig.default()
        assert config.is_valid_status("todo") is True
        assert config.is_valid_status("in_progress") is True
        assert config.is_valid_status("done") is True

    def test_is_valid_status_archived(self):
        """is_valid_status returns True for 'archived' (always valid)."""
        config = BoardConfig.default()
        assert config.is_valid_status("archived") is True

    def test_is_valid_status_unknown(self):
        """is_valid_status returns False for unknown status."""
        config = BoardConfig.default()
        assert config.is_valid_status("unknown") is False
        assert config.is_valid_status("review") is False

    def test_column_ids_property(self):
        """column_ids returns IDs in order."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="backlog", title="Backlog"),
                ColumnConfig(id="active", title="Active"),
                ColumnConfig(id="done", title="Done"),
            ]
        )
        assert config.column_ids == ["backlog", "active", "done"]


class TestSltasksConfig:
    """Tests for SltasksConfig model."""

    def test_default(self):
        """Default config has version 1 and 3 columns."""
        config = SltasksConfig.default()
        assert config.version == 1
        assert len(config.board.columns) == 3

    def test_default_board_config(self):
        """Default board config is accessible."""
        config = SltasksConfig.default()
        assert config.board.column_ids == ["todo", "in_progress", "done"]

    def test_custom_version(self):
        """Custom version is accepted."""
        config = SltasksConfig(version=2, board=BoardConfig.default())
        assert config.version == 2

    def test_custom_board(self):
        """Custom board config is accepted."""
        board = BoardConfig(
            columns=[
                ColumnConfig(id="a", title="A"),
                ColumnConfig(id="b", title="B"),
            ]
        )
        config = SltasksConfig(board=board)
        assert config.board.column_ids == ["a", "b"]

    def test_from_dict(self):
        """Config can be created from dict (as from YAML)."""
        data = {
            "version": 1,
            "board": {
                "columns": [
                    {"id": "backlog", "title": "Backlog"},
                    {"id": "done", "title": "Done"},
                ]
            },
        }
        config = SltasksConfig(**data)
        assert config.version == 1
        assert config.board.column_ids == ["backlog", "done"]

    def test_from_dict_minimal(self):
        """Config with minimal data uses defaults."""
        data = {"version": 1}
        config = SltasksConfig(**data)
        assert len(config.board.columns) == 3  # Default

    def test_default_task_root(self):
        """Default config has task_root of '.tasks'."""
        config = SltasksConfig.default()
        assert config.task_root == ".tasks"

    def test_custom_task_root(self):
        """Custom task_root is accepted."""
        config = SltasksConfig(task_root="my-tasks")
        assert config.task_root == "my-tasks"

    def test_task_root_dot_valid(self):
        """task_root '.' is valid (same directory)."""
        config = SltasksConfig(task_root=".")
        assert config.task_root == "."

    def test_task_root_nested_valid(self):
        """Nested relative task_root is valid."""
        config = SltasksConfig(task_root="sub/dir/tasks")
        assert config.task_root == "sub/dir/tasks"

    def test_task_root_absolute_invalid(self):
        """Absolute path for task_root is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SltasksConfig(task_root="/absolute/path")
        assert "relative" in str(exc_info.value).lower()

    def test_task_root_parent_traversal_invalid(self):
        """task_root with parent traversal is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            SltasksConfig(task_root="../other")
        assert "within" in str(exc_info.value).lower()
