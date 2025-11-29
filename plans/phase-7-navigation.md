# Phase 7: Keyboard Navigation

## Overview

This phase implements full keyboard navigation for the kanban board. Users will be able to move between columns and tasks using arrow keys or vim-style hjkl keys. The focus system will track the currently selected task and column.

## Goals

1. Implement column-level navigation (left/right)
2. Implement task-level navigation within columns (up/down)
3. Support both arrow keys and vim-style hjkl bindings
4. Maintain focus state across board refreshes
5. Handle edge cases (empty columns, single task, etc.)
6. Visual feedback for current selection

## Task Checklist

- [ ] Create navigation state management:
  - [ ] Track current column index
  - [ ] Track current task index within column
  - [ ] Handle focus persistence across refreshes
- [ ] Implement key bindings in `KosmosApp`:
  - [ ] `h` / `←` - Move to previous column
  - [ ] `l` / `→` - Move to next column
  - [ ] `k` / `↑` - Move to previous task
  - [ ] `j` / `↓` - Move to next task
  - [ ] `g` / `Home` - Jump to first task in column
  - [ ] `G` / `End` - Jump to last task in column
- [ ] Update `BoardScreen`:
  - [ ] Add focus management methods
  - [ ] `focus_column(index)` - Focus a column
  - [ ] `focus_task(column_index, task_index)` - Focus specific task
  - [ ] `get_current_task()` - Get currently focused task
- [ ] Update `KanbanColumn`:
  - [ ] Add `focused` property
  - [ ] Method to focus nth task
  - [ ] Return focused task
- [ ] Update `TaskCard`:
  - [ ] Ensure proper focus handling
  - [ ] Add `selected` class when focused
- [ ] Handle edge cases:
  - [ ] Empty columns (skip or show message)
  - [ ] Moving past first/last column
  - [ ] Moving past first/last task
  - [ ] Columns with different task counts
- [ ] Update CSS for focus states

## Detailed Specifications

### Navigation State

```python
@dataclass
class NavigationState:
    """Tracks current navigation position."""

    column_index: int = 0
    task_index: int = 0

    def reset(self) -> None:
        """Reset to initial state."""
        self.column_index = 0
        self.task_index = 0
```

### Key Bindings

```python
class KosmosApp(App):
    """Kosmos - Terminal Kanban TUI."""

    BINDINGS = [
        # Existing
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
```

### BoardScreen Navigation Methods

```python
class BoardScreen(Screen):
    """Main kanban board screen with navigation."""

    COLUMN_STATES = [TaskState.TODO, TaskState.IN_PROGRESS, TaskState.DONE]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_column = 0
        self._current_task = 0

    def navigate_column(self, delta: int) -> None:
        """Navigate between columns."""
        new_column = self._current_column + delta

        # Clamp to valid range
        new_column = max(0, min(new_column, len(self.COLUMN_STATES) - 1))

        if new_column != self._current_column:
            self._current_column = new_column
            # Clamp task index to new column's task count
            column = self._get_column(new_column)
            self._current_task = min(self._current_task, max(0, column.task_count - 1))
            self._update_focus()

    def navigate_task(self, delta: int) -> None:
        """Navigate between tasks in current column."""
        column = self._get_column(self._current_column)
        if column.task_count == 0:
            return

        new_task = self._current_task + delta
        new_task = max(0, min(new_task, column.task_count - 1))

        if new_task != self._current_task:
            self._current_task = new_task
            self._update_focus()

    def navigate_to_task(self, index: int) -> None:
        """Navigate to specific task index (-1 for last)."""
        column = self._get_column(self._current_column)
        if column.task_count == 0:
            return

        if index < 0:
            index = column.task_count - 1
        else:
            index = min(index, column.task_count - 1)

        self._current_task = index
        self._update_focus()

    def _get_column(self, index: int) -> KanbanColumn:
        """Get column widget by index."""
        state = self.COLUMN_STATES[index]
        column_id = f"column-{state.value.replace('_', '-')}"
        return self.query_one(f"#{column_id}", KanbanColumn)

    def _update_focus(self) -> None:
        """Update focus to current task."""
        column = self._get_column(self._current_column)
        column.focus_task(self._current_task)

    def get_current_task(self) -> Task | None:
        """Get the currently focused task."""
        column = self._get_column(self._current_column)
        return column.get_task(self._current_task)

    @property
    def current_column_state(self) -> TaskState:
        """Get the state of the current column."""
        return self.COLUMN_STATES[self._current_column]
```

### KanbanColumn Focus Methods

```python
class KanbanColumn(Widget):
    """A single column in the kanban board."""

    def focus_task(self, index: int) -> None:
        """Focus the task at the given index."""
        if not self._tasks or index < 0 or index >= len(self._tasks):
            return

        task = self._tasks[index]
        try:
            card = self.query_one(f"#task-{task.filename}", TaskCard)
            card.focus()
        except Exception:
            pass

    def get_task(self, index: int) -> Task | None:
        """Get task at index."""
        if 0 <= index < len(self._tasks):
            return self._tasks[index]
        return None

    def get_focused_task_index(self) -> int:
        """Get index of currently focused task, or -1."""
        for i, task in enumerate(self._tasks):
            try:
                card = self.query_one(f"#task-{task.filename}", TaskCard)
                if card.has_focus:
                    return i
            except Exception:
                pass
        return -1
```

## Navigation Behavior

### Column Navigation (h/l or ←/→)

```
┌─────────┐   ┌─────────┐   ┌─────────┐
│ To Do   │ → │ In Prog │ → │ Done    │
│  ←      │ ← │         │ ← │   →     │
└─────────┘   └─────────┘   └─────────┘
     ↑             ↑             ↑
  col 0         col 1         col 2

- Moving left from col 0 stays at col 0
- Moving right from col 2 stays at col 2
- Task index is preserved when possible
- If new column has fewer tasks, clamp to last task
```

### Task Navigation (j/k or ↑/↓)

```
Column with 3 tasks:

  ┌───────────┐
  │ Task 1    │  ← index 0 (k goes nowhere)
  └───────────┘
       ↓ j
  ┌───────────┐
  │ Task 2    │  ← index 1
  └───────────┘
       ↓ j
  ┌───────────┐
  │ Task 3    │  ← index 2 (j goes nowhere)
  └───────────┘

- Moving up from index 0 stays at 0
- Moving down from last index stays at last
- g/Home jumps to index 0
- G/End jumps to last index
```

### Empty Column Handling

When navigating to an empty column:
- Focus remains on the column header area
- Task navigation (j/k) does nothing
- Column navigation (h/l) still works

## CSS Updates

```css
/* Column focus state */
KanbanColumn.focused {
    border: solid $primary;
}

KanbanColumn.focused .column-header {
    background: $primary-darken-2;
}

/* Task focus state */
TaskCard:focus {
    background: $primary-darken-1;
    border: double $primary;
}

TaskCard:focus .task-title {
    color: $text;
    text-style: bold;
}
```

## Testing Notes

Manual testing scenarios:
1. Navigate through all columns with h/l
2. Navigate through tasks in a column with j/k
3. Navigate to empty column and back
4. Navigate when one column has more tasks than others
5. Use g/G to jump to first/last task
6. Refresh board (r) and verify focus is maintained
7. Test arrow keys work same as hjkl

## Deviations from Plan

_This section will be updated if implementation differs from the plan._

| Date | Deviation | Reason |
|------|-----------|--------|
| - | - | - |

## Key Notes

- Navigation wraps at boundaries (doesn't cycle)
- Focus state is visual only (doesn't affect scrolling yet)
- Empty columns are navigable but have no task selection
- Task index is clamped when moving to column with fewer tasks
- Focus should survive board refresh when possible
