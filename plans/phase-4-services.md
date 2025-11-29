# Phase 4: Service Layer

## Overview

This phase implements the service layer that contains business logic and orchestrates operations between the TUI and repository layers. Services handle task CRUD, board state management, and filter parsing. They provide a clean interface for the UI layer.

## Goals

1. Implement TaskService for task CRUD operations
2. Implement BoardService for board state and task movement
3. Implement FilterService for parsing and applying filters
4. Keep business logic out of the repository and UI layers

## Task Checklist

- [x] Create `src/kosmos/services/task_service.py`:
  - [x] `TaskService` class
  - [x] `create_task(title: str) -> Task` - create new task
  - [x] `update_task(task: Task) -> Task` - save changes
  - [x] `delete_task(filename: str) -> None` - remove task
  - [x] `get_task(filename: str) -> Task | None` - get single task
  - [x] `get_all_tasks() -> list[Task]` - get all tasks
  - [x] `open_in_editor(task: Task) -> bool` - launch $EDITOR
  - [x] `_unique_filename()` - handle filename collisions
- [x] Create `src/kosmos/services/board_service.py`:
  - [x] `BoardService` class
  - [x] `load_board() -> Board` - load full board state
  - [x] `move_task(filename: str, to_state: TaskState) -> Task | None`
  - [x] `move_task_left(filename: str) -> Task | None`
  - [x] `move_task_right(filename: str) -> Task | None`
  - [x] `archive_task(filename: str) -> Task | None`
  - [x] `get_tasks_by_state(state: TaskState) -> list[Task]`
  - [x] `get_board_order() -> BoardOrder`
  - [x] `save_board_order(order: BoardOrder) -> None`
  - [x] `reload() -> None`
- [x] Create `src/kosmos/services/filter_service.py`:
  - [x] `Filter` dataclass
  - [x] `FilterService` class
  - [x] `parse(expr: str) -> Filter`
  - [x] `apply(tasks: list[Task], filter_: Filter) -> list[Task]`
- [x] `Board` model already created in Phase 2 (models/board.py)
- [x] Update `src/kosmos/services/__init__.py` with exports
- [x] Write tests for filter parsing - 29 tests passing

## Detailed Specifications

### TaskService (services/task_service.py)

```python
import os
import subprocess
from pathlib import Path

from ..models import Task, TaskState, Priority
from ..repositories import FilesystemRepository
from ..utils.slug import generate_filename
from ..utils.datetime import now_utc


class TaskService:
    """Service for task CRUD operations."""

    def __init__(self, repository: FilesystemRepository) -> None:
        self.repository = repository

    def create_task(
        self,
        title: str,
        state: TaskState = TaskState.TODO,
        priority: Priority = Priority.MEDIUM,
        tags: list[str] | None = None,
    ) -> Task:
        """
        Create a new task with the given title.

        Generates a filename from the title and creates the file.
        """
        filename = generate_filename(title)

        # Handle filename collision
        filename = self._unique_filename(filename)

        now = now_utc()
        task = Task(
            filename=filename,
            title=title,
            state=state,
            priority=priority,
            tags=tags or [],
            created=now,
            updated=now,
            body="",
        )

        return self.repository.save(task)

    def update_task(self, task: Task) -> Task:
        """
        Update an existing task.

        Updates the 'updated' timestamp automatically.
        """
        task.updated = now_utc()
        return self.repository.save(task)

    def delete_task(self, filename: str) -> None:
        """Delete a task by filename."""
        self.repository.delete(filename)

    def get_task(self, filename: str) -> Task | None:
        """Get a task by filename."""
        return self.repository.get_by_id(filename)

    def open_in_editor(self, task: Task) -> bool:
        """
        Open task file in the user's editor.

        Returns True if editor exited successfully.
        """
        if task.filepath is None:
            return False

        editor = os.environ.get("EDITOR", "vim")

        try:
            result = subprocess.run(
                [editor, str(task.filepath)],
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            # Editor not found
            return False

    def _unique_filename(self, filename: str) -> str:
        """Ensure filename is unique by appending numbers if needed."""
        base = filename.removesuffix(".md")
        candidate = filename
        counter = 1

        while self.repository.get_by_id(candidate) is not None:
            candidate = f"{base}-{counter}.md"
            counter += 1

        return candidate
```

### BoardService (services/board_service.py)

```python
from ..models import Task, TaskState, BoardOrder
from ..models.board import Board
from ..repositories import FilesystemRepository
from ..utils.datetime import now_utc


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

        old_state = task.state
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
```

### Board Model Addition (models/board.py)

```python
from pydantic import BaseModel, Field
from .task import Task
from .enums import TaskState


class BoardOrder(BaseModel):
    """Represents the ordering of tasks in tasks.yaml."""
    # ... existing implementation ...


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
```

### FilterService (services/filter_service.py)

```python
import re
from dataclasses import dataclass, field
from ..models import Task, TaskState, Priority


@dataclass
class Filter:
    """Represents a parsed filter expression."""

    text: str | None = None  # Free text search
    tags: list[str] = field(default_factory=list)  # tag:value
    exclude_tags: list[str] = field(default_factory=list)  # -tag:value
    states: list[TaskState] = field(default_factory=list)  # state:value
    priorities: list[Priority] = field(default_factory=list)  # priority:value
    show_archived: bool = False  # archived:true


class FilterService:
    """Service for parsing and applying filters to tasks."""

    # Pattern for key:value tokens
    TOKEN_PATTERN = re.compile(
        r'(-?)(?:(tag|state|priority|archived):)?(\S+)'
    )

    def parse(self, expression: str) -> Filter:
        """
        Parse a filter expression string.

        Syntax:
        - Free text: matches title or body
        - tag:value: filter by tag
        - -tag:value: exclude tag
        - state:todo/in_progress/done/archived
        - priority:low/medium/high/critical
        - archived:true - show archived tasks

        Multiple conditions are ANDed together.
        """
        f = Filter()
        text_parts = []

        for match in self.TOKEN_PATTERN.finditer(expression):
            negated = match.group(1) == "-"
            key = match.group(2)
            value = match.group(3).lower()

            if key is None:
                # Free text (might be negated, but we ignore that for text)
                if not negated:
                    text_parts.append(match.group(3))

            elif key == "tag":
                if negated:
                    f.exclude_tags.append(value)
                else:
                    f.tags.append(value)

            elif key == "state":
                try:
                    f.states.append(TaskState(value))
                except ValueError:
                    pass  # Invalid state, ignore

            elif key == "priority":
                try:
                    f.priorities.append(Priority(value))
                except ValueError:
                    pass  # Invalid priority, ignore

            elif key == "archived":
                f.show_archived = value == "true"

        if text_parts:
            f.text = " ".join(text_parts)

        return f

    def apply(self, tasks: list[Task], filter_: Filter) -> list[Task]:
        """Apply filter to a list of tasks."""
        result = []

        for task in tasks:
            if self._matches(task, filter_):
                result.append(task)

        return result

    def _matches(self, task: Task, f: Filter) -> bool:
        """Check if a task matches the filter."""
        # Hide archived by default unless explicitly requested
        if task.state == TaskState.ARCHIVED and not f.show_archived:
            return False

        # Text search (case-insensitive)
        if f.text:
            search_text = f.text.lower()
            title = task.display_title.lower()
            body = task.body.lower()
            if search_text not in title and search_text not in body:
                return False

        # Tag inclusion (any match)
        if f.tags:
            task_tags = [t.lower() for t in task.tags]
            if not any(tag in task_tags for tag in f.tags):
                return False

        # Tag exclusion (no matches)
        if f.exclude_tags:
            task_tags = [t.lower() for t in task.tags]
            if any(tag in task_tags for tag in f.exclude_tags):
                return False

        # State filter (any match)
        if f.states:
            if task.state not in f.states:
                return False

        # Priority filter (any match)
        if f.priorities:
            if task.priority not in f.priorities:
                return False

        return True
```

## Service Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         UI Layer                              │
└──────────────────────────────┬───────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
┌───────────────┐    ┌────────────────┐    ┌─────────────────┐
│ TaskService   │    │ BoardService   │    │ FilterService   │
│               │    │                │    │                 │
│ - create_task │    │ - load_board   │    │ - parse         │
│ - update_task │    │ - move_task    │    │ - apply         │
│ - delete_task │    │ - archive_task │    │                 │
│ - open_editor │    │ - reload       │    │                 │
└───────┬───────┘    └───────┬────────┘    └─────────────────┘
        │                    │
        └────────────┬───────┘
                     │
                     ▼
        ┌────────────────────────┐
        │ FilesystemRepository   │
        └────────────────────────┘
```

## Service Initialization

Services will be initialized in the main app with dependency injection:

```python
# In app.py or __main__.py
from pathlib import Path
from kosmos.repositories import FilesystemRepository
from kosmos.services import TaskService, BoardService, FilterService

def create_services(task_root: Path):
    repository = FilesystemRepository(task_root)
    return {
        "task": TaskService(repository),
        "board": BoardService(repository),
        "filter": FilterService(),
    }
```

## Filter Syntax Examples

| Filter | Description |
|--------|-------------|
| `login` | Tasks with "login" in title or body |
| `tag:bug` | Tasks tagged with "bug" |
| `tag:bug tag:auth` | Tasks with both "bug" AND "auth" tags |
| `-tag:wontfix` | Exclude tasks tagged "wontfix" |
| `state:in_progress` | Only in-progress tasks |
| `priority:high` | Only high priority tasks |
| `bug priority:high` | Text "bug" AND high priority |
| `archived:true` | Include archived tasks |

## Testing Notes

Tests should focus on:
- Filter parsing with various expressions
- Filter application edge cases
- Task creation with filename collision handling
- State transitions (move left/right)

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|
| 2025-11-28 | Added `get_task()` and `get_all_tasks()` to TaskService | Convenience methods for UI layer |
| 2025-11-28 | Added `move_task_left()` and `move_task_right()` to BoardService | Easier keyboard navigation support |
| 2025-11-28 | Added `get_board_order()` and `save_board_order()` to BoardService | Expose ordering for potential reordering UI |
| 2025-11-28 | `open_in_editor()` returns bool instead of None | Allow caller to know if editor succeeded |

## Completion Notes

**Phase 4 completed on 2025-11-28**

Files created:
- `src/kosmos/services/task_service.py` - TaskService implementation
- `src/kosmos/services/board_service.py` - BoardService implementation
- `src/kosmos/services/filter_service.py` - Filter dataclass and FilterService
- `tests/test_filter.py` - 29 tests for filter parsing and application

Test coverage:
- Filter parsing (16 tests): empty, text, tags, states, priorities, archived, complex
- Filter application (13 tests): text search, tag matching, exclusions, combinations

All 61 tests passing (14 slug + 18 repository + 29 filter).

## Key Notes

- Services own business logic; repository only handles I/O
- FilterService is stateless (no repository dependency)
- `open_in_editor` uses subprocess.run for simplicity
- Archived tasks are hidden by default in filter results
- State transitions exclude "archived" from the normal flow
