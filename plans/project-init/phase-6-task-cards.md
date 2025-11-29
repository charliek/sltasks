# Phase 6: Task Cards Enhancement

## Overview

This phase enhances the task card display with better visual hierarchy, selection state, and improved information density. We'll add visual indicators for task state, improve the tag display, and prepare the cards for keyboard navigation.

## Goals

1. Improve task card visual design and information display
2. Add selection/focus state styling for cards
3. Display timestamps (created/updated) on hover or detail view
4. Add visual indicators for state within cards
5. Improve tag display with color coding
6. Add task count badges to column headers

## Task Checklist

- [x] Enhance `TaskCard` widget:
  - [x] Improve layout with better spacing
  - [x] Add focus/selected visual state (border highlight)
  - [x] Show truncated body preview (first line)
  - [ ] Add created/updated timestamp display (deferred)
  - [x] Handle long titles with ellipsis
- [x] Improve priority indicators:
  - [x] Use colored symbols consistently
  - [x] Add priority label text
- [x] Enhance tag display:
  - [x] Style tags as chips/badges
  - [x] Limit visible tags with "+N more" indicator
  - [x] Add default tag colors
- [x] Update column headers:
  - [x] Add task count badges
  - [x] Style count distinctly from title
- [x] Update CSS styles:
  - [x] Focus state styling
  - [x] Tag chip styling
  - [ ] Timestamp styling (muted) (deferred)
  - [x] Hover effects
- [x] Add empty state display:
  - [x] Show "No tasks" message in empty columns

## Detailed Specifications

### Enhanced TaskCard Widget

```python
"""Enhanced task card widget."""

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from ...models import Priority, Task


class TaskCard(Widget, can_focus=True):
    """A task card displayed in a column."""

    PRIORITY_DISPLAY = {
        Priority.CRITICAL: ("●", "red", "critical"),
        Priority.HIGH: ("●", "orange1", "high"),
        Priority.MEDIUM: ("●", "yellow", "medium"),
        Priority.LOW: ("●", "green", "low"),
    }

    def __init__(self, task: Task, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.task = task

    def compose(self) -> ComposeResult:
        """Create card layout."""
        # Title with truncation
        title = self._truncate(self.task.display_title, 40)
        yield Static(title, classes="task-title")

        # Priority line
        symbol, color, label = self.PRIORITY_DISPLAY.get(
            self.task.priority, ("●", "white", "medium")
        )
        priority_text = f"[{color}]{symbol}[/] {label}"
        yield Static(priority_text, classes="task-priority")

        # Tags as chips
        if self.task.tags:
            yield Static(self._format_tags(), classes="task-tags")

        # Body preview (first non-empty line)
        if self.task.body.strip():
            preview = self._get_body_preview()
            if preview:
                yield Static(preview, classes="task-preview")

    def _truncate(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 1] + "…"

    def _format_tags(self) -> str:
        """Format tags for display."""
        max_tags = 3
        tags = self.task.tags[:max_tags]
        formatted = " ".join(f"[dim]#{tag}[/]" for tag in tags)

        if len(self.task.tags) > max_tags:
            extra = len(self.task.tags) - max_tags
            formatted += f" [dim]+{extra}[/]"

        return formatted

    def _get_body_preview(self) -> str:
        """Get first non-empty, non-heading line of body."""
        for line in self.task.body.split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                return self._truncate(line, 50)
        return ""
```

### Updated CSS Styles

```css
/* Enhanced task card styles */
TaskCard {
    height: auto;
    min-height: 3;
    max-height: 8;
    margin-bottom: 1;
    padding: 0 1;
    background: $surface;
    border: solid $primary-darken-3;
}

TaskCard:hover {
    background: $surface-lighten-1;
    border: solid $primary-darken-1;
}

TaskCard:focus {
    background: $primary-darken-2;
    border: double $primary;
}

.task-title {
    text-style: bold;
    width: 100%;
}

.task-priority {
    height: 1;
}

.task-tags {
    height: 1;
    color: $text-muted;
}

.task-preview {
    height: 1;
    color: $text-muted;
    text-style: italic;
}

/* Empty column state */
.empty-column {
    text-align: center;
    color: $text-muted;
    padding: 2;
    text-style: italic;
}

/* Column header with count */
.column-header {
    height: 3;
    padding: 1;
    background: $surface;
    text-align: center;
    border-bottom: solid $primary-darken-2;
}

.column-count {
    color: $text-muted;
}
```

### Empty State Widget

```python
class EmptyColumnMessage(Static):
    """Displayed when a column has no tasks."""

    DEFAULT_CSS = """
    EmptyColumnMessage {
        text-align: center;
        color: $text-muted;
        padding: 2;
        text-style: italic;
        width: 100%;
    }
    """

    def __init__(self, state_name: str) -> None:
        super().__init__(f"No {state_name} tasks")
```

### Column Header Update

```python
@property
def _header_text(self) -> str:
    """Header text with styled task count."""
    count = len(self._tasks)
    return f"{self.title} [dim]({count})[/]"
```

## Visual Design

```
┌─────────────────────────────────────────────────────────────────────┐
│  Kosmos                                                              │
├───────────────────┬───────────────────┬───────────────────┬─────────┤
│ To Do [dim](2)[/] │ In Progress (1)   │ Done (2)          │         │
├───────────────────┼───────────────────┼───────────────────┤         │
│                   │                   │                   │         │
│ ┌───────────────┐ │ ┌───────────────┐ │ ┌───────────────┐ │         │
│ │ Fix login bug │ │ │ Refactor API  │ │ │ Setup CI      │ │         │
│ │ ● high        │ │ │ ● medium      │ │ │ ● low         │ │         │
│ │ #bug #auth    │ │ │ #backend      │ │ │ #devops       │ │         │
│ │ Users are...  │ │ │ Modernize...  │ │ │               │ │         │
│ └───────────────┘ │ └───────────────┘ │ └───────────────┘ │         │
│                   │                   │                   │         │
│ ┌───────────────┐ │                   │ ┌───────────────┐ │         │
│ │ Add dark mode │ │                   │ │ Write docs    │ │         │
│ │ ● medium      │ │                   │ │ ● medium      │ │         │
│ │ #feature #ui  │ │                   │ │ #docs         │ │         │
│ └───────────────┘ │                   │ └───────────────┘ │         │
│                   │                   │                   │         │
└───────────────────┴───────────────────┴───────────────────┴─────────┘
│ q Quit  ? Help  r Refresh                                            │
└─────────────────────────────────────────────────────────────────────┘
```

## Testing Notes

Manual testing:
- Verify focus state is visually distinct
- Test with tasks that have very long titles
- Test with tasks that have many tags (5+)
- Test with empty body vs body with content
- Verify empty column shows placeholder message
- Test column count updates when tasks change

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|
| 2025-11-28 | Timestamp display deferred | Adds visual clutter; can be added in detail view later |
| 2025-11-28 | EmptyColumnMessage is separate class (not embedded CSS) | Follows pattern of using .tcss file for styles |

## Completion Notes

**Phase 6 completed on 2025-11-28**

Files modified:
- `src/kosmos/ui/widgets/task_card.py` - Enhanced with truncation, body preview, improved tag display
- `src/kosmos/ui/widgets/column.py` - Added EmptyColumnMessage, styled header count
- `src/kosmos/ui/widgets/__init__.py` - Exported EmptyColumnMessage
- `src/kosmos/ui/styles.tcss` - Added focus, hover, empty state, and preview styles

Verification:
- All 61 tests passing
- App initializes correctly
- TaskCard displays title, priority with color, tags as #chips, body preview
- Empty columns show "No {state} tasks" message
- Column headers show styled task count: "To Do (2)"
- Focus state uses double border for visibility
- Hover effects provide visual feedback

## Key Notes

- TaskCard remains focusable for Phase 7 navigation
- Body preview only shows first meaningful line (skips headings)
- Tag display uses Rich markup for styling
- Focus state uses double border for visibility
- Max height prevents cards from becoming too tall
