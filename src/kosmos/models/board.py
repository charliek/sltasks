"""Board state models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from .task import (
    STATE_ARCHIVED,
    STATE_DONE,
    STATE_IN_PROGRESS,
    STATE_TODO,
    Task,
)

if TYPE_CHECKING:
    from .sltasks_config import BoardConfig


class BoardOrder(BaseModel):
    """Represents the ordering of tasks in tasks.yaml."""

    version: int = 1
    columns: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def default(cls) -> BoardOrder:
        """Create default BoardOrder with standard 3 columns + archived."""
        return cls(
            columns={
                "todo": [],
                "in_progress": [],
                "done": [],
                "archived": [],
            }
        )

    @classmethod
    def from_config(cls, config: BoardConfig) -> BoardOrder:
        """Create BoardOrder with columns from config."""
        columns: dict[str, list[str]] = {}
        for col in config.columns:
            columns[col.id] = []
        columns["archived"] = []
        return cls(columns=columns)

    def ensure_column(self, column_id: str) -> None:
        """Ensure a column exists in the order."""
        if column_id not in self.columns:
            self.columns[column_id] = []

    def get_position(self, filename: str, state: str) -> int:
        """Get position of task in its column, or -1 if not found."""
        column = self.columns.get(state, [])
        try:
            return column.index(filename)
        except ValueError:
            return -1

    def add_task(self, filename: str, state: str, position: int = -1) -> None:
        """Add task to column at position (-1 = end)."""
        self.ensure_column(state)

        # Remove from any existing column first
        self.remove_task(filename)

        if position < 0:
            self.columns[state].append(filename)
        else:
            self.columns[state].insert(position, filename)

    def remove_task(self, filename: str) -> None:
        """Remove task from all columns."""
        for column in self.columns.values():
            if filename in column:
                column.remove(filename)

    def move_task(
        self, filename: str, from_state: str, to_state: str, position: int = -1
    ) -> None:
        """Move task between columns."""
        self.remove_task(filename)
        self.add_task(filename, to_state, position)


class Board(BaseModel):
    """Full board state with tasks grouped by column."""

    # Dynamic columns storage
    columns: dict[str, list[Task]] = Field(default_factory=dict)

    # Store config for visible_columns method
    _config: BoardConfig | None = None

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_tasks(
        cls, tasks: list[Task], config: BoardConfig | None = None
    ) -> Board:
        """
        Create Board from tasks, grouping by state.

        Args:
            tasks: List of tasks to group
            config: Board configuration for column definitions.
                    If None, uses default 3-column config.
        """
        # Import here to avoid circular import
        from .sltasks_config import BoardConfig as BC

        if config is None:
            config = BC.default()

        board = cls()
        board._config = config

        # Initialize all columns from config
        for col in config.columns:
            board.columns[col.id] = []

        # Always have archived column
        board.columns[STATE_ARCHIVED] = []

        # Sort tasks into columns
        for task in tasks:
            if task.state in board.columns:
                board.columns[task.state].append(task)
            elif task.state == STATE_ARCHIVED:
                board.columns[STATE_ARCHIVED].append(task)
            else:
                # Unknown state - place in first column
                first_col = config.columns[0].id
                board.columns[first_col].append(task)

        return board

    def get_column(self, column_id: str) -> list[Task]:
        """Get tasks for a specific column."""
        return self.columns.get(column_id, [])

    def get_visible_columns(
        self, config: BoardConfig | None = None
    ) -> list[tuple[str, str, list[Task]]]:
        """
        Get visible columns (excludes archived) with their config.

        Returns:
            List of (column_id, title, tasks) tuples in display order.
        """
        # Import here to avoid circular import
        from .sltasks_config import BoardConfig as BC

        if config is None:
            config = self._config or BC.default()

        return [
            (col.id, col.title, self.columns.get(col.id, []))
            for col in config.columns
        ]

    # Backwards compatibility properties
    @property
    def todo(self) -> list[Task]:
        """Backwards compatibility - get 'todo' column."""
        return self.columns.get(STATE_TODO, [])

    @property
    def in_progress(self) -> list[Task]:
        """Backwards compatibility - get 'in_progress' column."""
        return self.columns.get(STATE_IN_PROGRESS, [])

    @property
    def done(self) -> list[Task]:
        """Backwards compatibility - get 'done' column."""
        return self.columns.get(STATE_DONE, [])

    @property
    def archived(self) -> list[Task]:
        """Backwards compatibility - get 'archived' column."""
        return self.columns.get(STATE_ARCHIVED, [])
