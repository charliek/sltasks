"""Unit tests for model edge cases."""

import pytest
from datetime import datetime, timezone

from kosmos.models import Task, TaskState, Priority, Board
from kosmos.models.task import _parse_datetime


class TestTaskFromFrontmatter:
    """Tests for Task.from_frontmatter edge cases."""

    def test_from_frontmatter_invalid_state_uses_default(self):
        """Invalid state value raises ValueError (Pydantic validation)."""
        # TaskState enum will raise ValueError for invalid values
        with pytest.raises(ValueError):
            Task.from_frontmatter(
                filename="task.md",
                metadata={"state": "invalid_state"},
                body="",
            )

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
        assert task.state == TaskState.TODO

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
            Task(filename="t1.md", state=TaskState.TODO),
            Task(filename="t2.md", state=TaskState.IN_PROGRESS),
            Task(filename="t3.md", state=TaskState.DONE),
            Task(filename="t4.md", state=TaskState.ARCHIVED),
        ]

        board = Board.from_tasks(tasks)

        assert len(board.todo) == 1
        assert len(board.in_progress) == 1
        assert len(board.done) == 1
        assert len(board.archived) == 1
        assert board.todo[0].filename == "t1.md"
        assert board.in_progress[0].filename == "t2.md"
        assert board.done[0].filename == "t3.md"
        assert board.archived[0].filename == "t4.md"

    def test_from_tasks_empty_list(self):
        """from_tasks handles empty task list."""
        board = Board.from_tasks([])

        assert board.todo == []
        assert board.in_progress == []
        assert board.done == []
        assert board.archived == []

    def test_from_tasks_multiple_same_state(self):
        """from_tasks handles multiple tasks in same state."""
        tasks = [
            Task(filename="t1.md", state=TaskState.TODO),
            Task(filename="t2.md", state=TaskState.TODO),
            Task(filename="t3.md", state=TaskState.TODO),
        ]

        board = Board.from_tasks(tasks)

        assert len(board.todo) == 3
        filenames = [t.filename for t in board.todo]
        assert filenames == ["t1.md", "t2.md", "t3.md"]
