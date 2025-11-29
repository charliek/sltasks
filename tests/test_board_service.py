"""Integration tests for BoardService."""

import pytest
from pathlib import Path

from kosmos.models import Task, Priority
from kosmos.models.task import (
    STATE_ARCHIVED,
    STATE_DONE,
    STATE_IN_PROGRESS,
    STATE_TODO,
)
from kosmos.repositories import FilesystemRepository
from kosmos.services import BoardService


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    """Create a temporary task directory."""
    task_root = tmp_path / ".tasks"
    task_root.mkdir()
    return task_root


@pytest.fixture
def repo(task_dir: Path) -> FilesystemRepository:
    """Create a repository with a temporary directory."""
    return FilesystemRepository(task_dir)


@pytest.fixture
def board_service(repo: FilesystemRepository) -> BoardService:
    """Create a BoardService with the repository."""
    return BoardService(repo)


def create_task_file(task_dir: Path, filename: str, state: str = "todo") -> None:
    """Helper to create a task file directly."""
    (task_dir / filename).write_text(
        f"---\ntitle: {filename.replace('.md', '').replace('-', ' ').title()}\n"
        f"state: {state}\npriority: medium\n---\nBody content"
    )


class TestBoardServiceLoad:
    """Tests for board loading."""

    def test_load_board_groups_by_state(
        self, board_service: BoardService, task_dir: Path
    ):
        """load_board groups tasks into correct columns."""
        create_task_file(task_dir, "task1.md", "todo")
        create_task_file(task_dir, "task2.md", "in_progress")
        create_task_file(task_dir, "task3.md", "done")
        create_task_file(task_dir, "task4.md", "archived")

        board = board_service.load_board()

        assert len(board.todo) == 1
        assert len(board.in_progress) == 1
        assert len(board.done) == 1
        assert len(board.archived) == 1
        assert board.todo[0].filename == "task1.md"
        assert board.in_progress[0].filename == "task2.md"


class TestBoardServiceMoveTask:
    """Tests for moving tasks between columns."""

    def test_move_task_updates_state_and_file(
        self, board_service: BoardService, task_dir: Path, repo: FilesystemRepository
    ):
        """move_task updates state in file and board order."""
        create_task_file(task_dir, "task.md", "todo")

        result = board_service.move_task("task.md", STATE_IN_PROGRESS)

        assert result is not None
        assert result.state == STATE_IN_PROGRESS

        # Verify persisted
        reloaded = repo.get_by_id("task.md")
        assert reloaded.state == STATE_IN_PROGRESS

    def test_move_task_left_from_in_progress(
        self, board_service: BoardService, task_dir: Path
    ):
        """move_task_left moves in_progress to todo."""
        create_task_file(task_dir, "task.md", "in_progress")

        result = board_service.move_task_left("task.md")

        assert result is not None
        assert result.state == STATE_TODO

    def test_move_task_left_from_todo_stays(
        self, board_service: BoardService, task_dir: Path
    ):
        """move_task_left from todo stays at todo (boundary)."""
        create_task_file(task_dir, "task.md", "todo")

        result = board_service.move_task_left("task.md")

        assert result is not None
        assert result.state == STATE_TODO

    def test_move_task_right_from_done_stays(
        self, board_service: BoardService, task_dir: Path
    ):
        """move_task_right from done stays at done (boundary)."""
        create_task_file(task_dir, "task.md", "done")

        result = board_service.move_task_right("task.md")

        assert result is not None
        assert result.state == STATE_DONE

    def test_move_task_from_archived_does_nothing(
        self, board_service: BoardService, task_dir: Path
    ):
        """move_task_left/right from archived returns task unchanged."""
        create_task_file(task_dir, "task.md", "archived")

        result_left = board_service.move_task_left("task.md")
        assert result_left is not None
        assert result_left.state == STATE_ARCHIVED

        result_right = board_service.move_task_right("task.md")
        assert result_right is not None
        assert result_right.state == STATE_ARCHIVED


class TestBoardServiceArchive:
    """Tests for archiving tasks."""

    def test_archive_task_changes_state(
        self, board_service: BoardService, task_dir: Path
    ):
        """archive_task moves task to archived state."""
        create_task_file(task_dir, "task.md", "todo")

        result = board_service.archive_task("task.md")

        assert result is not None
        assert result.state == STATE_ARCHIVED


class TestBoardServiceReorder:
    """Tests for reordering tasks within columns."""

    def test_reorder_task_up(
        self, board_service: BoardService, task_dir: Path, repo: FilesystemRepository
    ):
        """reorder_task with delta=-1 moves task up."""
        create_task_file(task_dir, "task1.md", "todo")
        create_task_file(task_dir, "task2.md", "todo")
        # Force order: task1, task2
        board_service.load_board()
        order = repo.get_board_order()
        order.columns["todo"] = ["task1.md", "task2.md"]
        repo.save_board_order(order)

        result = board_service.reorder_task("task2.md", -1)

        assert result is True
        order = repo.get_board_order()
        assert order.columns["todo"] == ["task2.md", "task1.md"]

    def test_reorder_task_down(
        self, board_service: BoardService, task_dir: Path, repo: FilesystemRepository
    ):
        """reorder_task with delta=1 moves task down."""
        create_task_file(task_dir, "task1.md", "todo")
        create_task_file(task_dir, "task2.md", "todo")
        board_service.load_board()
        order = repo.get_board_order()
        order.columns["todo"] = ["task1.md", "task2.md"]
        repo.save_board_order(order)

        result = board_service.reorder_task("task1.md", 1)

        assert result is True
        order = repo.get_board_order()
        assert order.columns["todo"] == ["task2.md", "task1.md"]

    def test_reorder_task_at_top_stays(
        self, board_service: BoardService, task_dir: Path, repo: FilesystemRepository
    ):
        """reorder_task up from top position returns False."""
        create_task_file(task_dir, "task1.md", "todo")
        create_task_file(task_dir, "task2.md", "todo")
        board_service.load_board()
        order = repo.get_board_order()
        order.columns["todo"] = ["task1.md", "task2.md"]
        repo.save_board_order(order)

        result = board_service.reorder_task("task1.md", -1)

        assert result is False
        order = repo.get_board_order()
        assert order.columns["todo"] == ["task1.md", "task2.md"]

    def test_reorder_task_at_bottom_stays(
        self, board_service: BoardService, task_dir: Path, repo: FilesystemRepository
    ):
        """reorder_task down from bottom position returns False."""
        create_task_file(task_dir, "task1.md", "todo")
        create_task_file(task_dir, "task2.md", "todo")
        board_service.load_board()
        order = repo.get_board_order()
        order.columns["todo"] = ["task1.md", "task2.md"]
        repo.save_board_order(order)

        result = board_service.reorder_task("task2.md", 1)

        assert result is False
        order = repo.get_board_order()
        assert order.columns["todo"] == ["task1.md", "task2.md"]
