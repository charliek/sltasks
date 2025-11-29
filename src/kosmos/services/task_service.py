"""Service for task CRUD operations."""

import os
import subprocess
from pathlib import Path

from ..models import Priority, Task, TaskState
from ..repositories import FilesystemRepository
from ..utils import generate_filename, now_utc


class TaskService:
    """Service for task CRUD operations."""

    def __init__(self, repository: FilesystemRepository) -> None:
        self.repository = repository

    def create_task(
        self,
        title: str,
        state: TaskState = TaskState.TODO,
        priority: Priority = Priority.MEDIUM,
        tags: list[str] | None = None,
    ) -> Task:
        """
        Create a new task with the given title.

        Generates a filename from the title and creates the file.
        """
        filename = generate_filename(title)

        # Handle filename collision
        filename = self._unique_filename(filename)

        now = now_utc()
        task = Task(
            filename=filename,
            title=title,
            state=state,
            priority=priority,
            tags=tags or [],
            created=now,
            updated=now,
            body="",
        )

        return self.repository.save(task)

    def update_task(self, task: Task) -> Task:
        """
        Update an existing task.

        Updates the 'updated' timestamp automatically.
        """
        task.updated = now_utc()
        return self.repository.save(task)

    def delete_task(self, filename: str) -> None:
        """Delete a task by filename."""
        self.repository.delete(filename)

    def get_task(self, filename: str) -> Task | None:
        """Get a task by filename."""
        return self.repository.get_by_id(filename)

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks."""
        return self.repository.get_all()

    def open_in_editor(self, task: Task) -> bool:
        """
        Open task file in the user's editor.

        Returns True if editor exited successfully.
        """
        if task.filepath is None:
            return False

        editor = os.environ.get("EDITOR", "vim")

        try:
            result = subprocess.run(
                [editor, str(task.filepath)],
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            # Editor not found
            return False

    def _unique_filename(self, filename: str) -> str:
        """Ensure filename is unique by appending numbers if needed."""
        base = filename.removesuffix(".md")
        candidate = filename
        counter = 1

        while self.repository.get_by_id(candidate) is not None:
            candidate = f"{base}-{counter}.md"
            counter += 1

        return candidate
