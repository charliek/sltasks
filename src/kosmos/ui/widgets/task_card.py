"""Task card widget."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ...models import Priority, Task


class TaskCard(Widget, can_focus=True):
    """A task card displayed in a column."""

    PRIORITY_DISPLAY = {
        Priority.CRITICAL: ("●", "red", "critical"),
        Priority.HIGH: ("●", "orange1", "high"),
        Priority.MEDIUM: ("●", "yellow", "medium"),
        Priority.LOW: ("●", "green", "low"),
    }

    def __init__(self, task: Task, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.task = task

    def compose(self) -> ComposeResult:
        """Create card layout."""
        # Title with truncation
        title = self._truncate(self.task.display_title, 40)
        yield Static(title, classes="task-title")

        # Priority line
        symbol, color, label = self.PRIORITY_DISPLAY.get(
            self.task.priority, ("●", "white", "medium")
        )
        priority_text = f"[{color}]{symbol}[/] {label}"
        yield Static(priority_text, classes="task-priority")

        # Tags as chips
        if self.task.tags:
            yield Static(self._format_tags(), classes="task-tags")

        # Body preview (first non-empty line)
        if self.task.body.strip():
            preview = self._get_body_preview()
            if preview:
                yield Static(preview, classes="task-preview")

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def _format_tags(self) -> str:
        """Format tags for display as chips."""
        max_tags = 3
        tags = self.task.tags[:max_tags]
        formatted = " ".join(f"[dim]#{tag}[/]" for tag in tags)

        if len(self.task.tags) > max_tags:
            extra = len(self.task.tags) - max_tags
            formatted += f" [dim]+{extra}[/]"

        return formatted

    def _get_body_preview(self) -> str:
        """Get first non-empty, non-heading line of body."""
        for line in self.task.body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                return self._truncate(line, 50)
        return ""
