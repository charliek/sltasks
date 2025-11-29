"""Kosmos TUI Application."""

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
        # Core bindings
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        # Navigation - vim style
        Binding("h", "nav_left", "← Column", show=False),
        Binding("j", "nav_down", "↓ Task", show=False),
        Binding("k", "nav_up", "↑ Task", show=False),
        Binding("l", "nav_right", "→ Column", show=False),
        # Navigation - arrow keys
        Binding("left", "nav_left", "← Column", show=False),
        Binding("down", "nav_down", "↓ Task", show=False),
        Binding("up", "nav_up", "↑ Task", show=False),
        Binding("right", "nav_right", "→ Column", show=False),
        # Jump navigation
        Binding("g", "nav_first", "First", show=False),
        Binding("G", "nav_last", "Last", show=False),
        Binding("home", "nav_first", "First", show=False),
        Binding("end", "nav_last", "Last", show=False),
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

    # Navigation actions
    def action_nav_left(self) -> None:
        """Navigate to previous column."""
        screen = self.query_one(BoardScreen)
        screen.navigate_column(-1)

    def action_nav_right(self) -> None:
        """Navigate to next column."""
        screen = self.query_one(BoardScreen)
        screen.navigate_column(1)

    def action_nav_up(self) -> None:
        """Navigate to previous task."""
        screen = self.query_one(BoardScreen)
        screen.navigate_task(-1)

    def action_nav_down(self) -> None:
        """Navigate to next task."""
        screen = self.query_one(BoardScreen)
        screen.navigate_task(1)

    def action_nav_first(self) -> None:
        """Navigate to first task in column."""
        screen = self.query_one(BoardScreen)
        screen.navigate_to_task(0)

    def action_nav_last(self) -> None:
        """Navigate to last task in column."""
        screen = self.query_one(BoardScreen)
        screen.navigate_to_task(-1)


def run(settings: Settings | None = None) -> None:
    """Run the Kosmos application."""
    app = KosmosApp(settings)
    app.run()
