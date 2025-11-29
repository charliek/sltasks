# Phase 5: Basic TUI

## Overview

This phase implements the initial Textual application with a 3-column Kanban board layout. The focus is on displaying tasks correctly and establishing the widget hierarchy. Navigation and actions will be added in later phases.

## Goals

1. Create the main Textual App class
2. Implement the board screen with 3-column layout
3. Create column and task card widgets
4. Display tasks from the repository
5. Add basic styling for readability
6. Set up the status bar with placeholder commands

## Task Checklist

- [ ] Create `src/kosmos/app.py`:
  - [ ] `KosmosApp` Textual App class
  - [ ] CSS styling setup
  - [ ] Service initialization
- [ ] Create `src/kosmos/ui/screens/board.py`:
  - [ ] `BoardScreen` main screen
  - [ ] 3-column horizontal layout
  - [ ] Load and display tasks on mount
- [ ] Create `src/kosmos/ui/widgets/column.py`:
  - [ ] `KanbanColumn` widget
  - [ ] Header with title and count
  - [ ] Container for task cards
- [ ] Create `src/kosmos/ui/widgets/task_card.py`:
  - [ ] `TaskCard` widget
  - [ ] Display title, priority indicator, tags
- [ ] Create `src/kosmos/ui/styles.py`:
  - [ ] CSS styles for the app
  - [ ] Priority colors
  - [ ] Column layout
- [ ] Update `src/kosmos/__main__.py`:
  - [ ] Parse CLI arguments
  - [ ] Launch the app
- [ ] Create `src/kosmos/config/settings.py`:
  - [ ] `Settings` Pydantic Settings class
  - [ ] task_root configuration
- [ ] Update all `__init__.py` files with exports

## Detailed Specifications

### KosmosApp (app.py)

```python
from pathlib import Path
from textual.app import App, ComposeResult
from textual.binding import Binding

from .config import Settings
from .repositories import FilesystemRepository
from .services import TaskService, BoardService, FilterService
from .ui.screens import BoardScreen


class KosmosApp(App):
    """Kosmos - Terminal Kanban TUI."""

    TITLE = "Kosmos"

    CSS_PATH = "ui/styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
        # More bindings in later phases
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


def run(settings: Settings | None = None) -> None:
    """Run the Kosmos application."""
    app = KosmosApp(settings)
    app.run()
```

### BoardScreen (ui/screens/board.py)

```python
from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal, Container
from textual.widgets import Header, Footer, Static

from ...models import TaskState
from ..widgets import KanbanColumn


class BoardScreen(Screen):
    """Main kanban board screen."""

    def compose(self) -> ComposeResult:
        """Create the board layout."""
        yield Header()

        with Container(id="board-container"):
            with Horizontal(id="columns"):
                yield KanbanColumn(
                    title="To Do",
                    state=TaskState.TODO,
                    id="column-todo",
                )
                yield KanbanColumn(
                    title="In Progress",
                    state=TaskState.IN_PROGRESS,
                    id="column-in-progress",
                )
                yield KanbanColumn(
                    title="Done",
                    state=TaskState.DONE,
                    id="column-done",
                )

        yield Footer()

    def on_mount(self) -> None:
        """Load tasks when screen mounts."""
        self.load_tasks()

    def load_tasks(self) -> None:
        """Load tasks from the board service and populate columns."""
        board = self.app.board_service.load_board()

        # Populate each column
        for state, tasks in board.visible_columns:
            column = self.query_one(f"#column-{state.value.replace('_', '-')}", KanbanColumn)
            column.set_tasks(tasks)
```

### KanbanColumn (ui/widgets/column.py)

```python
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.widgets import Static
from textual.widget import Widget

from ...models import Task, TaskState
from .task_card import TaskCard


class KanbanColumn(Widget):
    """A single column in the kanban board."""

    DEFAULT_CSS = """
    KanbanColumn {
        width: 1fr;
        height: 100%;
        border: solid $primary;
        margin: 0 1;
    }

    KanbanColumn .column-header {
        height: 3;
        padding: 1;
        background: $surface;
        text-align: center;
        text-style: bold;
    }

    KanbanColumn .column-content {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(
        self,
        title: str,
        state: TaskState,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.title = title
        self.state = state
        self._tasks: list[Task] = []

    def compose(self) -> ComposeResult:
        """Create column layout."""
        yield Static(self._header_text, classes="column-header")
        with VerticalScroll(classes="column-content"):
            # Task cards will be added dynamically
            pass

    @property
    def _header_text(self) -> str:
        """Header text with task count."""
        return f"{self.title} ({len(self._tasks)})"

    def set_tasks(self, tasks: list[Task]) -> None:
        """Set the tasks for this column."""
        self._tasks = tasks
        self._refresh_tasks()

    def _refresh_tasks(self) -> None:
        """Refresh the task cards in this column."""
        content = self.query_one(".column-content", VerticalScroll)
        content.remove_children()

        for task in self._tasks:
            content.mount(TaskCard(task))

        # Update header count
        header = self.query_one(".column-header", Static)
        header.update(self._header_text)
```

### TaskCard (ui/widgets/task_card.py)

```python
from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget

from ...models import Task, Priority


class TaskCard(Widget):
    """A task card displayed in a column."""

    DEFAULT_CSS = """
    TaskCard {
        height: auto;
        min-height: 4;
        margin-bottom: 1;
        padding: 1;
        background: $surface;
        border: solid $primary-darken-2;
    }

    TaskCard:hover {
        background: $surface-lighten-1;
    }

    TaskCard .task-title {
        text-style: bold;
    }

    TaskCard .task-priority {
        margin-top: 1;
    }

    TaskCard .task-tags {
        margin-top: 1;
        color: $text-muted;
    }

    TaskCard .priority-critical { color: red; }
    TaskCard .priority-high { color: orange; }
    TaskCard .priority-medium { color: yellow; }
    TaskCard .priority-low { color: green; }
    """

    def __init__(self, task: Task, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.task = task

    def compose(self) -> ComposeResult:
        """Create card layout."""
        yield Static(self.task.display_title, classes="task-title")
        yield Static(
            self._priority_indicator,
            classes=f"task-priority priority-{self.task.priority.value}",
        )
        if self.task.tags:
            yield Static(
                ", ".join(self.task.tags),
                classes="task-tags",
            )

    @property
    def _priority_indicator(self) -> str:
        """Get priority indicator with symbol."""
        symbols = {
            Priority.CRITICAL: "🔴 critical",
            Priority.HIGH: "🟠 high",
            Priority.MEDIUM: "🟡 medium",
            Priority.LOW: "🟢 low",
        }
        return symbols.get(self.task.priority, "")
```

### Styles (ui/styles.tcss)

```css
/* Main app styles */
Screen {
    background: $background;
}

#board-container {
    width: 100%;
    height: 100%;
    padding: 1;
}

#columns {
    width: 100%;
    height: 100%;
}

/* Column styles */
KanbanColumn {
    width: 1fr;
    height: 100%;
    border: solid $primary;
    margin: 0 1;
}

KanbanColumn .column-header {
    height: 3;
    padding: 1;
    background: $surface;
    text-align: center;
    text-style: bold;
}

KanbanColumn .column-content {
    height: 100%;
    padding: 1;
}

/* Task card styles */
TaskCard {
    height: auto;
    min-height: 4;
    margin-bottom: 1;
    padding: 1;
    background: $surface;
    border: solid $primary-darken-2;
}

TaskCard:hover {
    background: $surface-lighten-1;
}

TaskCard .task-title {
    text-style: bold;
}

TaskCard .task-priority {
    margin-top: 1;
}

TaskCard .task-tags {
    margin-top: 1;
    color: $text-muted;
}

/* Priority colors */
.priority-critical { color: red; }
.priority-high { color: orange; }
.priority-medium { color: yellow; }
.priority-low { color: green; }
```

### Settings (config/settings.py)

```python
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings."""

    task_root: Path = Field(
        default=Path(".tasks"),
        description="Path to tasks directory",
    )

    editor: str = Field(
        default_factory=lambda: os.environ.get("EDITOR", "vim"),
        description="Editor for task editing",
    )

    model_config = {
        "env_prefix": "KOSMOS_",
    }
```

### CLI Entry Point (__main__.py)

```python
"""CLI entry point for Kosmos."""
import argparse
from pathlib import Path

from .config import Settings


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        prog="kosmos",
        description="Terminal-based Kanban TUI for markdown task management",
    )
    parser.add_argument(
        "--task-root",
        type=Path,
        default=None,
        help="Path to tasks directory (default: .tasks/)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Build settings from CLI args
    settings_kwargs = {}
    if args.task_root:
        settings_kwargs["task_root"] = args.task_root

    settings = Settings(**settings_kwargs)

    # Import here to avoid circular imports
    from .app import run
    run(settings)


if __name__ == "__main__":
    main()
```

## Widget Hierarchy

```
KosmosApp
└── BoardScreen
    ├── Header (Textual built-in)
    ├── Container#board-container
    │   └── Horizontal#columns
    │       ├── KanbanColumn#column-todo
    │       │   ├── Static.column-header ("To Do (3)")
    │       │   └── VerticalScroll.column-content
    │       │       ├── TaskCard
    │       │       ├── TaskCard
    │       │       └── TaskCard
    │       ├── KanbanColumn#column-in-progress
    │       │   └── ...
    │       └── KanbanColumn#column-done
    │           └── ...
    └── Footer (Textual built-in)
```

## Testing Notes

For this phase, manual testing is primary:
- Run `uv run kosmos` with sample .tasks/ directory
- Verify 3 columns display correctly
- Verify tasks appear in correct columns
- Verify priority indicators and tags display
- Test with empty .tasks/ directory
- Test with no .tasks/ directory (should be created)

## Deviations from Plan

_This section will be updated if implementation differs from the plan._

| Date | Deviation | Reason |
|------|-----------|--------|
| - | - | - |

## Key Notes

- This phase focuses on display only - no interaction yet
- TaskCard doesn't have selection highlighting yet (Phase 7)
- The Footer shows bindings but they're not fully functional yet
- We use Textual's built-in CSS variables ($primary, $surface, etc.)
- The app accesses services via `self.app.board_service` pattern
- Styles can be in .tcss file or embedded in widgets via DEFAULT_CSS
