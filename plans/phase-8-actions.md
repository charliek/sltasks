# Phase 8: Task Actions

## Overview

This phase implements the core actions users can perform on tasks: creating new tasks, editing existing tasks, moving tasks between columns, and archiving/deleting tasks. These actions build on the navigation system from Phase 7.

## Goals

1. Create new tasks via keyboard shortcut
2. Edit tasks in external editor
3. Move tasks between columns (left/right state transitions)
4. Move tasks within columns (up/down reordering)
5. Archive and delete tasks
6. Quick state toggle (cycle through states)

## Task Checklist

- [ ] Add action key bindings in `KosmosApp`:
  - [ ] `n` - Create new task
  - [ ] `e` / `Enter` - Edit current task
  - [ ] `m` - Move mode (then h/l to move between columns)
  - [ ] `H` / `Shift+←` - Move task to previous column
  - [ ] `L` / `Shift+→` - Move task to next column
  - [ ] `K` / `Shift+↑` - Move task up in column
  - [ ] `J` / `Shift+↓` - Move task down in column
  - [ ] `a` - Archive current task
  - [ ] `d` - Delete current task (with confirmation)
  - [ ] `Space` - Quick state toggle
- [ ] Implement task creation:
  - [ ] Open editor with template
  - [ ] Parse created file
  - [ ] Add to board and refresh
- [ ] Implement task editing:
  - [ ] Open current task in editor
  - [ ] Reload task after editor closes
  - [ ] Refresh board display
- [ ] Implement column movement:
  - [ ] Use BoardService.move_task_left/right
  - [ ] Update focus to follow task
  - [ ] Handle edge cases (already at first/last column)
- [ ] Implement within-column reordering:
  - [ ] Add reorder_task method to BoardService
  - [ ] Update board order file
  - [ ] Maintain focus on moved task
- [ ] Implement archive action:
  - [ ] Use BoardService.archive_task
  - [ ] Move focus to next task or previous
  - [ ] Show brief notification
- [ ] Implement delete action:
  - [ ] Show confirmation modal
  - [ ] Use TaskService.delete_task
  - [ ] Update board and focus
- [ ] Add confirmation modal widget:
  - [ ] Simple yes/no dialog
  - [ ] Keyboard navigable (y/n or Enter/Escape)

## Detailed Specifications

### Key Bindings

```python
class KosmosApp(App):
    """Kosmos - Terminal Kanban TUI."""

    BINDINGS = [
        # Existing
        Binding("q", "quit", "Quit", show=True),
        Binding("?", "help", "Help", show=True),
        Binding("r", "refresh", "Refresh", show=True),

        # Navigation (from Phase 7)
        Binding("h", "nav_left", "← Column", show=False),
        Binding("j", "nav_down", "↓ Task", show=False),
        Binding("k", "nav_up", "↑ Task", show=False),
        Binding("l", "nav_right", "→ Column", show=False),
        # ... arrow keys ...

        # Actions
        Binding("n", "new_task", "New", show=True),
        Binding("e", "edit_task", "Edit", show=True),
        Binding("enter", "edit_task", "Edit", show=False),
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
    ]
```

### Action Implementations

```python
class KosmosApp(App):

    def action_new_task(self) -> None:
        """Create a new task."""
        # Create task with default template
        task = self.task_service.create_task(
            title="New Task",
            state=self.query_one(BoardScreen).current_column_state,
        )

        # Open in editor
        self.task_service.open_in_editor(task, self.settings.editor)

        # Reload and refresh
        self.repository.reload()
        self.query_one(BoardScreen).load_tasks()

    def action_edit_task(self) -> None:
        """Edit the current task in external editor."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        # Suspend TUI and open editor
        with self.suspend():
            self.task_service.open_in_editor(task, self.settings.editor)

        # Reload and refresh
        self.repository.reload()
        screen.load_tasks()

    def action_move_task_left(self) -> None:
        """Move current task to previous column."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        result = self.board_service.move_task_left(task)
        if result:
            screen.load_tasks()
            # Focus follows task to new column
            screen.navigate_column(-1)

    def action_move_task_right(self) -> None:
        """Move current task to next column."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        result = self.board_service.move_task_right(task)
        if result:
            screen.load_tasks()
            # Focus follows task to new column
            screen.navigate_column(1)

    def action_move_task_up(self) -> None:
        """Move current task up in column."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        self.board_service.reorder_task(task, -1)
        screen.load_tasks()
        screen.navigate_task(-1)

    def action_move_task_down(self) -> None:
        """Move current task down in column."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        self.board_service.reorder_task(task, 1)
        screen.load_tasks()
        screen.navigate_task(1)

    def action_archive_task(self) -> None:
        """Archive the current task."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        self.board_service.archive_task(task)
        screen.load_tasks()
        self.notify("Task archived", timeout=2)

    def action_delete_task(self) -> None:
        """Delete the current task (with confirmation)."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        # Show confirmation modal
        self.push_screen(
            ConfirmModal(f"Delete '{task.display_title}'?"),
            callback=self._handle_delete_confirm,
        )

    def _handle_delete_confirm(self, confirmed: bool) -> None:
        """Handle delete confirmation result."""
        if not confirmed:
            return

        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task:
            self.task_service.delete_task(task)
            screen.load_tasks()
            self.notify("Task deleted", timeout=2)

    def action_toggle_state(self) -> None:
        """Toggle task state: todo -> in_progress -> done -> todo."""
        screen = self.query_one(BoardScreen)
        task = screen.get_current_task()

        if task is None:
            return

        # Cycle through states
        state_cycle = {
            TaskState.TODO: TaskState.IN_PROGRESS,
            TaskState.IN_PROGRESS: TaskState.DONE,
            TaskState.DONE: TaskState.TODO,
        }

        new_state = state_cycle.get(task.state, TaskState.TODO)
        self.board_service.move_task(task, new_state)
        screen.load_tasks()
```

### BoardService Additions

```python
class BoardService:
    """Service for managing board state."""

    def reorder_task(self, task: Task, delta: int) -> bool:
        """
        Reorder task within its column.

        Args:
            task: Task to reorder
            delta: -1 to move up, 1 to move down

        Returns:
            True if task was moved
        """
        board_order = self.repository.get_board_order()
        column = board_order.columns.get(task.state.value, [])

        if task.filename not in column:
            return False

        current_idx = column.index(task.filename)
        new_idx = current_idx + delta

        # Check bounds
        if new_idx < 0 or new_idx >= len(column):
            return False

        # Swap positions
        column[current_idx], column[new_idx] = column[new_idx], column[current_idx]

        # Save updated order
        self.repository.save_board_order(board_order)
        return True
```

### Confirmation Modal

```python
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmModal(ModalScreen[bool]):
    """Modal dialog for confirming destructive actions."""

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    ConfirmModal > Vertical {
        width: 50;
        height: auto;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    ConfirmModal Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
    }

    ConfirmModal .buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    ConfirmModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(self.message)
            with Center(classes="buttons"):
                yield Button("Yes", id="yes", variant="error")
                yield Button("No", id="no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
```

### Task Template

When creating a new task, use this template:

```python
TASK_TEMPLATE = """---
title: "{title}"
state: {state}
priority: medium
tags: []
created: {created}
updated: {updated}
---

## Description

Describe the task here.

## Acceptance Criteria

- [ ] First criterion
- [ ] Second criterion
"""
```

## State Transition Diagram

```
     ┌──────────────────────────────────────────────────────┐
     │                                                      │
     ▼                                                      │
┌─────────┐  move_right (L)  ┌─────────────┐  move_right (L)  ┌──────┐
│  TODO   │ ───────────────► │ IN_PROGRESS │ ───────────────► │ DONE │
└─────────┘                  └─────────────┘                  └──────┘
     ▲                              │                            │
     │       move_left (H)          │      move_left (H)         │
     └──────────────────────────────┴────────────────────────────┘

     Any state can be archived with 'a':

     ┌──────────┐
     │ ARCHIVED │
     └──────────┘
```

## Visual Feedback

When actions are performed, provide brief visual feedback:

```
┌──────────────────────────────────────────────────────────────┐
│ Kosmos                                              [NOTIFY] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │
│ │ To Do (2)   │ │ In Prog (1) │ │ Done (2)    │             │
│ └─────────────┘ └─────────────┘ └─────────────┘             │
│                                                              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Task moved to In Progress                          [2s left] │
└──────────────────────────────────────────────────────────────┘
```

## Editor Integration

The `open_in_editor` method uses `App.suspend()` to temporarily pause the TUI:

```python
def open_in_editor(self, task: Task, editor: str) -> None:
    """Open task file in external editor."""
    import subprocess

    if task.filepath is None:
        raise ValueError("Task has no filepath")

    subprocess.run([editor, str(task.filepath)])
```

## Testing Notes

Manual testing scenarios:
1. Create new task with `n`, verify it appears in current column
2. Edit task with `e`, modify title, verify changes appear
3. Move task right with `L`, verify it moves to next column
4. Move task left with `H`, verify it moves to previous column
5. Reorder task with `J`/`K`, verify order changes
6. Archive task with `a`, verify it disappears
7. Delete task with `d`, verify confirmation appears
8. Cancel delete with `n` or Escape, verify task remains
9. Confirm delete with `y`, verify task is removed
10. Use Space to cycle through states

## Deviations from Plan

_This section will be updated if implementation differs from the plan._

| Date | Deviation | Reason |
|------|-----------|--------|
| - | - | - |

## Key Notes

- External editor is opened with `App.suspend()` to properly pause TUI
- Delete requires confirmation to prevent accidental data loss
- Move actions wrap at boundaries (no cycling)
- Archive is a soft delete (task still exists but hidden)
- Focus follows task when moving between columns
- Notifications use Textual's built-in `notify()` method
- Task template includes placeholder content for new tasks
