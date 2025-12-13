"""sltasks TUI Application."""

from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen

from .config import Settings
from .repositories import FilesystemRepository
from .repositories.github import GitHubRepository
from .repositories.protocol import RepositoryProtocol
from .services import (
    BoardService,
    ConfigService,
    FilterService,
    TaskService,
    TemplateService,
)
from .ui.screens.board import BoardScreen
from .ui.widgets import (
    CommandBar,
    ConfirmModal,
    HelpScreen,
    TaskPreviewModal,
    TypeSelectorModal,
)


class SltasksApp(App):
    """sltasks - Terminal Kanban TUI."""

    TITLE = "sltasks"

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
        # Task actions
        Binding("n", "new_task", "New", show=True),
        Binding("e", "edit_task", "Edit", show=True),
        Binding("enter", "preview_task", "Preview", show=False),
        Binding("H", "move_task_left", "Move ←", show=False),
        Binding("L", "move_task_right", "Move →", show=False),
        Binding("shift+left", "move_task_left", "Move ←", show=False),
        Binding("shift+right", "move_task_right", "Move →", show=False),
        Binding("K", "move_task_up", "Move ↑", show=False),
        Binding("J", "move_task_down", "Move ↓", show=False),
        Binding("shift+up", "move_task_up", "Move ↑", show=False),
        Binding("shift+down", "move_task_down", "Move ↓", show=False),
        Binding("a", "archive_task", "Archive", show=True),
        Binding("d", "delete_task", "Delete", show=False),
        Binding("space", "toggle_state", "Toggle", show=False),
        # Filter mode
        Binding("/", "enter_filter", "Filter", show=True),
        Binding("escape", "escape", "Back", show=False, priority=True),
    ]

    SCREENS = {
        "board": BoardScreen,
    }

    def __init__(self, settings: Settings | None = None) -> None:
        super().__init__()
        self.settings = settings or Settings()
        self._init_services()

    def _init_services(self) -> None:
        """Initialize repository and services."""
        self.config_service = ConfigService(self.settings.project_root)

        config = self.config_service.get_config()
        if config.backend == "github" and config.github:
            self.repository: RepositoryProtocol = GitHubRepository(config.github, self.config_service)
        else:
            # Get task_root from config service (computed from project_root + config.task_root)
            task_root = self.config_service.task_root
            self.repository: RepositoryProtocol = FilesystemRepository(task_root, self.config_service)

        self.template_service = TemplateService(self.config_service)
        self.task_service = TaskService(self.repository, self.config_service, self.template_service)
        self.board_service = BoardService(self.repository, self.config_service)
        self.filter_service = FilterService()

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Ensure tasks directory exists
        self.repository.ensure_directory()
        # Push the board screen
        self.push_screen("board")

    def action_refresh(self) -> None:
        """Refresh the board."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.refresh_board()

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())

    # Navigation actions
    def action_nav_left(self) -> None:
        """Navigate to previous column."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.navigate_column(-1)

    def action_nav_right(self) -> None:
        """Navigate to next column."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.navigate_column(1)

    def action_nav_up(self) -> None:
        """Navigate to previous task."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.navigate_task(-1)

    def action_nav_down(self) -> None:
        """Navigate to next task."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.navigate_task(1)

    def action_nav_first(self) -> None:
        """Navigate to first task in column."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.navigate_to_task(0)

    def action_nav_last(self) -> None:
        """Navigate to last task in column."""
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.navigate_to_task(-1)

    # Task actions
    def action_new_task(self) -> None:
        """Create a new task - shows type selector if types configured."""
        if not self.repository.capabilities.can_create:
            self.notify("Creation not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        # Check if types are configured
        config = self.config_service.get_board_config()
        if config.types:
            # Show type selector modal
            self.push_screen(
                TypeSelectorModal(config.types),
                callback=self._handle_type_selection,
            )
        else:
            # No types configured - create task directly
            self._create_task_with_type(None)

    def _handle_type_selection(self, selected_type: str | None) -> None:
        """Handle type selection from modal."""
        # Create task with selected type (None if user cancelled or chose no type)
        self._create_task_with_type(selected_type)

    def _create_task_with_type(self, task_type: str | None) -> None:
        """Create task with optional type."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        # Create task in current column's state
        task = self.task_service.create_task(
            title="New Task",
            state=screen.current_column_state,
            task_type=task_type,
        )

        original_filename = task.filename

        # Open in editor
        with self.suspend():
            self.task_service.open_in_editor(task)

        # Rename the file to match the (possibly updated) title
        renamed_task = self.task_service.rename_task_to_match_title(original_filename)
        task_filename = renamed_task.filename if renamed_task else original_filename

        # Reload and refresh, focusing the new task
        self.board_service.reload()
        screen.refresh_board(focus_task_filename=task_filename)
        self.notify("Task created", timeout=2)

    def action_edit_task(self) -> None:
        """Edit the current task in external editor."""
        if not self.repository.capabilities.can_edit:
            self.notify("Editing not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        # Suspend TUI and open editor
        with self.suspend():
            self.task_service.open_in_editor(task)

        # Reload and refresh
        self.board_service.reload()
        screen.refresh_board()

    def action_preview_task(self) -> None:
        """Show task preview modal."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        self.push_screen(  # pyrefly: ignore[no-matching-overload]
            TaskPreviewModal(task),
            callback=self._handle_preview_result,
        )

    def _handle_preview_result(self, edit_requested: bool) -> None:
        """Handle preview modal result."""
        if not edit_requested:
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        # Open in external editor
        with self.suspend():
            self.task_service.open_in_editor(task)

        # Reload and refresh
        self.board_service.reload()
        screen.refresh_board()

    def action_move_task_left(self) -> None:
        """Move current task to previous column."""
        if not self.repository.capabilities.can_move_column:
            self.notify("Moving not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_filename = task.filename
        result = self.board_service.move_task_left(task_filename)
        if result and result.state != task.state:
            screen.refresh_board(focus_task_filename=task_filename)
            self.notify(f"Moved to {result.state.replace('_', ' ')}", timeout=2)

    def action_move_task_right(self) -> None:
        """Move current task to next column."""
        if not self.repository.capabilities.can_move_column:
            self.notify("Moving not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_filename = task.filename
        result = self.board_service.move_task_right(task_filename)
        if result and result.state != task.state:
            screen.refresh_board(focus_task_filename=task_filename)
            self.notify(f"Moved to {result.state.replace('_', ' ')}", timeout=2)

    def action_move_task_up(self) -> None:
        """Move current task up in column."""
        if not self.repository.capabilities.can_reorder:
            self.notify("Reordering not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_filename = task.filename
        if self.board_service.reorder_task(task_filename, -1):
            screen.refresh_board(focus_task_filename=task_filename)

    def action_move_task_down(self) -> None:
        """Move current task down in column."""
        if not self.repository.capabilities.can_reorder:
            self.notify("Reordering not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_filename = task.filename
        if self.board_service.reorder_task(task_filename, 1):
            screen.refresh_board(focus_task_filename=task_filename)

    def action_archive_task(self) -> None:
        """Archive the current task."""
        if not self.repository.capabilities.can_archive:
            self.notify("Archiving not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        self.board_service.archive_task(task.filename)
        screen.refresh_board()
        self.notify("Task archived", timeout=2)

    def action_delete_task(self) -> None:
        """Delete the current task (with confirmation)."""
        if not self.repository.capabilities.can_delete:
            self.notify("Deletion not supported by this backend", severity="warning")
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        # Show confirmation modal
        self.push_screen(  # pyrefly: ignore[no-matching-overload]
            ConfirmModal(f"Delete '{task.display_title}'?"),
            callback=self._handle_delete_confirm,
        )

    def _handle_delete_confirm(self, confirmed: bool) -> None:
        """Handle delete confirmation result."""
        if not confirmed:
            return

        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task:
            self.task_service.delete_task(task.filename)
            screen.refresh_board()
            self.notify("Task deleted", timeout=2)

    def action_toggle_state(self) -> None:
        """Toggle task state: cycles through columns in order, wrapping at end."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_filename = task.filename

        # Get column order from config
        config = self.config_service.get_board_config()
        column_ids = [col.id for col in config.columns]

        # Find next state (cycle through columns)
        try:
            current_idx = column_ids.index(task.state)
            next_idx = (current_idx + 1) % len(column_ids)
            new_state = column_ids[next_idx]
        except ValueError:
            # Unknown state, move to first column
            new_state = column_ids[0]

        self.board_service.move_task(task_filename, new_state)

        # Focus follows task to its new column
        screen.refresh_board(focus_task_filename=task_filename)

        self.notify(f"State: {new_state.replace('_', ' ')}", timeout=2)

    # Filter actions
    def action_enter_filter(self) -> None:
        """Enter filter mode."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return
        command_bar = screen.query_one(CommandBar)
        command_bar.enter_filter_mode()

    def action_escape(self) -> None:
        """Handle escape: dismiss modal, exit filter mode, or clear filter."""
        screen = self.screen

        # If we're on a modal screen, dismiss it
        if isinstance(screen, ModalScreen):
            screen.dismiss()
            return

        if not isinstance(screen, BoardScreen):
            return

        command_bar = screen.query_one(CommandBar)
        if command_bar.is_visible:
            # Exit filter input mode
            command_bar.exit_filter_mode()
        elif command_bar.active_filter:
            # Clear the active filter
            command_bar.clear_filter()
            self._apply_filter("")

    def on_input_submitted(self, event) -> None:
        """Handle filter input submission."""
        if event.input.id == "filter-input":
            screen = self.screen
            if isinstance(screen, BoardScreen):
                command_bar = screen.query_one(CommandBar)
                command_bar.apply_filter(event.value)
                command_bar.exit_filter_mode()
                self._apply_filter(event.value)

    def _apply_filter(self, expression: str) -> None:
        """Apply filter to the board."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        if expression.strip():
            filter_ = self.filter_service.parse(expression)
            screen.set_filter(filter_, expression)
        else:
            screen.set_filter(None, "")

        screen.load_tasks()
        screen._update_focus()


def run(settings: Settings | None = None) -> None:
    """Run the sltasks application."""
    app = SltasksApp(settings)
    app.run()
