"""Sync management screen."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, ScrollableContainer, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

if TYPE_CHECKING:
    from ...models.sync import ChangeSet
    from ...sync.engine import GitHubSyncEngine

logger = logging.getLogger(__name__)


class SyncScreen(ModalScreen):
    """Modal screen for managing GitHub sync operations.

    Shows sections for:
    - Changes to pull from GitHub
    - Changes to push to GitHub
    - Conflicts requiring resolution
    """

    DEFAULT_CSS = """
    SyncScreen {
        align: center middle;
    }

    SyncScreen > Vertical {
        width: 80;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    SyncScreen .sync-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary-darken-2;
    }

    SyncScreen .sync-content {
        height: auto;
        max-height: 60;
        padding: 1 0;
    }

    SyncScreen .sync-section {
        height: auto;
        padding: 0 0 1 0;
    }

    SyncScreen .section-header {
        text-style: bold;
        padding-bottom: 1;
    }

    SyncScreen .section-header-pull {
        color: $success;
    }

    SyncScreen .section-header-push {
        color: $warning;
    }

    SyncScreen .section-header-conflict {
        color: $error;
    }

    SyncScreen .sync-item {
        height: 1;
        padding-left: 2;
    }

    SyncScreen .item-checkbox {
        width: 4;
    }

    SyncScreen .item-label {
        width: 1fr;
    }

    SyncScreen .item-badge {
        width: auto;
        margin-left: 1;
    }

    SyncScreen .badge-remote {
        color: $success;
    }

    SyncScreen .badge-local {
        color: $warning;
    }

    SyncScreen .badge-conflict {
        color: $error;
    }

    SyncScreen .conflict-detail {
        padding-left: 4;
        color: $text-muted;
        height: auto;
    }

    SyncScreen .empty-message {
        color: $text-muted;
        padding-left: 2;
    }

    SyncScreen .sync-footer {
        text-align: center;
        padding-top: 1;
        border-top: solid $primary-darken-2;
    }

    SyncScreen .footer-buttons {
        align: center middle;
        height: auto;
        padding-top: 1;
    }

    SyncScreen Button {
        margin: 0 1;
    }

    SyncScreen .keybinding-hint {
        color: $text-muted;
        text-align: center;
        padding-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
        Binding("P", "pull", "Pull", show=True),
        Binding("U", "push", "Push", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self, sync_engine: GitHubSyncEngine) -> None:
        super().__init__()
        self._sync_engine = sync_engine
        self._changes: ChangeSet | None = None
        self._push_selections: set[str] = set()
        self._loading = True

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Sync Status", classes="sync-title")

            with ScrollableContainer(classes="sync-content"):
                # Pull section
                with Vertical(classes="sync-section", id="pull-section"):
                    yield Static(
                        "Pull from GitHub (0 changes)",
                        classes="section-header section-header-pull",
                        id="pull-header",
                    )
                    yield Static("Loading...", classes="empty-message", id="pull-items")

                # Push section
                with Vertical(classes="sync-section", id="push-section"):
                    yield Static(
                        "Push to GitHub (0 changes)",
                        classes="section-header section-header-push",
                        id="push-header",
                    )
                    yield Static("Loading...", classes="empty-message", id="push-items")

                # Conflicts section
                with Vertical(classes="sync-section", id="conflict-section"):
                    yield Static(
                        "Conflicts (0)",
                        classes="section-header section-header-conflict",
                        id="conflict-header",
                    )
                    yield Static("Loading...", classes="empty-message", id="conflict-items")

            with Vertical(classes="sync-footer"):
                with Horizontal(classes="footer-buttons"):
                    yield Button("Pull All", id="btn-pull", variant="success")
                    yield Button("Push Selected", id="btn-push", variant="warning")
                    yield Button("Refresh", id="btn-refresh")
                    yield Button("Close", id="btn-close")

                yield Static(
                    "[P] Pull  [U] Push  [r] Refresh  [ESC] Close",
                    classes="keybinding-hint",
                )

    def on_mount(self) -> None:
        """Load sync data when screen mounts."""
        self._refresh_changes()

    def _refresh_changes(self) -> None:
        """Refresh the change detection."""
        self._loading = True
        try:
            self._changes = self._sync_engine.detect_changes()
            self._loading = False
            self._update_display()
        except Exception as e:
            logger.error("Failed to detect changes: %s", e)
            self._loading = False
            self.app.notify(f"Failed to detect changes: {e}", severity="error", timeout=5)

    def _update_display(self) -> None:
        """Update the display with current changes."""
        if not self._changes:
            return

        # Update pull section
        pull_header = self.query_one("#pull-header", Static)
        pull_items = self.query_one("#pull-items", Static)
        pull_count = len(self._changes.to_pull)
        pull_header.update(f"Pull from GitHub ({pull_count} changes)")

        if pull_count == 0:
            pull_items.update("[dim]No changes to pull[/]")
        else:
            lines: list[str] = []
            for task_id in self._changes.to_pull:
                # Show badge based on whether this is an existing or new issue
                if "#" in task_id:
                    lines.append(f"  [green]●[/] {task_id} [dim][remote][/]")
                else:
                    lines.append(f"  [green]●[/] {task_id} [dim][new][/]")
            pull_items.update("\n".join(lines))

        # Update push section
        push_header = self.query_one("#push-header", Static)
        push_items = self.query_one("#push-items", Static)
        push_count = len(self._changes.to_push)
        push_header.update(f"Push to GitHub ({push_count} changes)")

        if push_count == 0:
            push_items.update("[dim]No changes to push[/]")
            self._push_selections.clear()
        else:
            lines: list[str] = []
            for task_id in self._changes.to_push:
                # Determine badge based on whether it's local-only or modified
                if "#" not in task_id:
                    badge = "[dim][local only][/]"
                    symbol = "○"
                else:
                    badge = "[dim][local mod][/]"
                    symbol = "●"
                selected = "✓" if task_id in self._push_selections else " "
                lines.append(f"  [{selected}] [yellow]{symbol}[/] {task_id} {badge}")
            push_items.update("\n".join(lines))

        # Update conflicts section
        conflict_header = self.query_one("#conflict-header", Static)
        conflict_items = self.query_one("#conflict-items", Static)
        conflict_count = len(self._changes.conflicts)
        conflict_header.update(f"Conflicts ({conflict_count})")

        if conflict_count == 0:
            conflict_items.update("[dim]No conflicts[/]")
        else:
            lines: list[str] = []
            for conflict in self._changes.conflicts:
                lines.append(f"  [red]⚠[/] {conflict.task_id}")
                local_time = conflict.local_updated.strftime("%Y-%m-%d %H:%M")
                remote_time = conflict.remote_updated.strftime("%Y-%m-%d %H:%M")
                lines.append(f"    [dim]Local: {local_time}  GitHub: {remote_time}[/]")
                lines.append("    [dim]Pull will overwrite local changes - backup first![/]")
            conflict_items.update("\n".join(lines))

        # Update button states
        btn_pull = self.query_one("#btn-pull", Button)
        btn_push = self.query_one("#btn-push", Button)

        btn_pull.disabled = pull_count == 0 and conflict_count == 0
        btn_push.disabled = push_count == 0

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "btn-pull":
            self.action_pull()
        elif event.button.id == "btn-push":
            self.action_push()
        elif event.button.id == "btn-refresh":
            self.action_refresh()
        elif event.button.id == "btn-close":
            self.dismiss()

    def action_pull(self) -> None:
        """Pull all changes from GitHub."""
        if not self._changes:
            return

        pull_count = len(self._changes.to_pull)
        conflict_count = len(self._changes.conflicts)

        if pull_count == 0 and conflict_count == 0:
            self.app.notify("Nothing to pull", timeout=2)
            return

        # Confirm if there are conflicts
        if conflict_count > 0:
            # For now, just warn - in future could add confirmation dialog
            self.app.notify(
                f"Pulling {pull_count + conflict_count} changes (including {conflict_count} conflicts)",
                severity="warning",
                timeout=3,
            )

        try:
            # Use force=True if conflicts exist, to overwrite local changes
            force = conflict_count > 0
            result = self._sync_engine.sync_from_github(force=force)

            if result.has_errors:
                self.app.notify(
                    f"Pull completed with errors: {result.errors[0]}",
                    severity="error",
                    timeout=5,
                )
            else:
                self.app.notify(
                    f"Pulled {result.pulled} changes",
                    severity="information",
                    timeout=2,
                )

            # Refresh the display
            self._refresh_changes()

            # Refresh app sync statuses
            self.app.refresh_sync_statuses()  # pyrefly: ignore[missing-attribute]

        except Exception as e:
            logger.error("Pull failed: %s", e)
            self.app.notify(f"Pull failed: {e}", severity="error", timeout=5)

    def action_push(self) -> None:
        """Push selected changes to GitHub."""
        if not self._changes:
            return

        # If nothing selected, push all
        to_push = list(self._push_selections) if self._push_selections else self._changes.to_push

        if not to_push:
            self.app.notify("Nothing to push", timeout=2)
            return

        try:
            # Separate local-only from modified synced files
            local_only_ids = [t for t in to_push if "#" not in t]
            modified_ids = [t for t in to_push if "#" in t]

            pushed = 0
            errors = []

            # Push local-only as new issues
            if local_only_ids:
                # Find the actual Task objects
                tasks = self._sync_engine.find_local_only_tasks()
                tasks_to_push = [t for t in tasks if t.id in local_only_ids]

                if tasks_to_push:
                    result = self._sync_engine.push_new_issues(tasks_to_push)
                    pushed += result.success_count
                    errors.extend(result.errors)

            # Push modified synced files
            if modified_ids:
                tasks = self._sync_engine.find_modified_synced_tasks()
                tasks_to_push = [t for t in tasks if t.id in modified_ids]

                if tasks_to_push:
                    result = self._sync_engine.push_updates(tasks_to_push)
                    pushed += result.success_count
                    errors.extend(result.errors)

            if errors:
                self.app.notify(
                    f"Pushed {pushed} with {len(errors)} errors: {errors[0]}",
                    severity="error",
                    timeout=5,
                )
            else:
                self.app.notify(f"Pushed {pushed} changes", timeout=2)

            # Clear selections and refresh
            self._push_selections.clear()
            self._refresh_changes()

            # Refresh app sync statuses
            self.app.refresh_sync_statuses()  # pyrefly: ignore[missing-attribute]

        except Exception as e:
            logger.error("Push failed: %s", e)
            self.app.notify(f"Push failed: {e}", severity="error", timeout=5)

    def action_refresh(self) -> None:
        """Refresh change detection."""
        self.app.notify("Refreshing...", timeout=1)
        self._refresh_changes()
        self.app.refresh_sync_statuses()  # pyrefly: ignore[missing-attribute]
        self.app.notify("Refresh complete", timeout=1)
