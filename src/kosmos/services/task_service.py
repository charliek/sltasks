"""Service for task CRUD operations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import Priority, Task
from ..models.sltasks_config import BoardConfig
from ..repositories import FilesystemRepository
from ..utils import generate_filename, now_utc

if TYPE_CHECKING:
    from .config_service import ConfigService


class TaskService:
    """Service for task CRUD operations."""

    def __init__(
        self,
        repository: FilesystemRepository,
        config_service: ConfigService | None = None,
    ) -> None:
        self.repository = repository
        self._config_service = config_service

    def _get_default_state(self) -> str:
        """Get the default state for new tasks (first column)."""
        if self._config_service:
            config = self._config_service.get_board_config()
            return config.columns[0].id
        return "todo"

    def create_task(
        self,
        title: str,
        state: str | None = None,
        priority: Priority = Priority.MEDIUM,
        tags: list[str] | None = None,
    ) -> Task:
        """
        Create a new task with the given title.

        Generates a filename from the title and creates the file.
        If state is not provided, uses first column from config.
        """
        if state is None:
            state = self._get_default_state()

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

    def rename_task_to_match_title(self, filename: str) -> Task | None:
        """
        Rename a task file to match its current title.

        Reads the task, generates a new filename from the title,
        and renames the file if needed.

        Returns the task with updated filename, or None if task not found.
        """
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        # Generate filename from current title
        new_filename = generate_filename(task.title)

        # If filename would be the same, nothing to do
        if new_filename == filename:
            return task

        # Ensure unique filename
        new_filename = self._unique_filename(new_filename)

        # Rename the file
        if task.filepath and task.filepath.exists():
            new_filepath = task.filepath.parent / new_filename
            task.filepath.rename(new_filepath)

            # Update task with new filename/filepath
            old_filename = task.filename
            task.filename = new_filename
            task.filepath = new_filepath

            # Update board order to reflect the rename
            self.repository.rename_in_board_order(old_filename, new_filename)

        return task

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

        # Try $EDITOR, then common fallbacks
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if not editor:
            # Try common editors in order of preference
            for candidate in ["nvim", "vim", "vi", "nano"]:
                if self._command_exists(candidate):
                    editor = candidate
                    break
            else:
                return False

        # Handle editors with arguments (e.g., "zed --wait", "code --wait")
        # Use shell=True to properly handle the command string
        import shlex
        editor_parts = shlex.split(editor)
        editor_cmd = editor_parts + [str(task.filepath.absolute())]

        try:
            result = subprocess.run(
                editor_cmd,
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            # Editor not found
            return False

    def _command_exists(self, cmd: str) -> bool:
        """Check if a command exists in PATH."""
        import shutil
        return shutil.which(cmd) is not None

    def _unique_filename(self, filename: str) -> str:
        """Ensure filename is unique by appending numbers if needed."""
        base = filename.removesuffix(".md")
        candidate = filename
        counter = 1

        while self.repository.get_by_id(candidate) is not None:
            candidate = f"{base}-{counter}.md"
            counter += 1

        return candidate
