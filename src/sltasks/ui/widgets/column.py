"""Kanban column widget."""

import re

from textual.actions import SkipAction
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

from ...models import Task
from ...models.sync import SyncStatus
from .task_card import TaskCard


def _task_css_id(task_id: str) -> str:
    """Generate CSS-safe ID from task identifier.

    Handles various ID formats:
    - Filesystem: "fix-bug.md" -> "fix-bug"
    - Jira: "PROJ-123" -> "proj-123"
    - GitHub: "#456" or "owner/repo#456" -> "456" or "owner-repo-456"
    """
    safe_id = re.sub(r"[^a-zA-Z0-9\-]", "-", task_id)
    safe_id = safe_id.strip("-").lower()
    return safe_id or "task"


class TaskListScroll(VerticalScroll):
    """Scroll container for task lists.

    Raises SkipAction for navigation keys so they bubble up to the App
    for task navigation instead of being handled as scroll actions.
    """

    def action_scroll_up(self) -> None:
        """Skip scroll_up action to allow key to bubble."""
        raise SkipAction()

    def action_scroll_down(self) -> None:
        """Skip scroll_down action to allow key to bubble."""
        raise SkipAction()

    def action_scroll_home(self) -> None:
        """Skip scroll_home action to allow key to bubble."""
        raise SkipAction()

    def action_scroll_end(self) -> None:
        """Skip scroll_end action to allow key to bubble."""
        raise SkipAction()

    def action_page_up(self) -> None:
        """Skip page_up action to allow key to bubble."""
        raise SkipAction()

    def action_page_down(self) -> None:
        """Skip page_down action to allow key to bubble."""
        raise SkipAction()


class EmptyColumnMessage(Static):
    """Displayed when a column has no tasks."""

    pass


class KanbanColumn(Widget):
    """A single column in the kanban board."""

    def __init__(
        self,
        title: str,
        state: str,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.title = title
        self.state = state
        self._tasks: list[Task] = []
        self._sync_statuses: dict[str, SyncStatus] = {}  # task_id -> status

    @property
    def _state_css_id(self) -> str:
        """Get CSS-safe version of state for IDs."""
        return self.state.replace("_", "-")

    def compose(self) -> ComposeResult:
        """Create column layout."""
        yield Static(self._header_text, classes="column-header", id=f"header-{self._state_css_id}")
        yield TaskListScroll(classes="column-content", id=f"content-{self._state_css_id}")

    def on_mount(self) -> None:
        """Refresh tasks when column is mounted."""
        if self._tasks:
            self.call_after_refresh(self._refresh_tasks)

    @property
    def _header_text(self) -> str:
        """Header text with styled task count."""
        count = len(self._tasks)
        return f"{self.title} [dim]({count})[/]"

    def set_tasks(
        self,
        tasks: list[Task],
        sync_statuses: dict[str, SyncStatus] | None = None,
    ) -> None:
        """Set the tasks for this column.

        Args:
            tasks: List of tasks to display
            sync_statuses: Optional dict mapping task_id -> SyncStatus
        """
        self._tasks = tasks
        self._sync_statuses = sync_statuses or {}
        # Use call_after_refresh to ensure DOM is ready
        self.call_after_refresh(self._refresh_tasks)

    async def _refresh_tasks(self) -> None:
        """Refresh the task cards in this column."""
        content_id = f"#content-{self._state_css_id}"
        try:
            content = self.query_one(content_id, TaskListScroll)
        except Exception as e:
            self.log.error(f"Cannot find {content_id}: {e}")
            return

        # Remove existing task cards and wait for removal to complete
        await content.remove_children()

        # Show empty state or task cards
        if not self._tasks:
            state_name = self.state.replace("_", " ")
            await content.mount(EmptyColumnMessage(f"No {state_name} tasks"))
        else:
            # Get board config for type lookups
            board_config = None
            if hasattr(self.app, "config_service"):
                board_config = self.app.config_service.get_board_config()

            for task in self._tasks:
                # Generate CSS-safe ID from task ID
                css_id = _task_css_id(task.id)

                # Get type config if task has a type
                type_config = None
                if task.type and board_config:
                    type_config = board_config.get_type(task.type)

                # Get priority config for dynamic colors
                priority_config = None
                if board_config:
                    priority_config = board_config.get_priority(task.priority)

                # Get sync status for this task
                sync_status = self._sync_statuses.get(task.id)

                card = TaskCard(
                    task,
                    type_config=type_config,
                    priority_config=priority_config,
                    sync_status=sync_status,
                    id=f"task-{css_id}",
                )
                await content.mount(card)

        # Update header count
        try:
            header = self.query_one(f"#header-{self._state_css_id}", Static)
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
        css_id = _task_css_id(task.id)
        try:
            card = self.query_one(f"#task-{css_id}", TaskCard)
            card.focus()
            card.scroll_visible()
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
            css_id = _task_css_id(task.id)
            try:
                card = self.query_one(f"#task-{css_id}", TaskCard)
                if card.has_focus:
                    return i
            except Exception:
                pass
        return -1
