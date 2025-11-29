"""Board state models."""

from pydantic import BaseModel, Field

from .enums import TaskState
from .task import Task


class BoardOrder(BaseModel):
    """Represents the ordering of tasks in tasks.yaml."""

    version: int = 1
    columns: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "todo": [],
            "in_progress": [],
            "done": [],
            "archived": [],
        }
    )

    def get_position(self, filename: str, state: str) -> int:
        """Get position of task in its column, or -1 if not found."""
        column = self.columns.get(state, [])
        try:
            return column.index(filename)
        except ValueError:
            return -1

    def add_task(self, filename: str, state: str, position: int = -1) -> None:
        """Add task to column at position (-1 = end)."""
        if state not in self.columns:
            self.columns[state] = []

        # Remove from any existing column first
        self.remove_task(filename)

        if position < 0:
            self.columns[state].append(filename)
        else:
            self.columns[state].insert(position, filename)

    def remove_task(self, filename: str) -> None:
        """Remove task from all columns."""
        for column in self.columns.values():
            if filename in column:
                column.remove(filename)

    def move_task(
        self, filename: str, from_state: str, to_state: str, position: int = -1
    ) -> None:
        """Move task between columns."""
        self.remove_task(filename)
        self.add_task(filename, to_state, position)


class Board(BaseModel):
    """Full board state with tasks grouped by column."""

    todo: list[Task] = Field(default_factory=list)
    in_progress: list[Task] = Field(default_factory=list)
    done: list[Task] = Field(default_factory=list)
    archived: list[Task] = Field(default_factory=list)

    @classmethod
    def from_tasks(cls, tasks: list[Task]) -> "Board":
        """Create Board from a list of tasks, grouping by state."""
        board = cls()
        for task in tasks:
            match task.state:
                case TaskState.TODO:
                    board.todo.append(task)
                case TaskState.IN_PROGRESS:
                    board.in_progress.append(task)
                case TaskState.DONE:
                    board.done.append(task)
                case TaskState.ARCHIVED:
                    board.archived.append(task)
        return board

    def get_column(self, state: TaskState) -> list[Task]:
        """Get tasks for a specific state."""
        match state:
            case TaskState.TODO:
                return self.todo
            case TaskState.IN_PROGRESS:
                return self.in_progress
            case TaskState.DONE:
                return self.done
            case TaskState.ARCHIVED:
                return self.archived

    @property
    def visible_columns(self) -> list[tuple[TaskState, list[Task]]]:
        """Get non-archived columns in display order."""
        return [
            (TaskState.TODO, self.todo),
            (TaskState.IN_PROGRESS, self.in_progress),
            (TaskState.DONE, self.done),
        ]
