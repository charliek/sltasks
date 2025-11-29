"""Kanban column widget."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from ...models import Task, TaskState
from .task_card import TaskCard


class KanbanColumn(Widget):
    """A single column in the kanban board."""

    def __init__(
        self,
        title: str,
        state: TaskState,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.title = title
        self.state = state
        self._tasks: list[Task] = []

    def compose(self) -> ComposeResult:
        """Create column layout."""
        yield Static(self._header_text, classes="column-header", id=f"header-{self.state.value}")
        yield VerticalScroll(classes="column-content", id=f"content-{self.state.value}")

    @property
    def _header_text(self) -> str:
        """Header text with task count."""
        return f"{self.title} ({len(self._tasks)})"

    def set_tasks(self, tasks: list[Task]) -> None:
        """Set the tasks for this column."""
        self._tasks = tasks
        self._refresh_tasks()

    def _refresh_tasks(self) -> None:
        """Refresh the task cards in this column."""
        try:
            content = self.query_one(f"#content-{self.state.value}", VerticalScroll)
        except Exception:
            return

        # Remove existing task cards
        content.remove_children()

        # Add new task cards
        for task in self._tasks:
            content.mount(TaskCard(task, id=f"task-{task.filename}"))

        # Update header count
        try:
            header = self.query_one(f"#header-{self.state.value}", Static)
            header.update(self._header_text)
        except Exception:
            pass

    @property
    def tasks(self) -> list[Task]:
        """Get the tasks in this column."""
        return self._tasks

    @property
    def task_count(self) -> int:
        """Get the number of tasks in this column."""
        return len(self._tasks)
