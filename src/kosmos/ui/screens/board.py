"""Main kanban board screen."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...models import TaskState
from ..widgets.column import KanbanColumn


class BoardScreen(Screen):
    """Main kanban board screen."""

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

        yield Footer()

    def on_mount(self) -> None:
        """Load tasks when screen mounts."""
        self.load_tasks()

    def load_tasks(self) -> None:
        """Load tasks from the board service and populate columns."""
        board = self.app.board_service.load_board()

        # Populate each column
        for state, tasks in board.visible_columns:
            column_id = f"column-{state.value.replace('_', '-')}"
            try:
                column = self.query_one(f"#{column_id}", KanbanColumn)
                column.set_tasks(tasks)
            except Exception:
                pass

    def refresh_board(self) -> None:
        """Refresh the board display."""
        self.app.board_service.reload()
        self.load_tasks()
