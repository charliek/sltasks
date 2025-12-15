"""Repository protocol for task storage backends."""

from typing import Protocol

from ..models import BoardOrder, Task


class RepositoryProtocol(Protocol):
    """Interface for task storage backends.

    This protocol defines the contract that all repository implementations
    must follow. It supports various backends including:
    - Filesystem (markdown files)
    - GitHub Projects
    - Jira

    For the filesystem repository, task IDs are filenames (e.g., "fix-bug.md").
    For other repositories, task IDs may be issue keys (e.g., "PROJ-123") or
    numbers (e.g., "#456").
    """

    def get_all(self) -> list[Task]:
        """Load all tasks from the backend.

        Returns:
            List of all tasks, ordered by board position within each state.
        """
        ...

    def get_by_id(self, task_id: str) -> Task | None:
        """Get a single task by ID.

        Args:
            task_id: The task identifier (e.g., "fix-bug.md", "PROJ-123")

        Returns:
            The task if found, None otherwise.
        """
        ...

    def save(self, task: Task) -> Task:
        """Create or update a task.

        Args:
            task: The task to save. If the task exists, it will be updated.

        Returns:
            The saved task (may have updated fields like filepath).
        """
        ...

    def delete(self, task_id: str) -> None:
        """Delete a task by ID.

        Args:
            task_id: The task identifier to delete.

        Note:
            Does not raise an error if the task doesn't exist.
        """
        ...

    def get_board_order(self) -> BoardOrder:
        """Get task ordering within columns.

        Returns:
            The current board order configuration.
        """
        ...

    def save_board_order(self, order: BoardOrder) -> None:
        """Save task ordering.

        Args:
            order: The board order to persist.
        """
        ...

    def reorder_task(self, task_id: str, delta: int) -> bool:
        """Reorder a task within its column.

        Handles the full reorder operation: bounds checking, swapping positions
        in the board order, and persisting the change to the backend.

        Args:
            task_id: The task to move
            delta: Position change (-1 = move up, +1 = move down)

        Returns:
            True if task was moved, False if at boundary or not found
        """
        ...

    def reload(self) -> None:
        """Clear caches and reload from source.

        Call this after external changes to ensure fresh data.
        """
        ...

    def rename_in_board_order(self, old_task_id: str, new_task_id: str) -> None:
        """Rename a task in the board order.

        This is primarily used for filesystem repositories when a task file
        is renamed to match its title.

        Args:
            old_task_id: The previous task ID
            new_task_id: The new task ID
        """
        ...

    def validate(self) -> tuple[bool, str | None]:
        """Validate provider connectivity and configuration.

        This method allows providers to verify their configuration is correct
        and they can connect to their backend (if applicable).

        Returns:
            A tuple of (is_valid, error_message).
            - (True, None) if validation passes
            - (False, "error description") if validation fails

        Examples:
            - Filesystem: Always returns (True, None)
            - GitHub: Validates token and project access
            - Jira: Validates credentials and board access
        """
        ...
