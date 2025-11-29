"""Task preview modal with syntax-highlighted markdown."""

from rich.syntax import Syntax as RichSyntax
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from ...models import Task


class TaskPreviewModal(ModalScreen[bool]):
    """Modal for previewing task markdown with syntax highlighting.

    Returns True if user wants to edit in external editor, False otherwise.
    """

    DEFAULT_CSS = """
    TaskPreviewModal {
        align: center middle;
    }

    TaskPreviewModal > VerticalScroll {
        width: 100%;
        height: 100%;
        border: solid $primary;
        background: $surface;
        margin: 1 2;
    }

    TaskPreviewModal > VerticalScroll > #title-bar {
        height: 1;
        width: 100%;
        background: $primary-darken-2;
        color: $text;
        text-align: center;
    }

    TaskPreviewModal > VerticalScroll > #content {
        width: 100%;
        height: auto;
        padding: 0 1;
    }

    TaskPreviewModal > VerticalScroll > #footer-bar {
        height: 1;
        width: 100%;
        background: $surface-lighten-1;
        color: $text-muted;
        text-align: center;
        dock: bottom;
    }
    """

    # Only define bindings for actions we handle - let other keys dismiss
    BINDINGS = [
        Binding("e", "edit_external", "Edit", show=False),
    ]

    # Keys that should scroll content, not dismiss
    SCROLL_KEYS = {"up", "down", "pageup", "pagedown", "home", "end"}

    def __init__(self, task_data: Task) -> None:
        super().__init__()
        self._task_data = task_data

    def compose(self) -> ComposeResult:
        content = self._read_file_content()

        # Use Rich's Syntax for highlighting, displayed in a Static
        syntax = RichSyntax(
            content,
            "markdown",
            theme="github-dark",
            line_numbers=True,
            word_wrap=True,
        )

        with VerticalScroll():
            yield Static(self._task_data.display_title, id="title-bar")
            yield Static(syntax, id="content")
            yield Static("[e] Edit  [any key] Close", id="footer-bar")

    def _read_file_content(self) -> str:
        """Read the full file content including YAML front matter."""
        if self._task_data.filepath and self._task_data.filepath.exists():
            return self._task_data.filepath.read_text()
        return "(File not found)"

    def on_key(self, event) -> None:
        """Handle key events - scroll keys scroll, others dismiss."""
        if event.key in self.SCROLL_KEYS:
            # Let scroll keys bubble up to scroll the content
            return
        if event.key == "e":
            # Let the binding handle this
            return
        # Any other key dismisses the modal
        event.stop()
        self.dismiss(False)

    def action_edit_external(self) -> None:
        """Signal to open external editor."""
        self.dismiss(True)
