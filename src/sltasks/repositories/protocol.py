"""Protocol for data repositories."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ..models import BoardOrder, Task


class RepositoryCapabilities(BaseModel):
    """Capabilities of the repository."""

    can_create: bool = True
    can_edit: bool = True
    can_delete: bool = True
    can_move_column: bool = True  # Can change status/column
    can_reorder: bool = True  # Can reorder within column
    can_archive: bool = True


@runtime_checkable
class RepositoryProtocol(Protocol):
    """Protocol for task storage repositories."""

    @property
    def capabilities(self) -> RepositoryCapabilities:
        """Get repository capabilities."""
        ...

    def ensure_directory(self) -> None:
        """Prepare storage (e.g. create dirs)."""
        ...

    def get_all(self) -> list[Task]:
        """Get all tasks."""
        ...

    def get_by_id(self, filename: str) -> Task | None:
        """Get a single task by ID (filename)."""
        ...

    def save(self, task: Task) -> Task:
        """Save a task."""
        ...

    def delete(self, filename: str) -> None:
        """Delete a task."""
        ...

    def get_board_order(self) -> BoardOrder:
        """Get the board order."""
        ...

    def save_board_order(self, order: BoardOrder) -> None:
        """Save the board order."""
        ...

    def rename_in_board_order(self, old_filename: str, new_filename: str) -> None:
        """Rename a task in the board order."""
        ...

    def reload(self) -> None:
        """Reload data from source."""
        ...
