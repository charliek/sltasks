"""Command/filter bar widget."""

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Input, Static


class CommandBar(Widget):
    """Command/filter bar at the bottom of the screen."""

    DEFAULT_CSS = """
    CommandBar {
        height: 1;
        dock: bottom;
        background: $surface;
        display: none;
        layer: command;
    }

    CommandBar.-visible {
        display: block;
    }

    CommandBar .mode-indicator {
        width: auto;
        padding: 0 1;
        background: $primary;
        color: $text;
    }

    CommandBar .filter-input {
        width: 1fr;
        border: none;
        background: $surface;
    }

    CommandBar .filter-input:focus {
        border: none;
    }

    CommandBar .filter-status {
        width: auto;
        padding: 0 1;
        color: $text-muted;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._active_filter: str = ""

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Filter:", id="mode-indicator", classes="mode-indicator")
            yield Input(
                placeholder="tag:bug priority:high text...",
                id="filter-input",
                classes="filter-input",
            )
            yield Static("", id="filter-status", classes="filter-status")

    def enter_filter_mode(self) -> None:
        """Enter filter input mode."""
        self.add_class("-visible")
        input_widget = self.query_one("#filter-input", Input)
        input_widget.value = self._active_filter
        input_widget.focus()

    def exit_filter_mode(self) -> None:
        """Exit filter mode without applying."""
        self.remove_class("-visible")

    def apply_filter(self, expression: str) -> None:
        """Apply the filter expression."""
        self._active_filter = expression.strip()
        self._update_status()

    def clear_filter(self) -> None:
        """Clear the active filter."""
        self._active_filter = ""
        input_widget = self.query_one("#filter-input", Input)
        input_widget.value = ""
        self._update_status()

    def _update_status(self) -> None:
        """Update the status display."""
        status = self.query_one("#filter-status", Static)
        if self._active_filter:
            status.update(f"[dim]Active: {self._active_filter}[/]")
        else:
            status.update("")

    @property
    def active_filter(self) -> str:
        """Get the active filter expression."""
        return self._active_filter

    @property
    def is_visible(self) -> bool:
        """Check if command bar is visible."""
        return self.has_class("-visible")
