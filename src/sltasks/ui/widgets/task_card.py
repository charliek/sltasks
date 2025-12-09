"""Task card widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from ...models import Priority, Task
from ...models.sltasks_config import TypeConfig


class TaskCard(Widget, can_focus=True):
    """A task card displayed in a column."""

    PRIORITY_DISPLAY = {
        Priority.CRITICAL: ("●", "red", "critical"),
        Priority.HIGH: ("●", "orange1", "high"),
        Priority.MEDIUM: ("●", "yellow", "medium"),
        Priority.LOW: ("●", "green", "low"),
    }

    def __init__(
        self,
        task_data: Task,
        type_config: TypeConfig | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._task_data = task_data
        self._type_config = type_config

    @property
    def task(self) -> Task:
        """Get the task for this card."""
        return self._task_data

    def compose(self) -> ComposeResult:
        """Create card layout."""
        # Title with truncation
        title = self._truncate(self._task_data.display_title, 40)
        yield Static(title, classes="task-title")

        # Priority and type line
        priority_text = self._format_priority()
        type_text = self._format_type()

        if type_text:
            # Show both priority and type in a horizontal layout
            with Horizontal(classes="task-meta"):
                yield Static(priority_text, classes="task-priority")
                yield Static(type_text, classes="task-type")
        else:
            # Just priority
            yield Static(priority_text, classes="task-priority")

        # Tags as chips
        if self._task_data.tags:
            yield Static(self._format_tags(), classes="task-tags")

        # Body preview (first non-empty line)
        if self._task_data.body.strip():
            preview = self._get_body_preview()
            if preview:
                yield Static(preview, classes="task-preview")

    def _format_priority(self) -> str:
        """Format priority for display."""
        symbol, color, label = self.PRIORITY_DISPLAY.get(
            self._task_data.priority, ("●", "white", "medium")
        )
        return f"[{color}]{symbol}[/] {label}"

    def _format_type(self) -> str:
        """Format type for display. Returns empty string if no type."""
        if not self._task_data.type or not self._type_config:
            return ""
        return f"[{self._type_config.color}]●[/] {self._task_data.type}"

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def _format_tags(self) -> str:
        """Format tags for display as chips."""
        max_tags = 3
        tags = self._task_data.tags[:max_tags]
        formatted = " ".join(f"[dim]#{tag}[/]" for tag in tags)

        if len(self._task_data.tags) > max_tags:
            extra = len(self._task_data.tags) - max_tags
            formatted += f" [dim]+{extra}[/]"

        return formatted

    def _get_body_preview(self) -> str:
        """Get first non-empty, non-heading line of body."""
        for line in self._task_data.body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                return self._truncate(line, 50)
        return ""
