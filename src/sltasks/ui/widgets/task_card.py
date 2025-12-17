"""Task card widget."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Static

from ...models import Task
from ...models.sltasks_config import PriorityConfig, TypeConfig
from ...models.sync import SyncStatus


class TaskCard(Widget, can_focus=True):
    """A task card displayed in a column."""

    # Sync status display mapping: (symbol, color)
    SYNC_STATUS_DISPLAY: dict[SyncStatus, tuple[str, str]] = {
        SyncStatus.SYNCED: ("●", "green"),
        SyncStatus.LOCAL_MODIFIED: ("●", "yellow"),
        SyncStatus.REMOTE_MODIFIED: ("●", "blue"),
        SyncStatus.CONFLICT: ("⚠", "red"),
        SyncStatus.LOCAL_ONLY: ("○", "dim"),
    }

    def __init__(
        self,
        task_data: Task,
        type_config: TypeConfig | None = None,
        priority_config: PriorityConfig | None = None,
        sync_status: SyncStatus | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._task_data = task_data
        self._type_config = type_config
        self._priority_config = priority_config
        self._sync_status = sync_status

    @property
    def task(self) -> Task:  # pyrefly: ignore[bad-override]
        """Get the task for this card."""
        return self._task_data

    def compose(self) -> ComposeResult:
        """Create card layout."""
        # Title with truncation
        title = self._truncate(self._task_data.display_title, 40)
        yield Static(title, classes="task-title")

        # Priority and type line (with optional sync indicator)
        priority_text = self._format_priority()
        type_text = self._format_type()
        sync_text = self._format_sync_indicator()

        if type_text or sync_text:
            # Show priority, type, and sync indicator in a horizontal layout
            with Horizontal(classes="task-meta"):
                yield Static(priority_text, classes="task-priority")
                if type_text:
                    yield Static(type_text, classes="task-type")
                if sync_text:
                    yield Static(sync_text, classes="sync-indicator")
        else:
            # Just priority
            yield Static(priority_text, classes="task-priority")

        # Tags as chips
        if self._task_data.tags:
            yield Static(self._format_tags(), classes="task-tags")

        # Show assignee if present, otherwise body preview
        assignee = self._get_first_assignee()
        if assignee:
            yield Static(f"@{assignee}", classes="task-assignee")
        elif self._task_data.body.strip():
            preview = self._get_body_preview()
            if preview:
                yield Static(preview, classes="task-preview")

    def _format_priority(self) -> str:
        """Format priority for display using config."""
        # Handle None/unset priority
        if self._task_data.priority is None:
            return "[dim]—[/]"

        if self._priority_config:
            # Use configured color, symbol, and label
            color = self._priority_config.color
            symbol = self._priority_config.symbol
            label = self._priority_config.label
        else:
            # Fallback for unknown priorities
            color = "white"
            symbol = "●"
            label = self._task_data.priority
        return f"[{color}]{symbol}[/] {label}"

    def _format_type(self) -> str:
        """Format type for display. Returns empty string if no type."""
        if not self._task_data.type or not self._type_config:
            return ""
        return f"[{self._type_config.color}]●[/] {self._task_data.type}"

    def _format_sync_indicator(self) -> str:
        """Format sync status indicator. Returns empty string if no sync status."""
        if self._sync_status is None:
            return ""
        display = self.SYNC_STATUS_DISPLAY.get(self._sync_status)
        if not display:
            return ""
        symbol, color = display
        return f"[{color}]{symbol}[/]"

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

    def _get_first_assignee(self) -> str | None:
        """Get first assignee username if any."""
        if self._task_data.assignees:
            return self._task_data.assignees[0]
        return None
