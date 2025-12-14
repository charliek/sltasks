"""Service for task CRUD operations."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from ..models import FileProviderData, Task
from ..repositories import RepositoryProtocol
from ..utils import generate_filename, now_utc

if TYPE_CHECKING:
    from .config_service import ConfigService
    from .template_service import TemplateService


class TaskService:
    """Service for task CRUD operations."""

    def __init__(
        self,
        repository: RepositoryProtocol,
        config_service: ConfigService | None = None,
        template_service: TemplateService | None = None,
    ) -> None:
        self.repository = repository
        self._config_service = config_service
        self._template_service = template_service

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
        priority: str | None = None,
        tags: list[str] | None = None,
        task_type: str | None = None,
    ) -> Task:
        """
        Create a new task with the given title.

        Generates a filename from the title and creates the file.
        If state is not provided, uses first column from config.
        If task_type is provided and a template exists, the template's
        frontmatter provides defaults and body content.
        """
        if state is None:
            state = self._get_default_state()
        elif self._config_service:
            # Resolve alias to canonical ID
            config = self._config_service.get_board_config()
            state = config.resolve_status(state)

        # Resolve type alias to canonical ID
        resolved_type = task_type
        if task_type and self._config_service:
            config = self._config_service.get_board_config()
            resolved_type = config.resolve_type(task_type)

        filename = generate_filename(title)

        # Handle filename collision
        filename = self._unique_filename(filename)

        now = now_utc()

        # Base values (always set)
        final_priority = priority if priority is not None else "medium"
        final_tags = tags if tags is not None else []
        body = ""

        # Apply template if type provided and template service available
        if resolved_type and self._template_service:
            base_fm = {
                "title": title,
                "state": state,
                "created": now.isoformat(),
                "updated": now.isoformat(),
            }
            merged_fm, body = self._template_service.apply_template(resolved_type, base_fm)

            # Use template defaults if not explicitly provided
            if priority is None and "priority" in merged_fm:
                final_priority = merged_fm["priority"]
            if tags is None and "tags" in merged_fm:
                final_tags = merged_fm.get("tags", [])

        task = Task(
            id=filename,
            title=title,
            state=state,
            priority=final_priority,
            tags=final_tags,  # pyrefly: ignore[bad-argument-type]
            type=resolved_type,
            created=now,
            updated=now,
            body=body,
        )

        return self.repository.save(task)

    def update_task(self, task: Task) -> Task:
        """
        Update an existing task.

        Updates the 'updated' timestamp automatically.
        """
        task.updated = now_utc()
        return self.repository.save(task)

    def delete_task(self, task_id: str) -> None:
        """Delete a task by ID."""
        self.repository.delete(task_id)

    def rename_task_to_match_title(
        self, task_id: str, task_root: Path | None = None
    ) -> Task | None:
        """
        Rename a task file to match its current title.

        Reads the task, generates a new ID from the title,
        and renames the file if needed. This is a filesystem-specific operation.

        Args:
            task_id: The current task ID (filename)
            task_root: The task root directory (required for filesystem tasks)

        Returns the task with updated ID, or None if task not found.
        """
        task = self.repository.get_by_id(task_id)
        if task is None:
            return None

        # This operation only makes sense for filesystem tasks
        if not isinstance(task.provider_data, FileProviderData):
            return task

        if task_root is None:
            return task

        # Generate filename from current title (use display_title which never returns None)
        new_task_id = generate_filename(task.display_title)

        # If ID would be the same, nothing to do
        if new_task_id == task_id:
            return task

        # Ensure unique ID
        new_task_id = self._unique_filename(new_task_id)

        # Rename the file
        filepath = task_root / task_id
        if filepath.exists():
            new_filepath = task_root / new_task_id
            filepath.rename(new_filepath)

            # Update task with new ID
            old_task_id = task.id
            task.id = new_task_id

            # Update board order to reflect the rename
            self.repository.rename_in_board_order(old_task_id, new_task_id)

        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.repository.get_by_id(task_id)

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks."""
        return self.repository.get_all()

    def open_in_editor(self, task: Task, task_root: Path | None = None) -> bool:
        """
        Open task file in the user's editor.

        This is a filesystem-specific operation. For non-filesystem tasks,
        returns False.

        Args:
            task: The task to edit
            task_root: The task root directory (required for filesystem tasks)

        Returns True if editor exited successfully.
        """
        # Only filesystem tasks can be edited locally
        if not isinstance(task.provider_data, FileProviderData):
            return False

        if task_root is None:
            return False

        filepath = task_root / task.id

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
        editor_cmd = [*editor_parts, str(filepath.absolute())]

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
