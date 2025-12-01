"""Unit tests for model edge cases."""

import pytest
from datetime import datetime, timezone

from sltasks.models import Task, Priority, Board, BoardOrder
from sltasks.models import BoardConfig, ColumnConfig
from sltasks.models.task import (
    STATE_TODO,
    STATE_IN_PROGRESS,
    STATE_DONE,
    STATE_ARCHIVED,
    _parse_datetime,
)


class TestTaskFromFrontmatter:
    """Tests for Task.from_frontmatter edge cases."""

    def test_from_frontmatter_unknown_state_accepted(self):
        """Unknown state values are accepted (validation happens at config level)."""
        task = Task.from_frontmatter(
            filename="task.md",
            metadata={"state": "custom_state"},
            body="",
        )
        assert task.state == "custom_state"

    def test_from_frontmatter_invalid_priority_uses_default(self):
        """Invalid priority value raises ValueError (Pydantic validation)."""
        with pytest.raises(ValueError):
            Task.from_frontmatter(
                filename="task.md",
                metadata={"priority": "super_high"},
                body="",
            )

    def test_from_frontmatter_missing_state_uses_default(self):
        """Missing state defaults to 'todo'."""
        task = Task.from_frontmatter(
            filename="task.md",
            metadata={},
            body="",
        )
        assert task.state == STATE_TODO

    def test_from_frontmatter_missing_priority_uses_default(self):
        """Missing priority defaults to 'medium'."""
        task = Task.from_frontmatter(
            filename="task.md",
            metadata={},
            body="",
        )
        assert task.priority == Priority.MEDIUM


class TestTaskDisplayTitle:
    """Tests for Task.display_title property."""

    def test_display_title_with_title_set(self):
        """display_title returns title when set."""
        task = Task(filename="task.md", title="My Custom Title")
        assert task.display_title == "My Custom Title"

    def test_display_title_without_title(self):
        """display_title transforms filename when title is None."""
        task = Task(filename="my-task-name.md", title=None)
        assert task.display_title == "My Task Name"

    def test_display_title_complex_filename(self):
        """display_title handles multiple hyphens correctly."""
        task = Task(filename="fix-login-timeout-bug.md", title=None)
        assert task.display_title == "Fix Login Timeout Bug"


class TestParseDatetime:
    """Tests for _parse_datetime helper."""

    def test_parse_datetime_z_suffix(self):
        """ISO datetime with Z suffix parsed as UTC."""
        result = _parse_datetime("2025-01-15T10:30:00Z")

        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.tzinfo is not None

    def test_parse_datetime_explicit_offset(self):
        """ISO datetime with explicit offset parsed correctly."""
        result = _parse_datetime("2025-01-15T10:30:00+00:00")

        assert result is not None
        assert result.year == 2025
        assert result.tzinfo is not None

    def test_parse_datetime_none_returns_none(self):
        """None input returns None."""
        result = _parse_datetime(None)
        assert result is None

    def test_parse_datetime_passthrough(self):
        """Already datetime objects pass through unchanged."""
        dt = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = _parse_datetime(dt)

        assert result is dt


class TestBoardFromTasks:
    """Tests for Board.from_tasks grouping."""

    def test_from_tasks_groups_all_states(self):
        """from_tasks correctly groups tasks by all 4 states."""
        tasks = [
            Task(filename="t1.md", state=STATE_TODO),
            Task(filename="t2.md", state=STATE_IN_PROGRESS),
            Task(filename="t3.md", state=STATE_DONE),
            Task(filename="t4.md", state=STATE_ARCHIVED),
        ]

        board = Board.from_tasks(tasks)

        assert len(board.get_column(STATE_TODO)) == 1
        assert len(board.get_column(STATE_IN_PROGRESS)) == 1
        assert len(board.get_column(STATE_DONE)) == 1
        assert len(board.get_column(STATE_ARCHIVED)) == 1
        assert board.get_column(STATE_TODO)[0].filename == "t1.md"
        assert board.get_column(STATE_IN_PROGRESS)[0].filename == "t2.md"
        assert board.get_column(STATE_DONE)[0].filename == "t3.md"
        assert board.get_column(STATE_ARCHIVED)[0].filename == "t4.md"

    def test_from_tasks_empty_list(self):
        """from_tasks handles empty task list."""
        board = Board.from_tasks([])

        assert board.get_column(STATE_TODO) == []
        assert board.get_column(STATE_IN_PROGRESS) == []
        assert board.get_column(STATE_DONE) == []
        assert board.get_column(STATE_ARCHIVED) == []

    def test_from_tasks_multiple_same_state(self):
        """from_tasks handles multiple tasks in same state."""
        tasks = [
            Task(filename="t1.md", state=STATE_TODO),
            Task(filename="t2.md", state=STATE_TODO),
            Task(filename="t3.md", state=STATE_TODO),
        ]

        board = Board.from_tasks(tasks)

        assert len(board.get_column(STATE_TODO)) == 3
        filenames = [t.filename for t in board.get_column(STATE_TODO)]
        assert filenames == ["t1.md", "t2.md", "t3.md"]


class TestBoardDynamicColumns:
    """Tests for Board with dynamic column configuration."""

    def test_from_tasks_custom_config(self):
        """from_tasks with custom config creates correct columns."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="backlog", title="Backlog"),
                ColumnConfig(id="active", title="Active"),
                ColumnConfig(id="complete", title="Complete"),
            ]
        )
        tasks = [
            Task(filename="a.md", state="backlog"),
            Task(filename="b.md", state="active"),
            Task(filename="c.md", state="complete"),
        ]

        board = Board.from_tasks(tasks, config)

        assert len(board.get_column("backlog")) == 1
        assert len(board.get_column("active")) == 1
        assert len(board.get_column("complete")) == 1
        assert board.get_column("backlog")[0].filename == "a.md"

    def test_unknown_state_goes_to_first_column(self):
        """Tasks with unknown states go to first configured column."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="todo", title="To Do"),
                ColumnConfig(id="done", title="Done"),
            ]
        )
        tasks = [
            Task(filename="a.md", state="weird_unknown_state"),
        ]

        board = Board.from_tasks(tasks, config)

        # Unknown state placed in first column (todo)
        assert len(board.get_column("todo")) == 1
        assert board.get_column("todo")[0].filename == "a.md"
        # Original state preserved on task
        assert board.get_column("todo")[0].state == "weird_unknown_state"

    def test_archived_always_available(self):
        """Archived column always exists even with custom config."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="backlog", title="Backlog"),
                ColumnConfig(id="done", title="Done"),
            ]
        )
        tasks = [
            Task(filename="archived.md", state=STATE_ARCHIVED),
        ]

        board = Board.from_tasks(tasks, config)

        assert len(board.get_column(STATE_ARCHIVED)) == 1
        assert board.get_column(STATE_ARCHIVED)[0].filename == "archived.md"

    def test_get_visible_columns(self):
        """get_visible_columns returns correct tuples."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="a", title="Column A"),
                ColumnConfig(id="b", title="Column B"),
            ]
        )
        tasks = [
            Task(filename="1.md", state="a"),
            Task(filename="2.md", state="b"),
            Task(filename="3.md", state=STATE_ARCHIVED),
        ]

        board = Board.from_tasks(tasks, config)
        visible = board.get_visible_columns(config)

        assert len(visible) == 2
        assert visible[0] == ("a", "Column A", board.get_column("a"))
        assert visible[1] == ("b", "Column B", board.get_column("b"))

    def test_tasks_with_alias_states(self):
        """Tasks with alias states are placed in correct column."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="todo", title="To Do", status_alias=["new"]),
                ColumnConfig(id="done", title="Done", status_alias=["finished"]),
            ]
        )
        tasks = [
            Task(filename="1.md", state="new"),
            Task(filename="2.md", state="finished"),
            Task(filename="3.md", state="todo"),
        ]

        board = Board.from_tasks(tasks, config)

        assert len(board.get_column("todo")) == 2
        assert len(board.get_column("done")) == 1

        todo_files = sorted([t.filename for t in board.get_column("todo")])
        assert todo_files == ["1.md", "3.md"]


class TestBoardOrderDynamic:
    """Tests for BoardOrder with dynamic columns."""

    def test_default_creates_standard_columns(self):
        """BoardOrder.default() creates standard 4 columns."""
        order = BoardOrder.default()

        assert "todo" in order.columns
        assert "in_progress" in order.columns
        assert "done" in order.columns
        assert "archived" in order.columns

    def test_from_config_creates_config_columns(self):
        """BoardOrder.from_config() creates columns from config."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="backlog", title="Backlog"),
                ColumnConfig(id="active", title="Active"),
            ]
        )

        order = BoardOrder.from_config(config)

        assert "backlog" in order.columns
        assert "active" in order.columns
        assert "archived" in order.columns  # Always added
        assert "todo" not in order.columns  # Not in config

    def test_ensure_column_creates_missing(self):
        """ensure_column creates column if missing."""
        order = BoardOrder.default()

        assert "custom" not in order.columns
        order.ensure_column("custom")
        assert "custom" in order.columns
        assert order.columns["custom"] == []

    def test_ensure_column_no_op_for_existing(self):
        """ensure_column doesn't affect existing columns."""
        order = BoardOrder.default()
        order.columns["todo"].append("task.md")

        order.ensure_column("todo")

        assert order.columns["todo"] == ["task.md"]
