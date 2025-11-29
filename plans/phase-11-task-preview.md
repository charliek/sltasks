# Phase 11: Task Preview Modal

## Overview

When the user presses Enter on a task, open a modal that displays the markdown file contents with syntax highlighting. The user can read/scroll through the content, and press 'e' to open in an external editor.

## Behavior

**User Flow:**
1. User selects a task on the kanban board
2. User presses Enter
3. Modal opens showing the full markdown file with syntax highlighting
4. User can scroll with up/down arrow keys if content is long
5. User presses 'e' → modal closes, external editor opens, returns to board after editing
6. User presses any other key (except arrows) → modal closes, returns to board

**Key Bindings in Modal:**
- `up/down/pageup/pagedown` - Scroll content
- `e` - Open in external editor, then return to board
- Any other key - Close modal and return to board

## Implementation

### Step 1: Create `TaskPreviewModal` widget

**File:** `src/kosmos/ui/widgets/task_preview_modal.py` (NEW)

```python
"""Task preview modal with syntax-highlighted markdown."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

from rich.syntax import Syntax as RichSyntax

from ...models import Task


class TaskPreviewModal(ModalScreen[bool]):
    """Modal for previewing task markdown with syntax highlighting.

    Returns True if user wants to edit in external editor, False otherwise.
    """

    DEFAULT_CSS = """
    TaskPreviewModal {
        align: center middle;
    }

    TaskPreviewModal > Vertical {
        width: 90%;
        height: 85%;
        max-width: 120;
        border: solid $primary;
        background: $surface;
        padding: 1;
    }

    TaskPreviewModal > Vertical > #title-bar {
        height: 1;
        width: 100%;
        background: $primary-darken-2;
        color: $text;
        text-align: center;
    }

    TaskPreviewModal > Vertical > #content {
        height: 1fr;
        overflow-y: auto;
    }

    TaskPreviewModal > Vertical > #footer-bar {
        height: 1;
        width: 100%;
        background: $surface-lighten-1;
        color: $text-muted;
        text-align: center;
    }
    """

    # Only define bindings for actions we handle - let other keys dismiss
    BINDINGS = [
        Binding("e", "edit_external", "Edit", show=False),
    ]

    # Keys that should scroll content, not dismiss
    SCROLL_KEYS = {"up", "down", "pageup", "pagedown", "home", "end"}

    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task = task

    def compose(self) -> ComposeResult:
        content = self._read_file_content()

        # Use Rich's Syntax for highlighting, displayed in a Static
        syntax = RichSyntax(
            content,
            "markdown",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )

        with Vertical():
            yield Static(self.task.display_title, id="title-bar")
            yield Static(syntax, id="content")
            yield Static("[e] Edit  [any key] Close", id="footer-bar")

    def _read_file_content(self) -> str:
        """Read the full file content including YAML front matter."""
        if self.task.filepath and self.task.filepath.exists():
            return self.task.filepath.read_text()
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
```

### Step 2: Export the new widget

**File:** `src/kosmos/ui/widgets/__init__.py`

Add `TaskPreviewModal` to the exports:
```python
from .task_preview_modal import TaskPreviewModal
```

### Step 3: Update app bindings and actions

**File:** `src/kosmos/app.py`

**Change the Enter binding** - make it call a new preview action:
```python
# Change from:
Binding("enter", "edit_task", "Edit", show=False),

# To:
Binding("enter", "preview_task", "Preview", show=False),
```

**Add new action for preview:**
```python
def action_preview_task(self) -> None:
    """Show task preview modal."""
    screen = self.screen
    if not isinstance(screen, BoardScreen):
        return

    task = screen.get_current_task()
    if task is None:
        return

    self.push_screen(
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
```

**Keep `action_edit_task()` as-is** - 'e' key on board still opens editor directly.

### Step 4: Add import in app.py

```python
from .ui.widgets import CommandBar, ConfirmModal, HelpScreen, TaskPreviewModal
```

## Files to Modify

| File | Action |
|------|--------|
| `src/kosmos/ui/widgets/task_preview_modal.py` | CREATE - New modal widget |
| `src/kosmos/ui/widgets/__init__.py` | EDIT - Add export |
| `src/kosmos/app.py` | EDIT - Add binding, action, callback, import |

## Key Design Decisions

1. **Use Rich's Syntax class** instead of Textual's Syntax widget - Rich's Syntax renders to a Rich object that can be displayed in a Static widget inside a scrollable container.

2. **Static inside Vertical** - The Vertical container provides scrolling. The Static displays the syntax-highlighted content.

3. **SCROLL_KEYS check in on_key** - Allows arrow keys to scroll while other keys dismiss, following the HelpScreen pattern.

4. **ModalScreen[bool] return type** - Returns True to signal "edit requested", False for "just close".

5. **Keep 'e' binding on board** - Pressing 'e' on the board still opens editor directly (no preview). Enter shows preview first.

## Testing

1. Select a task and press Enter - modal should open
2. Modal shows full markdown with syntax highlighting (colors for headers, code, etc.)
3. Up/down arrows scroll the content if it's long
4. Press 'e' - modal closes, editor opens, returns to board after editing
5. Press any other key (q, Escape, space, etc.) - modal closes
6. Pressing 'e' on the board (not in modal) still opens editor directly
