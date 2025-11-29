"""Main kanban board screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...models import Task, TaskState
from ...services import Filter
from ..widgets.column import KanbanColumn
from ..widgets.command_bar import CommandBar


class BoardScreen(Screen):
    """Main kanban board screen with navigation."""

    COLUMN_STATES = [TaskState.TODO, TaskState.IN_PROGRESS, TaskState.DONE]

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

    def compose(self) -> ComposeResult:
        """Create the board layout."""
        yield Header()

        with Container(id="board-container"):
            with Horizontal(id="columns"):
                yield KanbanColumn(
                    title="To Do",
                    state=TaskState.TODO,
                    id="column-todo",
                )
                yield KanbanColumn(
                    title="In Progress",
                    state=TaskState.IN_PROGRESS,
                    id="column-in-progress",
                )
                yield KanbanColumn(
                    title="Done",
                    state=TaskState.DONE,
                    id="column-done",
                )

        yield Static("", id="filter-status", classes="filter-status-bar")
        yield CommandBar()
        yield Footer()

    def on_mount(self) -> None:
        """Load tasks when screen mounts."""
        self.load_tasks()
        # Focus first task after loading
        self.call_after_refresh(self._initial_focus)

    def _initial_focus(self) -> None:
        """Set initial focus after mount."""
        self._update_focus()

    def set_filter(self, filter_: Filter | None, expression: str = "") -> None:
        """Set the active filter."""
        self._filter = filter_
        self._update_filter_status(expression)

    def load_tasks(self) -> None:
        """Load tasks from the board service and populate columns."""
        board = self.app.board_service.load_board()

        # Populate each column
        for state, tasks in board.visible_columns:
            # Apply filter if active
            if self._filter:
                tasks = self.app.filter_service.apply(tasks, self._filter)

            column_id = f"column-{state.value.replace('_', '-')}"
            try:
                column = self.query_one(f"#{column_id}", KanbanColumn)
                column.set_tasks(tasks)
            except Exception as e:
                self.log.error(f"Failed to load column {column_id}: {e}")

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

        # Reload data
        self.app.board_service.reload()
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
        for col_idx in range(len(self.COLUMN_STATES)):
            column = self._get_column(col_idx)
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
        self._current_column = self._pending_column
        column = self._get_column(self._current_column)
        if column.task_count > 0:
            self._current_task = min(self._pending_task, column.task_count - 1)
        else:
            self._current_task = 0

        self._update_focus()

    def navigate_column(self, delta: int) -> None:
        """Navigate between columns."""
        new_column = self._current_column + delta

        # Clamp to valid range
        new_column = max(0, min(new_column, len(self.COLUMN_STATES) - 1))

        if new_column != self._current_column:
            self._current_column = new_column
            # Clamp task index to new column's task count
            column = self._get_column(new_column)
            if column.task_count > 0:
                self._current_task = min(self._current_task, column.task_count - 1)
            else:
                self._current_task = 0
            self._update_focus()

    def navigate_task(self, delta: int) -> None:
        """Navigate between tasks in current column."""
        column = self._get_column(self._current_column)
        if column.task_count == 0:
            return

        new_task = self._current_task + delta
        new_task = max(0, min(new_task, column.task_count - 1))

        if new_task != self._current_task:
            self._current_task = new_task
            self._update_focus()

    def navigate_to_task(self, index: int) -> None:
        """Navigate to specific task index (-1 for last)."""
        column = self._get_column(self._current_column)
        if column.task_count == 0:
            return

        if index < 0:
            index = column.task_count - 1
        else:
            index = min(index, column.task_count - 1)

        self._current_task = index
        self._update_focus()

    def _get_column(self, index: int) -> KanbanColumn:
        """Get column widget by index."""
        state = self.COLUMN_STATES[index]
        column_id = f"column-{state.value.replace('_', '-')}"
        return self.query_one(f"#{column_id}", KanbanColumn)

    def _update_focus(self) -> None:
        """Update focus to current task."""
        column = self._get_column(self._current_column)
        column.focus_task(self._current_task)

    def get_current_task(self) -> Task | None:
        """Get the currently focused task."""
        column = self._get_column(self._current_column)
        return column.get_task(self._current_task)

    @property
    def current_column_index(self) -> int:
        """Get the current column index."""
        return self._current_column

    @property
    def current_task_index(self) -> int:
        """Get the current task index."""
        return self._current_task

    @property
    def current_column_state(self) -> TaskState:
        """Get the state of the current column."""
        return self.COLUMN_STATES[self._current_column]

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
