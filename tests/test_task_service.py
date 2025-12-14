"""Integration tests for TaskService."""

from pathlib import Path

import pytest

from sltasks.models.task import STATE_IN_PROGRESS, STATE_TODO
from sltasks.repositories import FilesystemRepository
from sltasks.services import TaskService


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
def task_service(repo: FilesystemRepository) -> TaskService:
    """Create a TaskService with the repository."""
    return TaskService(repo)


class TestTaskServiceCreate:
    """Tests for task creation."""

    def test_create_task_basic(self, task_service: TaskService, task_dir: Path):
        """create_task creates a task file with correct defaults."""
        task = task_service.create_task("My New Task")

        assert task.id == "my-new-task.md"
        assert task.title == "My New Task"
        assert task.state == STATE_TODO
        assert task.priority == "medium"
        assert task.created is not None
        assert task.updated is not None
        assert (task_dir / "my-new-task.md").exists()

    def test_create_task_in_specific_state(self, task_service: TaskService):
        """create_task respects state parameter."""
        task = task_service.create_task(
            "In Progress Task",
            state=STATE_IN_PROGRESS,
            priority="high",
        )

        assert task.state == STATE_IN_PROGRESS
        assert task.priority == "high"

    def test_create_task_unique_id_collision(self, task_service: TaskService):
        """Creating tasks with same title generates unique IDs."""
        task1 = task_service.create_task("Fix Bug")
        task2 = task_service.create_task("Fix Bug")

        assert task1.id == "fix-bug.md"
        assert task2.id == "fix-bug-1.md"

    def test_create_task_multiple_collisions(self, task_service: TaskService):
        """Handles 3+ tasks with same title."""
        task1 = task_service.create_task("Same Title")
        task2 = task_service.create_task("Same Title")
        task3 = task_service.create_task("Same Title")

        assert task1.id == "same-title.md"
        assert task2.id == "same-title-1.md"
        assert task3.id == "same-title-2.md"


class TestTaskServiceUpdate:
    """Tests for task updates."""

    def test_update_task_changes_updated_timestamp(
        self, task_service: TaskService, repo: FilesystemRepository
    ):
        """update_task automatically updates the timestamp."""
        task = task_service.create_task("Update Me")
        original_updated = task.updated

        # Modify and update
        task.title = "Updated Title"
        updated_task = task_service.update_task(task)

        assert updated_task.updated > original_updated
        assert updated_task.title == "Updated Title"

        # Verify persisted
        reloaded = repo.get_by_id(task.id)
        assert reloaded.title == "Updated Title"


class TestTaskServiceDelete:
    """Tests for task deletion."""

    def test_delete_task_removes_file(
        self, task_service: TaskService, task_dir: Path, repo: FilesystemRepository
    ):
        """delete_task removes the file and board order entry."""
        task = task_service.create_task("Delete Me")
        task_id = task.id
        assert (task_dir / task_id).exists()

        task_service.delete_task(task_id)

        assert not (task_dir / task_id).exists()
        assert repo.get_by_id(task_id) is None


class TestTaskServiceGet:
    """Tests for task retrieval."""

    def test_get_task_returns_none_for_missing(self, task_service: TaskService):
        """get_task returns None for non-existent task."""
        result = task_service.get_task("nonexistent.md")
        assert result is None
