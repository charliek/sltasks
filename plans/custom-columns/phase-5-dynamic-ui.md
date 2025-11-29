# Phase 5: Dynamic UI Generation

## Overview

This phase updates the TUI layer to dynamically generate columns from configuration instead of hardcoding three columns. This is the most user-visible change - after this phase, the board displays custom columns defined in `sltasks.yml`.

## Goals

1. Update `BoardScreen` to generate columns dynamically from config
2. Update `KanbanColumn` widget to accept string state
3. Update keyboard navigation for variable column count
4. Update task state cycling for custom columns
5. Ensure responsive layout works with 2-6 columns

## Task Checklist

- [ ] Update `src/kosmos/ui/screens/board.py`:
  - [ ] Remove `COLUMN_STATES` constant
  - [ ] Add config access via `self.app.config_service`
  - [ ] Rewrite `compose()` to generate columns from config
  - [ ] Update `load_tasks()` for dynamic columns
  - [ ] Update `_get_column()` helper for string IDs
  - [ ] Update `_get_current_column()` for variable count
  - [ ] Update navigation methods (left/right column switching)
- [ ] Update `src/kosmos/ui/widgets/column.py`:
  - [ ] Change `state: TaskState` to `state: str`
  - [ ] Update content ID generation for custom states
  - [ ] Update header ID generation
- [ ] Update `src/kosmos/app.py`:
  - [ ] Update `action_toggle_state()` for custom columns
  - [ ] Ensure config_service is available to screens
- [ ] Update CSS in `src/kosmos/ui/styles/` if needed:
  - [ ] Column width adjustments for 2-6 columns
- [ ] Test UI with various column counts (2, 3, 4, 5, 6)

## Detailed Specifications

### BoardScreen Updates

**Current Implementation (src/kosmos/ui/screens/board.py):**
```python
from kosmos.models import TaskState

COLUMN_STATES = [TaskState.TODO, TaskState.IN_PROGRESS, TaskState.DONE]


class BoardScreen(Screen):
    def compose(self) -> ComposeResult:
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
```

**New Implementation:**
```python
from kosmos.models import BoardConfig


class BoardScreen(Screen):
    """Main board screen showing kanban columns."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_column_idx = 0
        self._current_task_idx = 0
        self._filter: str = ""

    @property
    def board_config(self) -> BoardConfig:
        """Get board configuration from app."""
        return self.app.config_service.get_board_config()

    @property
    def column_ids(self) -> list[str]:
        """Get list of visible column IDs in order."""
        return self.board_config.column_ids

    @property
    def column_count(self) -> int:
        """Number of visible columns."""
        return len(self.column_ids)

    def compose(self) -> ComposeResult:
        """Compose the board with dynamic columns."""
        yield Header()

        with Container(id="board-container"):
            with Horizontal(id="columns"):
                for col in self.board_config.columns:
                    # Generate CSS-safe ID (replace underscores with hyphens)
                    col_id = f"column-{col.id.replace('_', '-')}"
                    yield KanbanColumn(
                        title=col.title,
                        state=col.id,
                        id=col_id,
                    )

        yield Static("", id="filter-status", classes="filter-status-bar")
        yield CommandBar()
        yield Footer()

    def _get_column_id(self, index: int) -> str:
        """Get column widget ID for index."""
        if 0 <= index < self.column_count:
            col_id = self.column_ids[index]
            return f"column-{col_id.replace('_', '-')}"
        return ""

    def _get_column(self, index: int) -> KanbanColumn | None:
        """Get column widget by index."""
        col_id = self._get_column_id(index)
        if not col_id:
            return None
        try:
            return self.query_one(f"#{col_id}", KanbanColumn)
        except Exception:
            return None

    def _get_current_column(self) -> KanbanColumn | None:
        """Get the currently focused column."""
        return self._get_column(self._current_column_idx)

    def load_tasks(self) -> None:
        """Load tasks from the board service and populate columns."""
        board = self.app.board_service.load_board()
        config = self.board_config

        # Populate each column
        for col_id, col_title, tasks in board.visible_columns(config):
            # Apply filter if active
            if self._filter:
                filter_obj = self.app.filter_service.parse(self._filter)
                tasks = self.app.filter_service.apply(tasks, filter_obj)

            # Find column widget
            widget_id = f"column-{col_id.replace('_', '-')}"
            try:
                column = self.query_one(f"#{widget_id}", KanbanColumn)
                column.set_tasks(tasks)
            except Exception as e:
                self.log.error(f"Failed to load column {widget_id}: {e}")

    # Navigation methods
    def action_focus_left_column(self) -> None:
        """Move focus to the column on the left."""
        if self._current_column_idx > 0:
            self._current_column_idx -= 1
            self._current_task_idx = 0
            self._update_focus()

    def action_focus_right_column(self) -> None:
        """Move focus to the column on the right."""
        if self._current_column_idx < self.column_count - 1:
            self._current_column_idx += 1
            self._current_task_idx = 0
            self._update_focus()

    def action_focus_first_column(self) -> None:
        """Move focus to the first column."""
        self._current_column_idx = 0
        self._current_task_idx = 0
        self._update_focus()

    def action_focus_last_column(self) -> None:
        """Move focus to the last column."""
        self._current_column_idx = self.column_count - 1
        self._current_task_idx = 0
        self._update_focus()

    def _update_focus(self) -> None:
        """Update visual focus indicator."""
        # Remove focus from all columns
        for i in range(self.column_count):
            col = self._get_column(i)
            if col:
                col.remove_class("focused")

        # Add focus to current column
        current = self._get_current_column()
        if current:
            current.add_class("focused")
            # Update task selection within column
            current.select_task(self._current_task_idx)

    # ... other methods ...
```

### KanbanColumn Updates

**Current Implementation (src/kosmos/ui/widgets/column.py):**
```python
from kosmos.models import TaskState


class KanbanColumn(Static):
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
```

**New Implementation:**
```python
class KanbanColumn(Static):
    """A single column in the kanban board."""

    def __init__(
        self,
        title: str,
        state: str,  # Changed from TaskState
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.title = title
        self.state = state  # Now a string
        self._tasks: list[Task] = []
        self._selected_idx = 0

    @property
    def _state_css_id(self) -> str:
        """Get CSS-safe version of state for IDs."""
        return self.state.replace("_", "-")

    @property
    def _header_text(self) -> str:
        """Header text with task count."""
        count = len(self._tasks)
        return f"{self.title} ({count})"

    def compose(self) -> ComposeResult:
        """Compose the column layout."""
        yield Static(
            self._header_text,
            id=f"header-{self._state_css_id}",
            classes="column-header",
        )
        yield TaskListScroll(
            id=f"content-{self._state_css_id}",
            classes="column-content",
        )

    def set_tasks(self, tasks: list[Task]) -> None:
        """Set the tasks for this column."""
        self._tasks = tasks
        self._selected_idx = min(self._selected_idx, max(0, len(tasks) - 1))
        self.call_after_refresh(self._refresh_tasks)

    async def _refresh_tasks(self) -> None:
        """Refresh the task cards in this column."""
        content_id = f"#content-{self._state_css_id}"
        try:
            content = self.query_one(content_id, TaskListScroll)
        except Exception as e:
            self.log.error(f"Cannot find {content_id}: {e}")
            return

        # Remove existing task cards
        await content.remove_children()

        # Show empty state or task cards
        if not self._tasks:
            state_name = self.state.replace("_", " ")
            await content.mount(EmptyColumnMessage(f"No {state_name} tasks"))
        else:
            for idx, task in enumerate(self._tasks):
                task_id = task.filename.replace(".md", "")
                card = TaskCard(task, id=f"task-{task_id}")
                if idx == self._selected_idx:
                    card.add_class("selected")
                await content.mount(card)

        # Update header count
        try:
            header = self.query_one(f"#header-{self._state_css_id}", Static)
            header.update(self._header_text)
        except Exception:
            pass

    def select_task(self, index: int) -> None:
        """Select a task by index."""
        if not self._tasks:
            return

        # Clamp index
        index = max(0, min(index, len(self._tasks) - 1))
        old_idx = self._selected_idx
        self._selected_idx = index

        # Update selection visuals
        if old_idx != index:
            self._update_selection(old_idx, index)

    def _update_selection(self, old_idx: int, new_idx: int) -> None:
        """Update visual selection."""
        # Remove old selection
        if 0 <= old_idx < len(self._tasks):
            old_task = self._tasks[old_idx]
            old_id = f"task-{old_task.filename.replace('.md', '')}"
            try:
                old_card = self.query_one(f"#{old_id}", TaskCard)
                old_card.remove_class("selected")
            except Exception:
                pass

        # Add new selection
        if 0 <= new_idx < len(self._tasks):
            new_task = self._tasks[new_idx]
            new_id = f"task-{new_task.filename.replace('.md', '')}"
            try:
                new_card = self.query_one(f"#{new_id}", TaskCard)
                new_card.add_class("selected")
                # Scroll into view
                new_card.scroll_visible()
            except Exception:
                pass

    @property
    def selected_task(self) -> Task | None:
        """Get the currently selected task."""
        if self._tasks and 0 <= self._selected_idx < len(self._tasks):
            return self._tasks[self._selected_idx]
        return None

    @property
    def task_count(self) -> int:
        """Number of tasks in this column."""
        return len(self._tasks)
```

### App State Cycling Update

**Current Implementation:**
```python
def action_toggle_state(self) -> None:
    """Cycle through task states."""
    # Uses hardcoded TaskState enum
```

**New Implementation:**
```python
class KosmosApp(App):
    def action_toggle_state(self) -> None:
        """Cycle the selected task through states."""
        screen = self.query_one(BoardScreen)
        task = screen.get_selected_task()
        if task is None:
            return

        # Get column order from config
        config = self.config_service.get_board_config()
        column_ids = config.column_ids

        # Find current position and advance
        try:
            current_idx = column_ids.index(task.state)
            next_idx = (current_idx + 1) % len(column_ids)
            next_state = column_ids[next_idx]
        except ValueError:
            # Unknown state - move to first column
            next_state = column_ids[0]

        # Move task
        self.board_service.move_task(task.filename, next_state)
        screen.load_tasks()
```

### CSS Adjustments for Variable Columns

The existing CSS should work, but we may need to ensure columns flex properly:

```css
/* src/kosmos/ui/styles/board.tcss */

#columns {
    width: 100%;
    height: 100%;
}

KanbanColumn {
    width: 1fr;  /* Equal width, flexible */
    min-width: 20;  /* Minimum readable width */
    height: 100%;
    border: solid $primary;
    margin: 0 1;
}

/* Adjust for many columns - reduce margins */
#columns.many-columns KanbanColumn {
    margin: 0;
}
```

Optionally, add logic to detect many columns:

```python
def on_mount(self) -> None:
    """Handle mount event."""
    # Add class if many columns
    if self.column_count > 4:
        columns_container = self.query_one("#columns")
        columns_container.add_class("many-columns")

    self.load_tasks()
    self._update_focus()
```

## Testing Strategy

### Visual Testing Checklist

Test with each column count:

- [ ] **2 columns**: Minimal layout displays correctly
- [ ] **3 columns**: Default layout (backwards compatible)
- [ ] **4 columns**: Extra column fits
- [ ] **5 columns**: Getting crowded but readable
- [ ] **6 columns**: Maximum columns, ensure usable

For each:
- [ ] Columns render with correct titles
- [ ] Tasks appear in correct columns
- [ ] Navigation (h/l) works across all columns
- [ ] Task movement (H/L) respects column order
- [ ] Filter applies to all columns
- [ ] Empty column shows appropriate message

### Integration Tests

```python
class TestBoardScreenDynamic:
    def test_compose_default_columns(self, app: KosmosApp):
        """Default config creates 3 columns."""
        screen = BoardScreen()
        app.push_screen(screen)

        columns = screen.query(KanbanColumn)
        assert len(list(columns)) == 3

    def test_compose_custom_columns(self, app_with_custom_config: KosmosApp):
        """Custom config creates correct columns."""
        screen = BoardScreen()
        app_with_custom_config.push_screen(screen)

        columns = list(screen.query(KanbanColumn))
        assert len(columns) == 5  # Based on custom config

        # Check titles match config
        config = app_with_custom_config.config_service.get_board_config()
        for i, col in enumerate(columns):
            assert col.title == config.columns[i].title

    def test_navigation_custom_columns(self, app_with_custom_config: KosmosApp):
        """Navigation respects custom column count."""
        screen = BoardScreen()
        app_with_custom_config.push_screen(screen)

        # Start at first column
        assert screen._current_column_idx == 0

        # Navigate right through all columns
        for i in range(4):  # 5 columns, 4 moves
            screen.action_focus_right_column()
            assert screen._current_column_idx == i + 1

        # At last column, can't go further
        screen.action_focus_right_column()
        assert screen._current_column_idx == 4  # Still at last

    def test_load_tasks_custom_columns(self, app_with_custom_config: KosmosApp):
        """Tasks load into correct custom columns."""
        # Create tasks in custom states
        # Verify they appear in correct columns
        pass
```

### Unit Tests for KanbanColumn

```python
class TestKanbanColumnString:
    def test_state_is_string(self):
        col = KanbanColumn(title="Test", state="custom_state", id="test")
        assert col.state == "custom_state"
        assert isinstance(col.state, str)

    def test_css_id_generation(self):
        col = KanbanColumn(title="Test", state="in_progress", id="test")
        assert col._state_css_id == "in-progress"

    def test_css_id_no_change_needed(self):
        col = KanbanColumn(title="Test", state="todo", id="test")
        assert col._state_css_id == "todo"
```

## Verification Steps

1. Run `uv run pytest` - all tests pass
2. Start app without `sltasks.yml` - shows default 3 columns
3. Create `sltasks.yml` with 5 columns - app shows 5 columns
4. Navigate with h/l keys - moves through all columns
5. Move task with H/L keys - respects custom order
6. Create task - appears in first custom column
7. Filter by custom state - works correctly
8. Test with 2 columns - layout works
9. Test with 6 columns - layout works (may be crowded)

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|

## Completion Notes

**Phase 5 status: Pending**

## Key Notes

- Column generation is entirely driven by config
- Widget IDs use hyphenated version of state (CSS-safe)
- Navigation bounds checking uses `column_count` property
- State cycling wraps around to first column after last
- Empty column messages show state name (with underscores replaced)
- May need CSS tweaks for 5-6 column layouts
- `board_config` property provides easy access to config from screen
