"""Filesystem-based repository for task storage."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter
import yaml

from ..models import BoardOrder, FileProviderData, Task
from ..models.sltasks_config import BoardConfig

if TYPE_CHECKING:
    from ..services.config_service import ConfigService


class FilesystemRepository:
    """
    Repository for task files stored on the filesystem.

    Tasks are stored as individual .md files with YAML front matter.
    Ordering is maintained in a tasks.yaml file.
    """

    TASKS_YAML = "tasks.yaml"

    def __init__(self, task_root: Path, config_service: ConfigService | None = None) -> None:
        """
        Initialize repository.

        Args:
            task_root: Path to the tasks directory (e.g., .tasks/)
            config_service: Optional config service for column configuration
        """
        self.task_root = task_root
        self._config_service = config_service
        self._tasks: dict[str, Task] = {}
        self._board_order: BoardOrder | None = None

    def _get_board_config(self) -> BoardConfig:
        """Get board config, using default if no config service."""
        if self._config_service:
            return self._config_service.get_board_config()
        return BoardConfig.default()

    def ensure_directory(self) -> None:
        """Create the tasks directory if it doesn't exist."""
        self.task_root.mkdir(parents=True, exist_ok=True)

    # --- Task Operations ---

    def get_all(self) -> list[Task]:
        """Load and return all tasks from the filesystem."""
        self._load_tasks()
        self._load_board_order()
        self._reconcile()
        return self._sorted_tasks()

    def get_by_id(self, task_id: str) -> Task | None:
        """Load a single task by ID."""
        filepath = self.task_root / task_id
        if not filepath.exists():
            return None
        return self._parse_task_file(filepath)

    def get_filepath(self, task: Task) -> Path:
        """Get the filesystem path for a task.

        For filesystem tasks, the path is derived from task_root + task.id.
        """
        return self.task_root / task.id

    def save(self, task: Task) -> Task:
        """
        Save a task to the filesystem.

        Creates or updates the markdown file with front matter.
        Updates the tasks.yaml ordering.
        """
        self.ensure_directory()

        filepath = self.get_filepath(task)

        # Set provider data if not already set (task is immutable, create copy)
        if task.provider_data is None:
            task = task.model_copy(update={"provider_data": FileProviderData()})

        # Build front matter document
        post = frontmatter.Post(task.body)
        post.metadata = task.to_frontmatter()

        # Write file (sort_keys=False preserves original key order)
        with filepath.open("w") as f:
            f.write(frontmatter.dumps(post, sort_keys=False))

        # Update board order
        self._ensure_board_order()
        if self._board_order is not None:
            self._board_order.add_task(task.id, task.state)
            self._save_board_order()

        return task

    def delete(self, task_id: str) -> None:
        """Delete a task file from the filesystem."""
        filepath = self.task_root / task_id
        if filepath.exists():
            filepath.unlink()

        # Remove from board order
        self._ensure_board_order()
        if self._board_order is not None:
            self._board_order.remove_task(task_id)
            self._save_board_order()

    # --- Board Order Operations ---

    def get_board_order(self) -> BoardOrder:
        """Load and return the board order."""
        self._load_board_order()
        if self._board_order is None:
            self._board_order = BoardOrder.default()
        return self._board_order

    def save_board_order(self, order: BoardOrder) -> None:
        """Save the board order to tasks.yaml."""
        self._board_order = order
        self._save_board_order()

    def reorder_task(
        self,
        task_id: str,  # noqa: ARG002
        after_task_id: str | None,  # noqa: ARG002
    ) -> bool:
        """Reorder a task to appear after another task.

        For filesystem, ordering is already persisted via save_board_order(),
        so this is a no-op that returns True (args unused, names must match protocol).
        """
        return True

    def rename_in_board_order(self, old_task_id: str, new_task_id: str) -> None:
        """Rename a task in the board order."""
        self._ensure_board_order()
        if self._board_order is None:
            return

        # Find and replace the task ID in all columns
        for column in self._board_order.columns.values():
            for i, task_id in enumerate(column):
                if task_id == old_task_id:
                    column[i] = new_task_id
                    break

        self._save_board_order()

    # --- Reload Support ---

    def reload(self) -> None:
        """Clear caches and reload from filesystem."""
        self._tasks.clear()
        self._board_order = None

    def validate(self) -> tuple[bool, str | None]:
        """Validate filesystem repository configuration.

        For filesystem, we check that the task_root directory is accessible.

        Returns:
            (True, None) - Filesystem repository is always valid if task_root exists
                          or can be created.
        """
        try:
            # Ensure directory can be created if it doesn't exist
            self.ensure_directory()
            return (True, None)
        except (OSError, PermissionError) as e:
            return (False, f"Cannot access task directory: {e}")

    # --- Private Methods ---

    def _load_tasks(self) -> None:
        """Scan directory and load all task files."""
        self._tasks.clear()

        if not self.task_root.exists():
            return

        for filepath in self._iter_task_files():
            task = self._parse_task_file(filepath)
            if task:
                self._tasks[task.id] = task

    def _iter_task_files(self) -> Iterator[Path]:
        """Iterate over all .md files in the task root."""
        yield from self.task_root.glob("*.md")

    def _parse_task_file(self, filepath: Path) -> Task | None:
        """Parse a single task file."""
        try:
            post = frontmatter.load(filepath)  # pyrefly: ignore[bad-argument-type]
            task = Task.from_frontmatter(
                task_id=filepath.name,
                metadata=post.metadata,
                body=post.content,
                provider_data=FileProviderData(),
            )

            # Normalize alias states to canonical column IDs
            config = self._get_board_config()
            canonical_state = config.resolve_status(task.state)
            if canonical_state != task.state:
                # Task is immutable, create copy with normalized state
                # We don't save immediately - file keeps alias until next save
                task = task.model_copy(update={"state": canonical_state})

            return task
        except Exception:
            # Skip files that can't be parsed
            # TODO: Consider logging this
            return None

    def _load_board_order(self) -> None:
        """Load tasks.yaml if it exists."""
        if self._board_order is not None:
            return

        yaml_path = self.task_root / self.TASKS_YAML
        if yaml_path.exists():
            with yaml_path.open() as f:
                data = yaml.safe_load(f) or {}
            self._board_order = BoardOrder(**data)
        else:
            # Create new board order from config (or default)
            config = self._get_board_config()
            self._board_order = BoardOrder.from_config(config)

    def _ensure_board_order(self) -> None:
        """Ensure board order is loaded and has all config columns."""
        if self._board_order is None:
            self._load_board_order()

        # Ensure all config columns exist in board order
        if self._board_order is not None:
            config = self._get_board_config()
            for col in config.columns:
                self._board_order.ensure_column(col.id)
            self._board_order.ensure_column("archived")

    def _save_board_order(self) -> None:
        """Write tasks.yaml to disk."""
        if self._board_order is None:
            return

        self.ensure_directory()
        yaml_path = self.task_root / self.TASKS_YAML

        data = self._board_order.model_dump()
        with yaml_path.open("w") as f:
            f.write("# Auto-generated - do not edit manually\n")
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def _reconcile(self) -> None:
        """
        Reconcile tasks with board order.

        - Files are the source of truth for task state
        - YAML provides ordering within columns
        - Missing files are removed from YAML
        - New files are added to YAML based on their state
        """
        self._ensure_board_order()
        if self._board_order is None:
            return

        modified = False

        # Get set of actual task filenames
        actual_files = set(self._tasks.keys())

        # Remove references to missing files from yaml
        for state, filenames in list(self._board_order.columns.items()):
            for filename in filenames[:]:  # Copy list for safe iteration
                if filename not in actual_files:
                    self._board_order.columns[state].remove(filename)
                    modified = True

        # Add new files and fix misplaced files
        all_in_yaml: set[str] = set()
        for task_ids in self._board_order.columns.values():
            all_in_yaml.update(task_ids)

        for task_id, task in self._tasks.items():
            state_value = task.state  # Now a string, no .value needed

            if task_id not in all_in_yaml:
                # New file - add to appropriate column
                self._board_order.add_task(task_id, state_value)
                modified = True
            else:
                # Check if in wrong column (file state takes precedence)
                current_column = self._find_task_column(task_id)
                if current_column and current_column != state_value:
                    self._board_order.move_task(task_id, current_column, state_value)
                    modified = True

        if modified:
            self._save_board_order()

    def _find_task_column(self, task_id: str) -> str | None:
        """Find which column a task is currently in."""
        if self._board_order is None:
            return None
        for state, task_ids in self._board_order.columns.items():
            if task_id in task_ids:
                return state
        return None

    def _sorted_tasks(self) -> list[Task]:
        """Return tasks sorted by their board order position."""
        if self._board_order is None:
            return list(self._tasks.values())

        # Get column order from config
        config = self._get_board_config()
        column_ids = [col.id for col in config.columns] + ["archived"]

        # Build a position map for sorting
        position_map: dict[str, tuple[int, int]] = {}

        for state_idx, state in enumerate(column_ids):
            task_ids = self._board_order.columns.get(state, [])
            for pos_idx, task_id in enumerate(task_ids):
                position_map[task_id] = (state_idx, pos_idx)

        def sort_key(task: Task) -> tuple[int, int, str]:
            if task.id in position_map:
                state_idx, pos_idx = position_map[task.id]
                return (state_idx, pos_idx, task.id)
            # Tasks not in yaml go to end
            return (999, 999, task.id)

        return sorted(self._tasks.values(), key=sort_key)
