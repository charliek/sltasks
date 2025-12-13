"""Service for board state management."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import Board, BoardOrder, Task
from ..models.sltasks_config import BoardConfig
from ..models.task import STATE_ARCHIVED
from ..repositories.protocol import RepositoryProtocol
from ..utils import now_utc

if TYPE_CHECKING:
    from .config_service import ConfigService


class BoardService:
    """Service for board state management."""

    def __init__(
        self,
        repository: RepositoryProtocol,
        config_service: ConfigService | None = None,
    ) -> None:
        self.repository = repository
        self._config_service = config_service

    def _get_board_config(self) -> BoardConfig:
        """Get board config, using default if no config service."""
        if self._config_service:
            return self._config_service.get_board_config()
        return BoardConfig.default()

    def load_board(self) -> Board:
        """Load the full board with all tasks grouped by state."""
        tasks = self.repository.get_all()
        config = self._get_board_config()
        return Board.from_tasks(tasks, config)

    def get_tasks_by_state(self, state: str) -> list[Task]:
        """Get all tasks in a specific state."""
        tasks = self.repository.get_all()
        return [t for t in tasks if t.state == state]

    def move_task(self, filename: str, to_state: str) -> Task | None:
        """
        Move a task to a different state/column.

        Updates both the task file and the board order.
        """
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        # Resolve alias to canonical ID
        config = self._get_board_config()
        canonical_state = config.resolve_status(to_state)

        task.state = canonical_state
        task.updated = now_utc()

        # Save updates the file and yaml
        self.repository.save(task)

        return task

    def move_task_left(self, filename: str) -> Task | None:
        """Move task to the previous column (e.g., in_progress -> todo)."""
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        new_state = self._previous_state(task.state)
        if new_state is None:
            return task  # Already at leftmost column

        return self.move_task(filename, new_state)

    def move_task_right(self, filename: str) -> Task | None:
        """Move task to the next column (e.g., todo -> in_progress)."""
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        new_state = self._next_state(task.state)
        if new_state is None:
            return task  # Already at rightmost column

        return self.move_task(filename, new_state)

    def archive_task(self, filename: str) -> Task | None:
        """Move a task to the archived state."""
        return self.move_task(filename, STATE_ARCHIVED)

    def unarchive_task(self, filename: str) -> Task | None:
        """Move an archived task to the first column."""
        task = self.repository.get_by_id(filename)
        if task is None or task.state != STATE_ARCHIVED:
            return None

        config = self._get_board_config()
        first_column = config.columns[0].id
        return self.move_task(filename, first_column)

    def get_board_order(self) -> BoardOrder:
        """Get the current board order."""
        return self.repository.get_board_order()

    def save_board_order(self, order: BoardOrder) -> None:
        """Save the board order."""
        self.repository.save_board_order(order)

    def reorder_task(self, filename: str, delta: int) -> bool:
        """
        Reorder task within its column.

        Args:
            filename: Task filename to reorder
            delta: -1 to move up, 1 to move down

        Returns:
            True if task was moved
        """
        task = self.repository.get_by_id(filename)
        if task is None:
            return False

        board_order = self.repository.get_board_order()
        column = board_order.columns.get(task.state, [])

        if filename not in column:
            return False

        current_idx = column.index(filename)
        new_idx = current_idx + delta

        # Check bounds
        if new_idx < 0 or new_idx >= len(column):
            return False

        # Swap positions
        column[current_idx], column[new_idx] = column[new_idx], column[current_idx]

        # Save updated order
        self.repository.save_board_order(board_order)
        return True

    def reload(self) -> None:
        """Reload board state from filesystem."""
        self.repository.reload()

    def _previous_state(self, state: str) -> str | None:
        """Get the previous state in the workflow."""
        config = self._get_board_config()
        column_ids = [col.id for col in config.columns]
        try:
            idx = column_ids.index(state)
            if idx > 0:
                return column_ids[idx - 1]
        except ValueError:
            pass
        return None

    def _next_state(self, state: str) -> str | None:
        """Get the next state in the workflow."""
        config = self._get_board_config()
        column_ids = [col.id for col in config.columns]
        try:
            idx = column_ids.index(state)
            if idx < len(column_ids) - 1:
                return column_ids[idx + 1]
        except ValueError:
            pass
        return None
