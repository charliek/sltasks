"""sltasks TUI Application."""

import logging

from textual.app import App
from textual.binding import Binding
from textual.screen import ModalScreen

from .config import Settings
from .github import GitHubClient, GitHubClientError
from .models.sync import SyncStatus
from .repositories import FilesystemRepository, GitHubProjectsRepository, RepositoryProtocol
from .services import (
    BoardService,
    ConfigService,
    FilterService,
    TaskService,
    TemplateService,
)
from .sync.engine import GitHubSyncEngine
from .ui.screens.board import BoardScreen
from .ui.widgets import (
    CommandBar,
    ConfirmModal,
    HelpScreen,
    TaskPreviewModal,
    TypeSelectorModal,
)

logger = logging.getLogger(__name__)


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
        # Sync operations (fetch/push via sync screen)
        Binding("s", "sync_screen", "Sync", show=True),
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
        logger.info("Initializing services")
        logger.debug("Project root: %s", self.settings.project_root.absolute())

        self.config_service = ConfigService(self.settings.project_root)
        config = self.config_service.get_config()

        # Log configuration details
        logger.info("Provider: %s", config.provider)
        board_config = config.board
        logger.debug(
            "Board config: %d columns, %d types, %d priorities",
            len(board_config.columns),
            len(board_config.types),
            len(board_config.priorities),
        )
        logger.debug("Columns: %s", [col.id for col in board_config.columns])

        # Initialize repository based on provider
        self.repository: RepositoryProtocol
        if config.provider == "github":
            logger.info("Using GitHub Projects repository")
            if config.github:
                logger.debug("GitHub project URL: %s", config.github.project_url)
                logger.debug("GitHub default repo: %s", config.github.default_repo)
            self.repository = GitHubProjectsRepository(self.config_service)
        else:
            # Default to filesystem
            task_root = self.config_service.task_root
            logger.info("Using filesystem repository: %s", task_root)
            self.repository = FilesystemRepository(task_root, self.config_service)

        # Validate repository configuration
        logger.debug("Validating repository configuration")
        valid, error = self.repository.validate()
        if not valid:
            # Store error for display on mount
            logger.error("Repository validation failed: %s", error)
            self._init_error = error
        else:
            logger.info("Repository validation successful")
            self._init_error = None

        self.template_service = TemplateService(self.config_service)
        self.task_service = TaskService(self.repository, self.config_service, self.template_service)
        self.board_service = BoardService(self.repository, self.config_service)
        self.filter_service = FilterService()

        # Initialize sync engine if GitHub sync is enabled
        self.sync_engine: GitHubSyncEngine | None = None
        self._sync_statuses: dict[str, SyncStatus] = {}
        if (
            config.provider == "github"
            and config.github
            and config.github.sync
            and config.github.sync.enabled
        ):
            logger.info("GitHub sync enabled, initializing sync engine")
            try:
                client = GitHubClient.from_environment(
                    base_url=config.github.base_url or "api.github.com"
                )
                self.sync_engine = GitHubSyncEngine(
                    self.config_service,
                    client,
                    self.config_service.task_root,
                )
            except Exception as e:
                logger.warning("Failed to initialize sync engine: %s", e)

        # Update app banner/title
        self._update_banner()

        logger.info("Services initialized")

    def _update_banner(self) -> None:
        """Update app banner/title based on config and provider."""
        banner = self.config_service.get_banner()

        # For GitHub provider, use project title if no explicit banner configured
        if banner == "sltasks" and hasattr(self.repository, "get_board_metadata"):
            try:
                metadata = self.repository.get_board_metadata()
                if metadata.get("project_title"):
                    banner = metadata["project_title"]
            except Exception:
                pass  # Keep default on error

        self.title = banner

    @property
    def sync_statuses(self) -> dict[str, SyncStatus]:
        """Get current sync statuses for all tasks.

        Lazily computes sync statuses from the sync engine's detect_changes().
        Returns empty dict if sync is not enabled.
        """
        return self._sync_statuses

    def refresh_sync_statuses(self) -> None:
        """Refresh sync statuses from the sync engine."""
        if not self.sync_engine:
            self._sync_statuses = {}
            return

        try:
            changes = self.sync_engine.detect_changes()

            # Build status map
            statuses: dict[str, SyncStatus] = {}

            # Mark tasks that need to be pulled
            for task_id in changes.to_pull:
                statuses[task_id] = SyncStatus.REMOTE_MODIFIED

            # Mark tasks that need to be pushed
            for task_id in changes.to_push:
                # Check if it's a local-only file or a modified synced file
                if "#" not in task_id:  # Local-only files don't have repo#number format
                    statuses[task_id] = SyncStatus.LOCAL_ONLY
                else:
                    statuses[task_id] = SyncStatus.LOCAL_MODIFIED

            # Mark conflicts
            for conflict in changes.conflicts:
                statuses[conflict.task_id] = SyncStatus.CONFLICT

            # Mark remaining synced files as synced (those not in any change category)
            synced_files = self.sync_engine._scan_synced_files()
            for task in synced_files:
                if task.id not in statuses:
                    statuses[task.id] = SyncStatus.SYNCED

            self._sync_statuses = statuses
            logger.debug("Refreshed sync statuses: %d tasks", len(statuses))

        except Exception as e:
            logger.warning("Failed to refresh sync statuses: %s", e)
            self._sync_statuses = {}

    def on_mount(self) -> None:
        """Called when app is mounted."""
        # Check for initialization errors
        if self._init_error:
            self.notify(f"Error: {self._init_error}", severity="error", timeout=10)

        # Ensure tasks directory exists (filesystem only)
        if hasattr(self.repository, "ensure_directory"):
            self.repository.ensure_directory()

        # Refresh sync statuses if sync is enabled
        if self.sync_engine:
            self.refresh_sync_statuses()

        # Push the board screen
        self.push_screen("board")

    def action_refresh(self) -> None:
        """Refresh the board."""
        # Refresh sync statuses if enabled
        if self.sync_engine:
            self.refresh_sync_statuses()

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

        original_task_id = task.id

        # Open in editor
        task_root = self.config_service.task_root
        with self.suspend():
            self.task_service.open_in_editor(task, task_root)

        # Rename the file to match the (possibly updated) title
        renamed_task = self.task_service.rename_task_to_match_title(original_task_id, task_root)
        task_id = renamed_task.id if renamed_task else original_task_id

        # Reload and refresh, focusing the new task
        self.board_service.reload()
        screen.refresh_board(focus_task_id=task_id)
        self.notify("Task created", timeout=2)

    def action_edit_task(self) -> None:
        """Edit the current task in external editor."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        # Suspend TUI and open editor
        task_root = self.config_service.task_root
        with self.suspend():
            success = self.task_service.open_in_editor(task, task_root)

        # Reload and refresh
        try:
            self.board_service.reload()
            screen.refresh_board()
            if success:
                self.notify("Task updated", timeout=2)
        except GitHubClientError as e:
            logger.error("Failed to save task: %s", e)
            self.notify(f"Failed to save: {e}", severity="error", timeout=5)

    def action_preview_task(self) -> None:
        """Show task preview modal."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_root = self.config_service.task_root
        self.push_screen(  # pyrefly: ignore[no-matching-overload]
            TaskPreviewModal(task, task_root),
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
        task_root = self.config_service.task_root
        with self.suspend():
            success = self.task_service.open_in_editor(task, task_root)

        # Reload and refresh
        try:
            self.board_service.reload()
            screen.refresh_board()
            if success:
                self.notify("Task updated", timeout=2)
        except GitHubClientError as e:
            logger.error("Failed to save task: %s", e)
            self.notify(f"Failed to save: {e}", severity="error", timeout=5)

    def action_move_task_left(self) -> None:
        """Move current task to previous column."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_id = task.id
        original_state = task.state  # Capture before modification (same object in cache)
        try:
            result = self.board_service.move_task_left(task_id)
            if result is None:
                self.notify("Cannot move task", severity="warning", timeout=2)
            elif result.state != original_state:
                screen.refresh_board(focus_task_id=task_id)
                self.notify(f"Moved to {result.state.replace('_', ' ')}", timeout=2)
            else:
                self.notify("Already at first column", severity="information", timeout=2)
        except GitHubClientError as e:
            logger.error("Failed to move task left: %s", e)
            self.notify(f"Failed to move: {e}", severity="error", timeout=5)

    def action_move_task_right(self) -> None:
        """Move current task to next column."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_id = task.id
        original_state = task.state  # Capture before modification (same object in cache)
        try:
            result = self.board_service.move_task_right(task_id)
            if result is None:
                self.notify("Cannot move task", severity="warning", timeout=2)
            elif result.state != original_state:
                screen.refresh_board(focus_task_id=task_id)
                self.notify(f"Moved to {result.state.replace('_', ' ')}", timeout=2)
            else:
                self.notify("Already at last column", severity="information", timeout=2)
        except GitHubClientError as e:
            logger.error("Failed to move task right: %s", e)
            self.notify(f"Failed to move: {e}", severity="error", timeout=5)

    def action_move_task_up(self) -> None:
        """Move current task up in column."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_id = task.id
        try:
            if self.board_service.reorder_task(task_id, -1):
                screen.refresh_board(focus_task_id=task_id)
                self.notify("Moved up", timeout=1)
            else:
                self.notify("Already at top", severity="information", timeout=1)
        except GitHubClientError as e:
            logger.error("Failed to reorder task: %s", e)
            self.notify(f"Failed to reorder: {e}", severity="error", timeout=5)

    def action_move_task_down(self) -> None:
        """Move current task down in column."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        task_id = task.id
        try:
            if self.board_service.reorder_task(task_id, 1):
                screen.refresh_board(focus_task_id=task_id)
                self.notify("Moved down", timeout=1)
            else:
                self.notify("Already at bottom", severity="information", timeout=1)
        except GitHubClientError as e:
            logger.error("Failed to reorder task: %s", e)
            self.notify(f"Failed to reorder: {e}", severity="error", timeout=5)

    def action_archive_task(self) -> None:
        """Archive the current task."""
        screen = self.screen
        if not isinstance(screen, BoardScreen):
            return

        task = screen.get_current_task()
        if task is None:
            return

        self.board_service.archive_task(task.id)
        screen.refresh_board()
        self.notify("Task archived", timeout=2)

    def action_delete_task(self) -> None:
        """Delete the current task (with confirmation)."""
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
            self.task_service.delete_task(task.id)
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

        task_id = task.id

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

        self.board_service.move_task(task_id, new_state)

        # Focus follows task to its new column
        screen.refresh_board(focus_task_id=task_id)

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

    # Sync actions
    def action_sync_screen(self) -> None:
        """Open sync management screen."""
        config = self.config_service.get_config()
        if not config.github or not config.github.sync or not config.github.sync.enabled:
            self.notify("Sync not enabled", severity="warning", timeout=2)
            return

        if not self.sync_engine:
            self.notify("Sync engine not initialized", severity="error", timeout=3)
            return

        from .ui.screens.sync_screen import SyncScreen

        self.push_screen(
            SyncScreen(self.sync_engine),
            callback=self._handle_sync_screen_close,
        )

    def _handle_sync_screen_close(self, _result: None) -> None:
        """Handle sync screen close - refresh the board."""
        # Refresh sync statuses and board after sync operations
        self.refresh_sync_statuses()
        screen = self.screen
        if isinstance(screen, BoardScreen):
            screen.refresh_board()


def run(settings: Settings | None = None) -> None:
    """Run the sltasks application."""
    app = SltasksApp(settings)
    app.run()
