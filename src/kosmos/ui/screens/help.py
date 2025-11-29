"""Help screen showing keyboard shortcuts."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class HelpScreen(ModalScreen):
    """Modal help screen showing keyboard shortcuts."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 90%;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    HelpScreen .help-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary-darken-2;
    }

    HelpScreen .help-section {
        padding: 1 0 0 0;
    }

    HelpScreen .section-title {
        text-style: bold;
        color: $primary;
    }

    HelpScreen .help-row {
        height: 1;
    }

    HelpScreen .help-key {
        width: 15;
        text-style: bold;
    }

    HelpScreen .help-desc {
        width: 1fr;
        color: $text-muted;
    }

    HelpScreen .help-footer {
        text-align: center;
        color: $text-muted;
        padding-top: 1;
        border-top: solid $primary-darken-2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("?", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Keyboard Shortcuts", classes="help-title")

            # Navigation section
            with Vertical(classes="help-section"):
                yield Static("Navigation", classes="section-title")
                yield self._help_row("h / Left", "Previous column")
                yield self._help_row("l / Right", "Next column")
                yield self._help_row("k / Up", "Previous task")
                yield self._help_row("j / Down", "Next task")
                yield self._help_row("g / Home", "First task in column")
                yield self._help_row("G / End", "Last task in column")

            # Actions section
            with Vertical(classes="help-section"):
                yield Static("Actions", classes="section-title")
                yield self._help_row("n", "Create new task")
                yield self._help_row("e / Enter", "Edit current task")
                yield self._help_row("H / Shift+Left", "Move task left")
                yield self._help_row("L / Shift+Right", "Move task right")
                yield self._help_row("K / Shift+Up", "Move task up")
                yield self._help_row("J / Shift+Down", "Move task down")
                yield self._help_row("Space", "Toggle task state")
                yield self._help_row("a", "Archive task")
                yield self._help_row("d", "Delete task")

            # Filter section
            with Vertical(classes="help-section"):
                yield Static("Filter", classes="section-title")
                yield self._help_row("/", "Enter filter mode")
                yield self._help_row("Escape", "Clear filter / Cancel")

            # Filter syntax section
            with Vertical(classes="help-section"):
                yield Static("Filter Syntax", classes="section-title")
                yield self._help_row("text", "Search in title/body")
                yield self._help_row("tag:name", "Filter by tag")
                yield self._help_row("-tag:name", "Exclude tag")
                yield self._help_row("state:todo", "Filter by state")
                yield self._help_row("priority:high", "Filter by priority")

            # General section
            with Vertical(classes="help-section"):
                yield Static("General", classes="section-title")
                yield self._help_row("r", "Refresh board")
                yield self._help_row("?", "Show this help")
                yield self._help_row("q", "Quit")

            yield Static("Press any key to close", classes="help-footer")

    def _help_row(self, key: str, description: str) -> Horizontal:
        """Create a help row with key and description."""
        row = Horizontal(classes="help-row")
        row.compose_add_child(Static(key, classes="help-key"))
        row.compose_add_child(Static(description, classes="help-desc"))
        return row

    def on_key(self, event) -> None:
        """Dismiss on any key press and prevent propagation."""
        event.stop()
        self.dismiss()
