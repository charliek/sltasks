"""Service for board state management."""

from ..models import Board, BoardOrder, Task, TaskState
from ..repositories import FilesystemRepository
from ..utils import now_utc


class BoardService:
    """Service for board state management."""

    def __init__(self, repository: FilesystemRepository) -> None:
        self.repository = repository

    def load_board(self) -> Board:
        """Load the full board with all tasks grouped by state."""
        tasks = self.repository.get_all()
        return Board.from_tasks(tasks)

    def get_tasks_by_state(self, state: TaskState) -> list[Task]:
        """Get all tasks in a specific state."""
        tasks = self.repository.get_all()
        return [t for t in tasks if t.state == state]

    def move_task(self, filename: str, to_state: TaskState) -> Task | None:
        """
        Move a task to a different state/column.

        Updates both the task file and the board order.
        """
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        task.state = to_state
        task.updated = now_utc()

        # Save updates the file and yaml
        self.repository.save(task)

        return task

    def move_task_left(self, filename: str) -> Task | None:
        """Move task to the previous column (e.g., in_progress -> todo)."""
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        new_state = self._previous_state(task.state)
        if new_state is None:
            return task  # Already at leftmost column

        return self.move_task(filename, new_state)

    def move_task_right(self, filename: str) -> Task | None:
        """Move task to the next column (e.g., todo -> in_progress)."""
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        new_state = self._next_state(task.state)
        if new_state is None:
            return task  # Already at rightmost column

        return self.move_task(filename, new_state)

    def archive_task(self, filename: str) -> Task | None:
        """Move a task to the archived state."""
        return self.move_task(filename, TaskState.ARCHIVED)

    def get_board_order(self) -> BoardOrder:
        """Get the current board order."""
        return self.repository.get_board_order()

    def save_board_order(self, order: BoardOrder) -> None:
        """Save the board order."""
        self.repository.save_board_order(order)

    def reload(self) -> None:
        """Reload board state from filesystem."""
        self.repository.reload()

    def _previous_state(self, state: TaskState) -> TaskState | None:
        """Get the previous state in the workflow."""
        order = [TaskState.TODO, TaskState.IN_PROGRESS, TaskState.DONE]
        try:
            idx = order.index(state)
            if idx > 0:
                return order[idx - 1]
        except ValueError:
            pass
        return None

    def _next_state(self, state: TaskState) -> TaskState | None:
        """Get the next state in the workflow."""
        order = [TaskState.TODO, TaskState.IN_PROGRESS, TaskState.DONE]
        try:
            idx = order.index(state)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            pass
        return None
