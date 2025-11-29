# Phase 9: Filter & Command Bar

## Overview

This phase adds a filter/command bar that allows users to filter tasks by text, tags, state, and priority. The bar appears at the bottom of the screen and provides a quick way to narrow down visible tasks. The FilterService was already implemented in Phase 4.

## Goals

1. Add command bar UI widget
2. Implement filter input mode
3. Apply filters to board display
4. Show active filter indicator
5. Persist filter across refreshes
6. Clear filter with Escape

## Task Checklist

- [ ] Create `CommandBar` widget:
  - [ ] Text input for filter expression
  - [ ] Mode indicator (filter, command, etc.)
  - [ ] Active filter display
- [ ] Implement filter mode in `KosmosApp`:
  - [ ] `/` - Enter filter mode
  - [ ] `Escape` - Exit filter mode / clear filter
  - [ ] `Enter` - Apply filter
- [ ] Update `BoardScreen` to support filtering:
  - [ ] `set_filter(Filter)` method
  - [ ] Apply filter when loading tasks
  - [ ] Show filtered task counts in headers
- [ ] Add filter status display:
  - [ ] Show active filter expression
  - [ ] Show filtered vs total task counts
- [ ] Handle empty filter results:
  - [ ] Show "No matching tasks" in empty columns
- [ ] Add filter autocomplete (optional):
  - [ ] Suggest tag: completions
  - [ ] Suggest state: completions
  - [ ] Suggest priority: completions

## Detailed Specifications

### CommandBar Widget

```python
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
    }

    CommandBar .mode-indicator {
        width: 8;
        padding: 0 1;
        background: $primary;
    }

    CommandBar .filter-input {
        width: 1fr;
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
        self._mode: str = "normal"

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static("Filter:", id="mode-indicator", classes="mode-indicator")
            yield Input(placeholder="tag:bug priority:high...", id="filter-input", classes="filter-input")
            yield Static("", id="filter-status", classes="filter-status")

    def enter_filter_mode(self) -> None:
        """Enter filter input mode."""
        self._mode = "filter"
        input_widget = self.query_one("#filter-input", Input)
        input_widget.value = self._active_filter
        input_widget.focus()

    def exit_filter_mode(self) -> None:
        """Exit filter mode."""
        self._mode = "normal"
        self.app.query_one(BoardScreen).focus()

    def apply_filter(self, expression: str) -> None:
        """Apply the filter expression."""
        self._active_filter = expression
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
    def is_filter_mode(self) -> bool:
        """Check if in filter mode."""
        return self._mode == "filter"
```

### App Key Bindings

```python
class KosmosApp(App):

    BINDINGS = [
        # ... existing bindings ...

        # Filter mode
        Binding("/", "enter_filter", "Filter", show=True),
        Binding("escape", "exit_filter", "Clear", show=False, priority=True),
    ]

    def action_enter_filter(self) -> None:
        """Enter filter mode."""
        command_bar = self.query_one(CommandBar)
        command_bar.enter_filter_mode()

    def action_exit_filter(self) -> None:
        """Exit filter mode or clear filter."""
        command_bar = self.query_one(CommandBar)
        if command_bar.is_filter_mode:
            command_bar.exit_filter_mode()
        elif command_bar.active_filter:
            command_bar.clear_filter()
            self._apply_filter("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle filter input submission."""
        if event.input.id == "filter-input":
            self._apply_filter(event.value)
            self.query_one(CommandBar).exit_filter_mode()

    def _apply_filter(self, expression: str) -> None:
        """Apply filter to the board."""
        filter_ = self.filter_service.parse(expression)
        screen = self.query_one(BoardScreen)
        screen.set_filter(filter_)
        screen.load_tasks()
```

### BoardScreen Filter Support

```python
class BoardScreen(Screen):
    """Main kanban board screen with filtering."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_column = 0
        self._current_task = 0
        self._filter: Filter | None = None

    def set_filter(self, filter_: Filter | None) -> None:
        """Set the active filter."""
        self._filter = filter_

    def load_tasks(self) -> None:
        """Load tasks from the board service and apply filter."""
        board = self.app.board_service.load_board()

        for state, tasks in board.visible_columns:
            # Apply filter if active
            if self._filter:
                tasks = self.app.filter_service.apply(tasks, self._filter)

            column_id = f"column-{state.value.replace('_', '-')}"
            try:
                column = self.query_one(f"#{column_id}", KanbanColumn)
                column.set_tasks(tasks)
            except Exception:
                pass
```

### Filter Syntax Reference

```
Filter Expression Syntax:
------------------------
text           - Search in title and body (case-insensitive)
tag:bug        - Include tasks with tag "bug"
-tag:wontfix   - Exclude tasks with tag "wontfix"
state:todo     - Filter by state (todo, in_progress, done, archived)
priority:high  - Filter by priority (low, medium, high, critical)
archived:true  - Show archived tasks

Multiple conditions are ANDed together:
  tag:bug priority:high login
  → Tasks with tag "bug" AND priority high AND containing "login"
```

## Visual Design

```
┌─────────────────────────────────────────────────────────────────────┐
│ Kosmos                                                               │
├───────────────────┬───────────────────┬───────────────────┬─────────┤
│ To Do (2/5)       │ In Progress (1/2) │ Done (0/3)        │         │
│ ↑ filtered count  │                   │                   │         │
├───────────────────┼───────────────────┼───────────────────┤         │
│                   │                   │                   │         │
│ ┌───────────────┐ │ ┌───────────────┐ │                   │         │
│ │ Fix login bug │ │ │ Refactor API  │ │  No matching      │         │
│ │ ● high        │ │ │ ● high        │ │  tasks            │         │
│ │ #bug #auth    │ │ │ #backend      │ │                   │         │
│ └───────────────┘ │ └───────────────┘ │                   │         │
│                   │                   │                   │         │
│ ┌───────────────┐ │                   │                   │         │
│ │ Add logging   │ │                   │                   │         │
│ │ ● high        │ │                   │                   │         │
│ │ #backend      │ │                   │                   │         │
│ └───────────────┘ │                   │                   │         │
│                   │                   │                   │         │
└───────────────────┴───────────────────┴───────────────────┴─────────┘
│ Filter: priority:high                          Active: priority:high │
└─────────────────────────────────────────────────────────────────────┘
│ q Quit  / Filter  ? Help  r Refresh                                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Testing Notes

Manual testing scenarios:
1. Press `/` to enter filter mode
2. Type `tag:bug` and press Enter
3. Verify only tasks with "bug" tag are shown
4. Press Escape to clear filter
5. Test multiple conditions: `priority:high tag:backend`
6. Test text search: `login`
7. Test exclusion: `-tag:docs`
8. Verify filter persists across refresh (r)
9. Navigate filtered results with hjkl

## Deviations from Plan

_This section will be updated if implementation differs from the plan._

| Date | Deviation | Reason |
|------|-----------|--------|
| - | - | - |

## Key Notes

- FilterService already exists from Phase 4 with full parsing logic
- Filter is applied after loading from BoardService
- Empty columns show "No matching tasks" when filtered
- Column headers could show filtered/total counts (e.g., "To Do (2/5)")
- Escape key has priority to exit filter mode first
- Filter persists until explicitly cleared
