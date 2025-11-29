"""Kanban column widget."""

from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from ...models import Task, TaskState
from .task_card import TaskCard


class EmptyColumnMessage(Static):
    """Displayed when a column has no tasks."""

    pass


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
        """Header text with styled task count."""
        count = len(self._tasks)
        return f"{self.title} [dim]({count})[/]"

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

        # Show empty state or task cards
        if not self._tasks:
            state_name = self.state.value.replace("_", " ")
            content.mount(EmptyColumnMessage(f"No {state_name} tasks"))
        else:
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

    def focus_task(self, index: int) -> bool:
        """
        Focus the task at the given index.

        Args:
            index: Task index to focus

        Returns:
            True if a task was focused, False otherwise
        """
        if not self._tasks or index < 0 or index >= len(self._tasks):
            return False

        task = self._tasks[index]
        try:
            card = self.query_one(f"#task-{task.filename}", TaskCard)
            card.focus()
            return True
        except Exception:
            return False

    def get_task(self, index: int) -> Task | None:
        """Get task at index."""
        if 0 <= index < len(self._tasks):
            return self._tasks[index]
        return None

    def get_focused_task_index(self) -> int:
        """Get index of currently focused task, or -1."""
        for i, task in enumerate(self._tasks):
            try:
                card = self.query_one(f"#task-{task.filename}", TaskCard)
                if card.has_focus:
                    return i
            except Exception:
                pass
        return -1
