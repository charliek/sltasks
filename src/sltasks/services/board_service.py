"""Service for board state management."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..models import Board, BoardOrder, Task
from ..models.sltasks_config import BoardConfig
from ..models.task import STATE_ARCHIVED
from ..repositories import RepositoryProtocol
from ..utils import now_utc

if TYPE_CHECKING:
    from .config_service import ConfigService

logger = logging.getLogger(__name__)


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

    def move_task(self, task_id: str, to_state: str) -> Task | None:
        """
        Move a task to a different state/column.

        Updates both the task file and the board order.
        """
        task = self.repository.get_by_id(task_id)
        if task is None:
            logger.debug("move_task: task not found: %s", task_id)
            return None

        old_state = task.state

        # Resolve alias to canonical ID
        config = self._get_board_config()
        canonical_state = config.resolve_status(to_state)

        task.state = canonical_state
        task.updated = now_utc()

        # Save updates the file and yaml
        self.repository.save(task)

        logger.info("Task moved: %s (%s -> %s)", task_id, old_state, canonical_state)
        return task

    def move_task_left(self, task_id: str) -> Task | None:
        """Move task to the previous column (e.g., in_progress -> todo)."""
        task = self.repository.get_by_id(task_id)
        if task is None:
            return None

        new_state = self._previous_state(task.state)
        if new_state is None:
            return task  # Already at leftmost column

        return self.move_task(task_id, new_state)

    def move_task_right(self, task_id: str) -> Task | None:
        """Move task to the next column (e.g., todo -> in_progress)."""
        task = self.repository.get_by_id(task_id)
        if task is None:
            return None

        new_state = self._next_state(task.state)
        if new_state is None:
            return task  # Already at rightmost column

        return self.move_task(task_id, new_state)

    def archive_task(self, task_id: str) -> Task | None:
        """Move a task to the archived state."""
        logger.info("Archiving task: %s", task_id)
        return self.move_task(task_id, STATE_ARCHIVED)

    def unarchive_task(self, task_id: str) -> Task | None:
        """Move an archived task to the first column."""
        task = self.repository.get_by_id(task_id)
        if task is None or task.state != STATE_ARCHIVED:
            logger.debug("unarchive_task: task not found or not archived: %s", task_id)
            return None

        config = self._get_board_config()
        first_column = config.columns[0].id
        logger.info("Unarchiving task: %s -> %s", task_id, first_column)
        return self.move_task(task_id, first_column)

    def get_board_order(self) -> BoardOrder:
        """Get the current board order."""
        return self.repository.get_board_order()

    def save_board_order(self, order: BoardOrder) -> None:
        """Save the board order."""
        self.repository.save_board_order(order)

    def reorder_task(self, task_id: str, delta: int) -> bool:
        """
        Reorder task within its column.

        Args:
            task_id: Task ID to reorder
            delta: -1 to move up, 1 to move down

        Returns:
            True if task was moved
        """
        task = self.repository.get_by_id(task_id)
        if task is None:
            logger.debug("reorder_task: task not found: %s", task_id)
            return False

        board_order = self.repository.get_board_order()
        column = board_order.columns.get(task.state, [])

        if task_id not in column:
            logger.debug("reorder_task: task not in column order: %s", task_id)
            return False

        current_idx = column.index(task_id)
        new_idx = current_idx + delta

        # Check bounds
        if new_idx < 0 or new_idx >= len(column):
            logger.debug("reorder_task: at boundary, cannot move: %s", task_id)
            return False

        # Swap positions
        column[current_idx], column[new_idx] = column[new_idx], column[current_idx]

        # Save updated order
        self.repository.save_board_order(board_order)
        direction = "up" if delta < 0 else "down"
        logger.debug(
            "Task reordered %s: %s (pos %d -> %d)", direction, task_id, current_idx, new_idx
        )
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
