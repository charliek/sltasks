# Phase 10: Help Screen

## Overview

This phase implements a help screen that displays all available keyboard shortcuts and commands. The help screen is accessible via `?` and provides a quick reference for users.

## Goals

1. Create help screen with keyboard shortcuts
2. Organize shortcuts by category
3. Show filter syntax reference
4. Make help dismissible with any key
5. Include version information

## Task Checklist

- [ ] Create `HelpScreen` modal:
  - [ ] Display all keyboard shortcuts
  - [ ] Organize by category (Navigation, Actions, etc.)
  - [ ] Show filter syntax reference
  - [ ] Version information at bottom
- [ ] Update `action_help()` in `KosmosApp`:
  - [ ] Push help screen as modal
  - [ ] Dismiss on any key press
- [ ] Style the help screen:
  - [ ] Centered modal dialog
  - [ ] Clear typography hierarchy
  - [ ] Muted secondary text
- [ ] Add dynamic binding collection (optional):
  - [ ] Collect bindings from app
  - [ ] Auto-generate help content

## Detailed Specifications

### HelpScreen Widget

```python
from textual.app import ComposeResult
from textual.containers import Center, Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Static
from textual.binding import Binding


class HelpScreen(ModalScreen):
    """Modal help screen showing keyboard shortcuts."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }

    HelpScreen > Vertical {
        width: 70;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    HelpScreen .help-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        border-bottom: solid $primary-darken-2;
    }

    HelpScreen .help-section {
        padding: 1 0;
    }

    HelpScreen .section-title {
        text-style: bold;
        color: $primary;
    }

    HelpScreen .help-row {
        height: 1;
    }

    HelpScreen .help-key {
        width: 15;
        text-style: bold;
    }

    HelpScreen .help-desc {
        width: 1fr;
        color: $text-muted;
    }

    HelpScreen .help-footer {
        text-align: center;
        color: $text-muted;
        padding-top: 1;
        border-top: solid $primary-darken-2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("?", "dismiss", "Close", show=False),
        Binding("q", "dismiss", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("⌨ Keyboard Shortcuts", classes="help-title")

            # Navigation section
            with Vertical(classes="help-section"):
                yield Static("Navigation", classes="section-title")
                yield from self._help_rows([
                    ("h / ←", "Previous column"),
                    ("l / →", "Next column"),
                    ("k / ↑", "Previous task"),
                    ("j / ↓", "Next task"),
                    ("g / Home", "First task in column"),
                    ("G / End", "Last task in column"),
                ])

            # Actions section
            with Vertical(classes="help-section"):
                yield Static("Actions", classes="section-title")
                yield from self._help_rows([
                    ("n", "Create new task"),
                    ("e / Enter", "Edit current task"),
                    ("H / Shift+←", "Move task left"),
                    ("L / Shift+→", "Move task right"),
                    ("J / Shift+↓", "Move task down"),
                    ("K / Shift+↑", "Move task up"),
                    ("Space", "Toggle task state"),
                    ("a", "Archive task"),
                    ("d", "Delete task"),
                ])

            # Filter section
            with Vertical(classes="help-section"):
                yield Static("Filter", classes="section-title")
                yield from self._help_rows([
                    ("/", "Enter filter mode"),
                    ("Escape", "Clear filter / Cancel"),
                ])

            # Filter syntax section
            with Vertical(classes="help-section"):
                yield Static("Filter Syntax", classes="section-title")
                yield from self._help_rows([
                    ("text", "Search in title/body"),
                    ("tag:name", "Filter by tag"),
                    ("-tag:name", "Exclude tag"),
                    ("state:todo", "Filter by state"),
                    ("priority:high", "Filter by priority"),
                ])

            # General section
            with Vertical(classes="help-section"):
                yield Static("General", classes="section-title")
                yield from self._help_rows([
                    ("r", "Refresh board"),
                    ("?", "Show this help"),
                    ("q", "Quit"),
                ])

            yield Static("Press any key to close • Kosmos v0.1.0", classes="help-footer")

    def _help_rows(self, items: list[tuple[str, str]]) -> list[Horizontal]:
        """Generate help row widgets."""
        rows = []
        for key, desc in items:
            row = Horizontal(classes="help-row")
            row.compose_add_child(Static(key, classes="help-key"))
            row.compose_add_child(Static(desc, classes="help-desc"))
            rows.append(row)
        return rows

    def on_key(self, event) -> None:
        """Dismiss on any key."""
        self.dismiss()
```

### App Integration

```python
class KosmosApp(App):

    def action_help(self) -> None:
        """Show help screen."""
        self.push_screen(HelpScreen())
```

## Visual Design

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                      │
│                    ┌────────────────────────────┐                    │
│                    │   ⌨ Keyboard Shortcuts     │                    │
│                    ├────────────────────────────┤                    │
│                    │                            │                    │
│                    │ Navigation                 │                    │
│                    │ h / ←      Previous column │                    │
│                    │ l / →      Next column     │                    │
│                    │ k / ↑      Previous task   │                    │
│                    │ j / ↓      Next task       │                    │
│                    │ g / Home   First task      │                    │
│                    │ G / End    Last task       │                    │
│                    │                            │                    │
│                    │ Actions                    │                    │
│                    │ n          Create new task │                    │
│                    │ e / Enter  Edit task       │                    │
│                    │ H / L      Move task h/l   │                    │
│                    │ J / K      Move task j/k   │                    │
│                    │ Space      Toggle state    │                    │
│                    │ a          Archive         │                    │
│                    │ d          Delete          │                    │
│                    │                            │                    │
│                    │ General                    │                    │
│                    │ /          Filter          │                    │
│                    │ r          Refresh         │                    │
│                    │ ?          Help            │                    │
│                    │ q          Quit            │                    │
│                    │                            │                    │
│                    │ Press any key to close     │                    │
│                    └────────────────────────────┘                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Alternative: DataTable-based Help

For easier row management, consider using a DataTable:

```python
from textual.widgets import DataTable

class HelpScreen(ModalScreen):

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("⌨ Keyboard Shortcuts", classes="help-title")

            table = DataTable(show_header=False, cursor_type="none")
            table.add_columns("Key", "Description")

            # Add rows by category
            table.add_row("[bold]Navigation[/]", "", key="nav-header")
            table.add_row("h / ←", "Previous column")
            table.add_row("l / →", "Next column")
            # ... more rows ...

            yield table

            yield Static("Press any key to close", classes="help-footer")
```

## Testing Notes

Manual testing scenarios:
1. Press `?` to open help
2. Verify all shortcuts are listed
3. Press any key to close
4. Press Escape to close
5. Verify help shows correct bindings
6. Check visual appearance and alignment

## Deviations from Plan

_This section will be updated if implementation differs from the plan._

| Date | Deviation | Reason |
|------|-----------|--------|
| - | - | - |

## Key Notes

- Help screen is a modal that overlays the board
- Any key dismisses the help (not just Escape)
- Shortcuts are organized by category for scannability
- Filter syntax is included as a quick reference
- Version info shown at bottom
- Consider collecting bindings dynamically from App.BINDINGS in future
