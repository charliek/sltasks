"""Push confirmation modal dialog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RadioButton, RadioSet, Static

if TYPE_CHECKING:
    from ...models import Task
    from ...models.sltasks_config import GitHubConfig


class PushConfirmModal(ModalScreen[tuple[bool, str] | None]):
    """Modal dialog for confirming push to GitHub.

    Returns:
        tuple[bool, str] | None: (confirmed, post_action) or None if cancelled.
        post_action is one of: "keep", "delete", "archive"
    """

    DEFAULT_CSS = """
    PushConfirmModal {
        align: center middle;
    }

    PushConfirmModal > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    PushConfirmModal .title {
        width: 100%;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    PushConfirmModal .details {
        width: 100%;
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
    }

    PushConfirmModal .detail-label {
        color: $text-muted;
    }

    PushConfirmModal .post-action {
        width: 100%;
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
    }

    PushConfirmModal .post-action-label {
        margin-bottom: 1;
        color: $text-muted;
    }

    PushConfirmModal RadioSet {
        width: 100%;
        height: auto;
        background: transparent;
        border: none;
    }

    PushConfirmModal RadioButton {
        background: transparent;
    }

    PushConfirmModal .buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    PushConfirmModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("enter", "confirm", "Confirm"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(
        self,
        task: Task,
        github_config: GitHubConfig | None = None,
    ) -> None:
        super().__init__()
        self._push_task = task
        self._github_config = github_config
        self._post_action = "keep"

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Push to GitHub?", classes="title")

            with Vertical(classes="details"):
                yield Static(f"[dim]Title:[/] {self._push_task.display_title}")
                if self._github_config and self._github_config.default_repo:
                    yield Static(f"[dim]Repository:[/] {self._github_config.default_repo}")
                yield Static(f"[dim]Status:[/] {self._push_task.state.replace('_', ' ')}")

            with Vertical(classes="post-action"):
                yield Label("After push:", classes="post-action-label")
                with RadioSet(id="post-action"):
                    yield RadioButton("Keep local file", id="keep", value=True)
                    yield RadioButton("Delete local file", id="delete")
                    yield RadioButton("Archive local file", id="archive")

            with Center(classes="buttons"):
                yield Button("Push", id="confirm", variant="primary")
                yield Button("Cancel", id="cancel")

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        """Handle post-action selection change."""
        if event.pressed and event.pressed.id:
            self._post_action = event.pressed.id

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss((True, self._post_action))
        else:
            self.dismiss(None)

    def action_confirm(self) -> None:
        self.dismiss((True, self._post_action))

    def action_cancel(self) -> None:
        self.dismiss(None)
