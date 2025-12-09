"""Type selector modal for task creation."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from ...models.sltasks_config import TypeConfig


class TypeSelectorModal(ModalScreen[str | None]):
    """Modal dialog for selecting task type when creating a new task."""

    DEFAULT_CSS = """
    TypeSelectorModal {
        align: center middle;
    }

    TypeSelectorModal > Vertical {
        width: 40;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        background: $surface;
        border: solid $primary;
    }

    TypeSelectorModal Label {
        width: 100%;
        text-align: center;
        margin-bottom: 1;
        text-style: bold;
    }

    TypeSelectorModal OptionList {
        height: auto;
        max-height: 10;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "select", "Select", show=False),
    ]

    def __init__(self, types: list[TypeConfig]) -> None:
        """Initialize the type selector.

        Args:
            types: List of type configurations to display
        """
        super().__init__()
        self._types = types

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("Select Task Type")
            option_list = OptionList(id="type-list")
            for t in self._types:
                # Display with colored bullet
                label = f"[{t.color}]●[/] {t.id}"
                option_list.add_option(Option(label, id=t.id))
            # Add "None" option for tasks without type
            option_list.add_option(Option("[dim]●[/] (no type)", id="__none__"))
            yield option_list

    def on_mount(self) -> None:
        """Focus the option list on mount."""
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle option selection via click or enter."""
        selected_id = event.option.id
        self.dismiss(None if selected_id == "__none__" else selected_id)

    def action_cancel(self) -> None:
        """Cancel selection."""
        self.dismiss(None)

    def action_select(self) -> None:
        """Confirm current selection."""
        option_list = self.query_one(OptionList)
        highlighted = option_list.highlighted
        if highlighted is not None:
            option = option_list.get_option_at_index(highlighted)
            selected_id = option.id
            self.dismiss(None if selected_id == "__none__" else selected_id)
        else:
            # No selection - treat as cancel
            self.dismiss(None)
