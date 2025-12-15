"""Integration tests for FilesystemRepository."""

from pathlib import Path

import pytest

from sltasks.models import BoardOrder, Task
from sltasks.models.task import (
    STATE_DONE,
    STATE_IN_PROGRESS,
    STATE_TODO,
)
from sltasks.repositories import FilesystemRepository


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


class TestFilesystemRepository:
    """Tests for FilesystemRepository."""

    def test_ensure_directory_creates_missing_dir(self, tmp_path: Path):
        """ensure_directory creates the directory if it doesn't exist."""
        task_root = tmp_path / ".tasks"
        repo = FilesystemRepository(task_root)

        assert not task_root.exists()
        repo.ensure_directory()
        assert task_root.exists()

    def test_get_all_empty_directory(self, repo: FilesystemRepository):
        """get_all returns empty list for empty directory."""
        tasks = repo.get_all()
        assert tasks == []

    def test_get_all_loads_tasks(self, task_dir: Path, repo: FilesystemRepository):
        """get_all loads all .md files from directory."""
        # Create some task files
        (task_dir / "task1.md").write_text(
            "---\ntitle: Task 1\nstate: todo\npriority: high\n---\nBody 1"
        )
        (task_dir / "task2.md").write_text(
            "---\ntitle: Task 2\nstate: in_progress\npriority: medium\n---\nBody 2"
        )

        tasks = repo.get_all()

        assert len(tasks) == 2
        task_ids = {t.id for t in tasks}
        assert task_ids == {"task1.md", "task2.md"}

    def test_get_all_handles_minimal_frontmatter(self, task_dir: Path, repo: FilesystemRepository):
        """get_all handles files with no frontmatter."""
        (task_dir / "minimal.md").write_text("# Just a heading\n\nSome content.")

        tasks = repo.get_all()

        assert len(tasks) == 1
        task = tasks[0]
        assert task.id == "minimal.md"
        assert task.state == STATE_TODO  # default
        assert task.priority is None  # default (unset)

    def test_get_by_id_returns_task(self, task_dir: Path, repo: FilesystemRepository):
        """get_by_id returns the task if it exists."""
        (task_dir / "my-task.md").write_text("---\ntitle: My Task\nstate: done\n---\nContent")

        task = repo.get_by_id("my-task.md")

        assert task is not None
        assert task.title == "My Task"
        assert task.state == STATE_DONE

    def test_get_by_id_returns_none_for_missing(self, repo: FilesystemRepository):
        """get_by_id returns None if file doesn't exist."""
        task = repo.get_by_id("nonexistent.md")
        assert task is None

    def test_save_creates_new_task(self, repo: FilesystemRepository, task_dir: Path):
        """save creates a new task file."""
        task = Task(
            id="new-task.md",
            title="New Task",
            state=STATE_TODO,
            priority="high",
            tags=["bug", "urgent"],
            body="Task description here.",
        )

        saved = repo.save(task)

        # Verify provider_data is set
        assert saved.provider_data is not None
        assert saved.provider_data.provider == "file"

        # Verify file exists (using repo.get_filepath helper)
        filepath = repo.get_filepath(saved)
        assert filepath == task_dir / "new-task.md"
        assert filepath.exists()

        # Verify file contents
        content = filepath.read_text()
        assert "title: New Task" in content
        assert "state: todo" in content
        assert "priority: high" in content
        assert "Task description here." in content

    def test_save_updates_existing_task(self, repo: FilesystemRepository, task_dir: Path):  # noqa: ARG002
        """save updates an existing task file."""
        # Create initial task
        task = Task(
            id="update-me.md",
            title="Original Title",
            state=STATE_TODO,
        )
        repo.save(task)

        # Update it
        task.title = "Updated Title"
        task.state = STATE_IN_PROGRESS
        repo.save(task)

        # Reload and verify
        reloaded = repo.get_by_id("update-me.md")
        assert reloaded is not None
        assert reloaded.title == "Updated Title"
        assert reloaded.state == STATE_IN_PROGRESS

    def test_delete_removes_task(self, repo: FilesystemRepository, task_dir: Path):
        """delete removes the task file."""
        task = Task(id="delete-me.md", title="Delete Me")
        repo.save(task)
        assert (task_dir / "delete-me.md").exists()

        repo.delete("delete-me.md")

        assert not (task_dir / "delete-me.md").exists()

    def test_delete_handles_nonexistent(self, repo: FilesystemRepository):
        """delete doesn't raise error for nonexistent file."""
        repo.delete("nonexistent.md")  # Should not raise


class TestBoardOrder:
    """Tests for board order management."""

    def test_save_creates_tasks_yaml(self, repo: FilesystemRepository, task_dir: Path):
        """Saving a task creates tasks.yaml."""
        task = Task(id="task.md", title="Task", state=STATE_TODO)
        repo.save(task)

        yaml_path = task_dir / "tasks.yaml"
        assert yaml_path.exists()

        content = yaml_path.read_text()
        assert "task.md" in content
        assert "todo:" in content

    def test_get_board_order_returns_order(self, repo: FilesystemRepository, task_dir: Path):  # noqa: ARG002
        """get_board_order returns the current ordering."""
        # Create tasks in different states
        repo.save(Task(id="t1.md", state=STATE_TODO))
        repo.save(Task(id="t2.md", state=STATE_IN_PROGRESS))
        repo.save(Task(id="t3.md", state=STATE_DONE))

        order = repo.get_board_order()

        assert "t1.md" in order.columns["todo"]
        assert "t2.md" in order.columns["in_progress"]
        assert "t3.md" in order.columns["done"]

    def test_save_board_order_persists(self, repo: FilesystemRepository, task_dir: Path):  # noqa: ARG002
        """save_board_order persists changes."""
        order = BoardOrder()
        order.add_task("a.md", "todo")
        order.add_task("b.md", "todo", position=0)  # Insert at front

        repo.save_board_order(order)

        # Reload
        repo.reload()
        reloaded = repo.get_board_order()

        assert reloaded.columns["todo"] == ["b.md", "a.md"]


class TestReconciliation:
    """Tests for reconciliation logic."""

    def test_new_files_added_to_yaml(self, task_dir: Path, repo: FilesystemRepository):
        """Files not in yaml are added based on their state."""
        # Create a file directly (not through repo)
        (task_dir / "new-file.md").write_text("---\nstate: in_progress\n---\nContent")

        tasks = repo.get_all()

        assert len(tasks) == 1
        order = repo.get_board_order()
        assert "new-file.md" in order.columns["in_progress"]

    def test_missing_files_removed_from_yaml(self, task_dir: Path, repo: FilesystemRepository):  # noqa: ARG002
        """Files in yaml but not on disk are removed from yaml."""
        # Create a task through repo
        repo.save(Task(id="exists.md", state=STATE_TODO))

        # Manually add a reference to a non-existent file
        order = repo.get_board_order()
        order.add_task("ghost.md", "todo")
        repo.save_board_order(order)

        # Reload and reconcile
        repo.reload()
        repo.get_all()  # Trigger reconciliation

        # ghost.md should be removed
        order = repo.get_board_order()
        assert "ghost.md" not in order.columns["todo"]
        assert "exists.md" in order.columns["todo"]

    def test_file_state_takes_precedence(self, task_dir: Path, repo: FilesystemRepository):
        """If file state differs from yaml column, file wins."""
        # Create task as TODO
        repo.save(Task(id="task.md", state=STATE_TODO))

        # Manually change the file to IN_PROGRESS
        (task_dir / "task.md").write_text("---\nstate: in_progress\n---\nContent")

        # Reload and reconcile
        repo.reload()
        repo.get_all()  # Trigger reconciliation

        order = repo.get_board_order()
        assert "task.md" not in order.columns["todo"]
        assert "task.md" in order.columns["in_progress"]

    def test_tasks_sorted_by_board_order(self, task_dir: Path, repo: FilesystemRepository):  # noqa: ARG002
        """get_all returns tasks sorted by board order position."""
        # Create tasks
        repo.save(Task(id="c.md", state=STATE_TODO))
        repo.save(Task(id="a.md", state=STATE_TODO))
        repo.save(Task(id="b.md", state=STATE_TODO))

        # Set custom order
        order = repo.get_board_order()
        order.columns["todo"] = ["b.md", "a.md", "c.md"]
        repo.save_board_order(order)

        # Reload and check order
        repo.reload()
        tasks = repo.get_all()

        todo_tasks = [t for t in tasks if t.state == STATE_TODO]
        task_ids = [t.id for t in todo_tasks]
        assert task_ids == ["b.md", "a.md", "c.md"]


class TestReload:
    """Tests for reload functionality."""

    def test_reload_clears_cache(self, task_dir: Path, repo: FilesystemRepository):
        """reload clears internal caches."""
        repo.save(Task(id="task.md", state=STATE_TODO))
        tasks1 = repo.get_all()
        assert len(tasks1) == 1

        # Add a file directly
        (task_dir / "new.md").write_text("---\nstate: todo\n---\n")

        # Without reload, cache is stale
        # With reload, new file is picked up
        repo.reload()
        tasks2 = repo.get_all()
        assert len(tasks2) == 2

    def test_reload_handles_alias_normalization(self, task_dir: Path, repo: FilesystemRepository):
        """Tasks with alias states are normalized on load."""
        (task_dir / "alias.md").write_text("---\nstate: new\n---\n")

        repo.reload()
        task = repo.get_by_id("alias.md")

        assert task is not None
        assert task.state == STATE_TODO  # Normalized from 'new'


class TestOptionalPriority:
    """Tests for optional (None) priority support."""

    def test_save_task_with_none_priority(self, repo: FilesystemRepository):
        """Saving a task with None priority works correctly."""
        task = Task(
            id="no-priority.md",
            title="Task Without Priority",
            state=STATE_TODO,
            priority=None,
        )
        repo.save(task)

        # Read back and verify
        loaded = repo.get_by_id("no-priority.md")
        assert loaded is not None
        assert loaded.priority is None

    def test_load_task_without_priority_field(self, task_dir: Path, repo: FilesystemRepository):
        """Loading a task file without priority field results in None priority."""
        # Create file without priority in frontmatter
        (task_dir / "missing-priority.md").write_text(
            "---\ntitle: Missing Priority\nstate: todo\n---\nBody content\n"
        )

        repo.reload()
        task = repo.get_by_id("missing-priority.md")

        assert task is not None
        assert task.priority is None

    def test_save_and_load_preserves_none_priority(self, repo: FilesystemRepository):
        """Round-trip save/load preserves None priority."""
        task = Task(
            id="roundtrip.md",
            title="Roundtrip Test",
            state=STATE_TODO,
            priority=None,
            tags=["test"],
        )
        repo.save(task)

        # Reload and verify
        repo.reload()
        loaded = repo.get_by_id("roundtrip.md")
        assert loaded is not None
        assert loaded.priority is None
        assert loaded.tags == ["test"]
