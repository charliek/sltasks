"""Task card widget."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ...models import Priority, Task


class TaskCard(Widget, can_focus=True):
    """A task card displayed in a column."""

    PRIORITY_SYMBOLS = {
        Priority.CRITICAL: "●",
        Priority.HIGH: "●",
        Priority.MEDIUM: "●",
        Priority.LOW: "●",
    }

    def __init__(self, task: Task, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.task = task

    def compose(self) -> ComposeResult:
        """Create card layout."""
        # Title line
        yield Static(self.task.display_title, classes="task-title")

        # Meta line: priority and tags
        meta_parts: list[str] = []

        # Priority indicator
        symbol = self.PRIORITY_SYMBOLS.get(self.task.priority, "●")
        priority_class = f"priority-{self.task.priority.value}"
        meta_parts.append(f"[{self._priority_color}]{symbol}[/] {self.task.priority.value}")

        # Tags
        if self.task.tags:
            tags_str = ", ".join(self.task.tags[:3])  # Limit to 3 tags
            if len(self.task.tags) > 3:
                tags_str += "…"
            meta_parts.append(tags_str)

        yield Static(" │ ".join(meta_parts), classes="task-meta")

    @property
    def _priority_color(self) -> str:
        """Get color for priority."""
        colors = {
            Priority.CRITICAL: "red",
            Priority.HIGH: "orange1",
            Priority.MEDIUM: "yellow",
            Priority.LOW: "green",
        }
        return colors.get(self.task.priority, "white")
