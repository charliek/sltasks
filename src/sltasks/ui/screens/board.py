"""Main kanban board screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...models import Task
from ...models.sltasks_config import BoardConfig
from ...services import Filter
from ..widgets.column import KanbanColumn
from ..widgets.command_bar import CommandBar


class BoardScreen(Screen):
    """Main kanban board screen with navigation."""

    # Layers for z-ordering (later = higher)
    LAYERS = ["base", "command"]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_column = 0
        self._current_task = 0
        self._filter: Filter | None = None
        # Pending focus state for deferred focus after refresh
        self._pending_focus_filename: str | None = None
        self._pending_column = 0
        self._pending_task = 0

    @property
    def board_config(self) -> BoardConfig:
        """Get board configuration from app."""
        return self.app.config_service.get_board_config()  # pyrefly: ignore[missing-attribute]

    @property
    def column_ids(self) -> list[str]:
        """Get list of visible column IDs in order."""
        return [col.id for col in self.board_config.columns]

    @property
    def column_count(self) -> int:
        """Number of visible columns."""
        return len(self.column_ids)

    def compose(self) -> ComposeResult:
        """Create the board layout with dynamic columns from config."""
        yield Header()

        with Container(id="board-container"), Horizontal(id="columns"):
            for col in self.board_config.columns:
                # Generate CSS-safe ID (replace underscores with hyphens)
                col_id = f"column-{col.id.replace('_', '-')}"
                yield KanbanColumn(
                    title=col.title,
                    state=col.id,
                    id=col_id,
                )

        yield Static("", id="filter-status", classes="filter-status-bar")
        yield CommandBar()
        yield Footer()

    def on_mount(self) -> None:
        """Load tasks when screen mounts."""
        self._update_bindings()
        self.load_tasks()
        # Focus first task after loading
        self.call_after_refresh(self._initial_focus)

    def _initial_focus(self) -> None:
        """Set initial focus after mount."""
        self._update_focus()

    def _update_bindings(self) -> None:
        """Update app bindings based on repository capabilities."""
        pass

    def set_filter(self, filter_: Filter | None, expression: str = "") -> None:
        """Set the active filter."""
        self._filter = filter_
        self._update_filter_status(expression)

    def load_tasks(self) -> None:
        """Load tasks from the board service and populate columns."""
        board = self.app.board_service.load_board()  # pyrefly: ignore[missing-attribute]

        # Populate each column using config
        for col_id, _title, tasks in board.get_visible_columns(self.board_config):
            # Apply filter if active
            if self._filter:
                tasks = self.app.filter_service.apply(  # pyrefly: ignore[missing-attribute]
                    tasks, self._filter
                )

            widget_id = f"column-{col_id.replace('_', '-')}"
            try:
                column = self.query_one(f"#{widget_id}", KanbanColumn)
                column.set_tasks(tasks)
            except Exception as e:
                self.log.error(f"Failed to load column {widget_id}: {e}")

    def refresh_board(self, focus_task_filename: str | None = None) -> None:
        """
        Refresh the board display.

        Args:
            focus_task_filename: If provided, focus this task after refresh.
                                If None, preserves current position.
        """
        # Save current position as fallback
        saved_column = self._current_column
        saved_task = self._current_task

        # Update bindings based on capabilities
        self._update_bindings()

        # Reload data
        self.app.board_service.reload()  # pyrefly: ignore[missing-attribute]
        self.load_tasks()

        # Store focus target for deferred application
        self._pending_focus_filename = focus_task_filename
        self._pending_column = saved_column
        self._pending_task = saved_task

        # Defer focus until after DOM is rebuilt (double-defer to ensure columns finish first)
        self.call_after_refresh(self._schedule_pending_focus)

    def _schedule_pending_focus(self) -> None:
        """Schedule the pending focus after one more refresh cycle."""
        # This ensures column _refresh_tasks has completed
        self.call_after_refresh(self._apply_pending_focus)

    def _find_task_position(self, filename: str) -> tuple[int, int] | None:
        """
        Find a task's position by filename.

        Args:
            filename: The task filename to search for

        Returns:
            (column_index, task_index) or None if not found
        """
        for col_idx in range(self.column_count):
            column = self._get_column(col_idx)
            if column is None:
                continue
            for task_idx, task in enumerate(column.tasks):
                if task.filename == filename:
                    return (col_idx, task_idx)
        return None

    def _apply_pending_focus(self) -> None:
        """Apply pending focus after refresh completes."""
        if self._pending_focus_filename:
            # Find the task by filename
            position = self._find_task_position(self._pending_focus_filename)
            if position:
                self._current_column, self._current_task = position
                self._update_focus()
                return

        # Fallback: restore previous position (clamped to valid range)
        self._current_column = min(self._pending_column, self.column_count - 1)
        column = self._get_column(self._current_column)
        if column and column.task_count > 0:
            self._current_task = min(self._pending_task, column.task_count - 1)
        else:
            self._current_task = 0

        self._update_focus()

    def navigate_column(self, delta: int) -> None:
        """Navigate between columns."""
        new_column = self._current_column + delta

        # Clamp to valid range
        new_column = max(0, min(new_column, self.column_count - 1))

        if new_column != self._current_column:
            self._current_column = new_column
            # Clamp task index to new column's task count
            column = self._get_column(new_column)
            if column and column.task_count > 0:
                self._current_task = min(self._current_task, column.task_count - 1)
            else:
                self._current_task = 0
            self._update_focus()

    def navigate_task(self, delta: int) -> None:
        """Navigate between tasks in current column."""
        column = self._get_column(self._current_column)
        if column is None or column.task_count == 0:
            return

        new_task = self._current_task + delta
        new_task = max(0, min(new_task, column.task_count - 1))

        if new_task != self._current_task:
            self._current_task = new_task
            self._update_focus()

    def navigate_to_task(self, index: int) -> None:
        """Navigate to specific task index (-1 for last)."""
        column = self._get_column(self._current_column)
        if column is None or column.task_count == 0:
            return

        index = column.task_count - 1 if index < 0 else min(index, column.task_count - 1)

        self._current_task = index
        self._update_focus()

    def _get_column(self, index: int) -> KanbanColumn | None:
        """Get column widget by index."""
        if index < 0 or index >= self.column_count:
            return None
        col_id = self.column_ids[index]
        widget_id = f"column-{col_id.replace('_', '-')}"
        try:
            return self.query_one(f"#{widget_id}", KanbanColumn)
        except Exception:
            return None

    def _update_focus(self) -> None:
        """Update focus to current task."""
        column = self._get_column(self._current_column)
        if column:
            column.focus_task(self._current_task)

    def get_current_task(self) -> Task | None:
        """Get the currently focused task."""
        column = self._get_column(self._current_column)
        if column:
            return column.get_task(self._current_task)
        return None

    @property
    def current_column_index(self) -> int:
        """Get the current column index."""
        return self._current_column

    @property
    def current_task_index(self) -> int:
        """Get the current task index."""
        return self._current_task

    @property
    def current_column_state(self) -> str:
        """Get the state of the current column."""
        if 0 <= self._current_column < self.column_count:
            return self.column_ids[self._current_column]
        return self.column_ids[0] if self.column_ids else "todo"

    def _update_filter_status(self, expression: str) -> None:
        """Update the filter status bar."""
        try:
            status = self.query_one("#filter-status", Static)
            if expression.strip():
                status.update(f"[dim]Filter:[/] {expression} [dim](Esc to clear)[/]")
                status.display = True
            else:
                status.update("")
                status.display = False
        except Exception:
            pass
