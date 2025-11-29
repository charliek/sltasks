"""Kosmos TUI Application."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding

from .config import Settings
from .repositories import FilesystemRepository
from .services import BoardService, FilterService, TaskService
from .ui.screens.board import BoardScreen


class KosmosApp(App):
    """Kosmos - Terminal Kanban TUI."""

    TITLE = "Kosmos"

    CSS_PATH = "ui/styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        self._init_services()

    def _init_services(self) -> None:
        """Initialize repository and services."""
        self.repository = FilesystemRepository(self.settings.task_root)
        self.task_service = TaskService(self.repository)
        self.board_service = BoardService(self.repository)
        self.filter_service = FilterService()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield BoardScreen()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Ensure tasks directory exists
        self.repository.ensure_directory()

    def action_refresh(self) -> None:
        """Refresh the board."""
        screen = self.query_one(BoardScreen)
        screen.refresh_board()

    def action_help(self) -> None:
        """Show help (placeholder for now)."""
        self.notify("Help screen coming in a future phase!", title="Help")


def run(settings: Settings | None = None) -> None:
    """Run the Kosmos application."""
    app = KosmosApp(settings)
    app.run()
