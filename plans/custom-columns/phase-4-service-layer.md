# Phase 4: Service Layer Updates

## Overview

This phase updates the service layer to use dynamic column configuration. The key changes are in `BoardService` (state transitions now use config-defined column order) and `FilterService` (state filtering accepts any string). After this phase, task movement between columns respects custom column order.

## Goals

1. Update `BoardService` to use `ConfigService` for column navigation
2. Rewrite `_previous_state()` and `_next_state()` for dynamic column order
3. Update `FilterService` to accept string states instead of `TaskState` enum
4. Update `TaskService` to accept string state in `create_task()`
5. Ensure all service tests pass with string states

## Task Checklist

- [ ] Update `src/kosmos/services/board_service.py`:
  - [ ] Add `ConfigService` dependency
  - [ ] Rewrite `_previous_state()` to use config column order
  - [ ] Rewrite `_next_state()` to use config column order
  - [ ] Update `move_task_left()` and `move_task_right()`
  - [ ] Update `archive_task()` - archived always valid
  - [ ] Update `cycle_task_state()` if it exists
- [ ] Update `src/kosmos/services/filter_service.py`:
  - [ ] Change `states: list[TaskState]` to `states: list[str]`
  - [ ] Update `_parse_filter()` to accept any state string
  - [ ] Update `apply()` to compare string states
- [ ] Update `src/kosmos/services/task_service.py`:
  - [ ] Update `create_task()` to accept `state: str` parameter
  - [ ] Default to first column from config (or "todo")
- [ ] Update `src/kosmos/services/__init__.py` exports
- [ ] Update tests:
  - [ ] `tests/test_board_service.py` - string states, custom columns
  - [ ] `tests/test_filter.py` - string state filtering
  - [ ] `tests/test_task_service.py` - string state creation

## Detailed Specifications

### BoardService Updates

**Current Implementation (src/kosmos/services/board_service.py lines 117-137):**
```python
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

**New Implementation:**
```python
from kosmos.models import BoardConfig
from kosmos.services.config_service import ConfigService


class BoardService:
    """Service for board-level operations."""

    def __init__(
        self,
        repository: FilesystemRepository,
        config_service: ConfigService | None = None,
    ) -> None:
        self.repository = repository
        self._config_service = config_service

        # Wire config service to repository if provided
        if config_service and hasattr(repository, 'config_service'):
            repository.config_service = config_service

    def _get_board_config(self) -> BoardConfig:
        """Get board configuration."""
        if self._config_service:
            return self._config_service.get_board_config()
        return BoardConfig.default()

    def _get_column_order(self) -> list[str]:
        """Get ordered list of visible column IDs."""
        config = self._get_board_config()
        return config.column_ids

    def _previous_state(self, state: str) -> str | None:
        """Get the previous state in the workflow."""
        # Archived tasks don't move left
        if state == "archived":
            return None

        order = self._get_column_order()
        try:
            idx = order.index(state)
            if idx > 0:
                return order[idx - 1]
        except ValueError:
            # Unknown state - can't determine previous
            pass
        return None

    def _next_state(self, state: str) -> str | None:
        """Get the next state in the workflow."""
        # Archived tasks don't move right
        if state == "archived":
            return None

        order = self._get_column_order()
        try:
            idx = order.index(state)
            if idx < len(order) - 1:
                return order[idx + 1]
        except ValueError:
            # Unknown state - can't determine next
            pass
        return None

    def move_task(self, filename: str, to_state: str) -> Task | None:
        """Move a task to a different state/column."""
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        task.state = to_state
        task.updated = now_utc()
        self.repository.save(task)
        return task

    def move_task_left(self, filename: str) -> Task | None:
        """Move task to the previous column."""
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        prev_state = self._previous_state(task.state)
        if prev_state is None:
            return None

        return self.move_task(filename, prev_state)

    def move_task_right(self, filename: str) -> Task | None:
        """Move task to the next column."""
        task = self.repository.get_by_id(filename)
        if task is None:
            return None

        next_state = self._next_state(task.state)
        if next_state is None:
            return None

        return self.move_task(filename, next_state)

    def archive_task(self, filename: str) -> Task | None:
        """Archive a task (move to archived state)."""
        return self.move_task(filename, "archived")

    def unarchive_task(self, filename: str) -> Task | None:
        """Unarchive a task (move to first column)."""
        task = self.repository.get_by_id(filename)
        if task is None or task.state != "archived":
            return None

        first_column = self._get_column_order()[0]
        return self.move_task(filename, first_column)

    def load_board(self) -> Board:
        """Load the full board with all tasks grouped by state."""
        tasks = self.repository.get_all()
        config = self._get_board_config()
        return Board.from_tasks(tasks, config)

    # ... other methods ...
```

### FilterService Updates

**Current Implementation (relevant parts):**
```python
@dataclass
class TaskFilter:
    """Parsed filter criteria."""
    text: str = ""
    tags: list[str] = field(default_factory=list)
    states: list[TaskState] = field(default_factory=list)
    priorities: list[Priority] = field(default_factory=list)
```

**New Implementation:**
```python
from dataclasses import dataclass, field
from kosmos.models import Task, Priority


@dataclass
class TaskFilter:
    """Parsed filter criteria."""

    text: str = ""
    tags: list[str] = field(default_factory=list)
    states: list[str] = field(default_factory=list)  # Changed from TaskState
    priorities: list[Priority] = field(default_factory=list)


class FilterService:
    """Service for filtering tasks."""

    def parse(self, query: str) -> TaskFilter:
        """Parse a filter query string into TaskFilter."""
        f = TaskFilter()

        if not query:
            return f

        parts = query.split()
        text_parts: list[str] = []

        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                key = key.lower()
                value = value.strip()

                if not value:
                    text_parts.append(part)
                    continue

                if key == "tag":
                    f.tags.append(value.lower())
                elif key == "state":
                    # Accept any state string (no enum validation)
                    f.states.append(value.lower())
                elif key == "priority":
                    try:
                        f.priorities.append(Priority(value.lower()))
                    except ValueError:
                        # Invalid priority, treat as text
                        text_parts.append(part)
                else:
                    text_parts.append(part)
            else:
                text_parts.append(part)

        f.text = " ".join(text_parts)
        return f

    def apply(self, tasks: list[Task], filter_obj: TaskFilter) -> list[Task]:
        """Apply filter to a list of tasks."""
        return [t for t in tasks if self._matches(t, filter_obj)]

    def _matches(self, task: Task, f: TaskFilter) -> bool:
        """Check if a task matches the filter criteria."""
        # Text search (title and body)
        if f.text:
            search_text = f.text.lower()
            title = (task.title or "").lower()
            body = task.body.lower()
            if search_text not in title and search_text not in body:
                return False

        # Tag filter (any match)
        if f.tags:
            task_tags = [t.lower() for t in task.tags]
            if not any(tag in task_tags for tag in f.tags):
                return False

        # State filter (any match) - now string comparison
        if f.states:
            if task.state not in f.states:
                return False

        # Priority filter (any match)
        if f.priorities:
            if task.priority not in f.priorities:
                return False

        return True
```

### TaskService Updates

```python
class TaskService:
    """Service for task CRUD operations."""

    def __init__(
        self,
        repository: FilesystemRepository,
        config_service: ConfigService | None = None,
    ) -> None:
        self.repository = repository
        self._config_service = config_service

    def _get_default_state(self) -> str:
        """Get the default state for new tasks (first column)."""
        if self._config_service:
            config = self._config_service.get_board_config()
            return config.columns[0].id
        return "todo"

    def create_task(
        self,
        title: str,
        state: str | None = None,
        priority: Priority = Priority.MEDIUM,
        tags: list[str] | None = None,
        body: str = "",
    ) -> Task:
        """Create a new task."""
        if state is None:
            state = self._get_default_state()

        filename = generate_filename(title)
        now = now_utc()

        task = Task(
            filename=filename,
            title=title,
            state=state,
            priority=priority,
            tags=tags or [],
            created=now,
            updated=now,
            body=body,
        )

        return self.repository.save(task)

    # ... other methods unchanged ...
```

### App Integration

Update `app.py` to pass `ConfigService` to services:

```python
class KosmosApp(App):
    def __init__(self, task_root: Path | None = None) -> None:
        super().__init__()
        self._task_root = task_root or Path(".tasks")
        self._config_service: ConfigService | None = None
        self._repository: FilesystemRepository | None = None
        self._board_service: BoardService | None = None
        self._task_service: TaskService | None = None
        self._filter_service: FilterService | None = None

    @property
    def config_service(self) -> ConfigService:
        if self._config_service is None:
            self._config_service = ConfigService(self._task_root)
        return self._config_service

    @property
    def repository(self) -> FilesystemRepository:
        if self._repository is None:
            self._repository = FilesystemRepository(
                self._task_root,
                self.config_service,
            )
        return self._repository

    @property
    def board_service(self) -> BoardService:
        if self._board_service is None:
            self._board_service = BoardService(
                self.repository,
                self.config_service,
            )
        return self._board_service

    @property
    def task_service(self) -> TaskService:
        if self._task_service is None:
            self._task_service = TaskService(
                self.repository,
                self.config_service,
            )
        return self._task_service

    @property
    def filter_service(self) -> FilterService:
        if self._filter_service is None:
            self._filter_service = FilterService()
        return self._filter_service
```

## Testing Strategy

### BoardService Tests

```python
import pytest
from pathlib import Path
from kosmos.services import BoardService, ConfigService
from kosmos.repositories import FilesystemRepository
from kosmos.models import BoardConfig, ColumnConfig


@pytest.fixture
def custom_config_service(task_dir: Path) -> ConfigService:
    """Create config service with custom 4-column layout."""
    config_file = task_dir / "sltasks.yml"
    config_file.write_text("""
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: todo
      title: "To Do"
    - id: in_progress
      title: "In Progress"
    - id: done
      title: "Done"
""")
    return ConfigService(task_dir)


class TestBoardServiceNavigation:
    def test_previous_state_default_config(self, task_dir: Path):
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = BoardService(repo, config_service)

        assert service._previous_state("in_progress") == "todo"
        assert service._previous_state("done") == "in_progress"
        assert service._previous_state("todo") is None

    def test_next_state_default_config(self, task_dir: Path):
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = BoardService(repo, config_service)

        assert service._next_state("todo") == "in_progress"
        assert service._next_state("in_progress") == "done"
        assert service._next_state("done") is None

    def test_previous_state_custom_config(
        self, task_dir: Path, custom_config_service: ConfigService
    ):
        repo = FilesystemRepository(task_dir, custom_config_service)
        service = BoardService(repo, custom_config_service)

        assert service._previous_state("todo") == "backlog"
        assert service._previous_state("in_progress") == "todo"
        assert service._previous_state("backlog") is None

    def test_next_state_custom_config(
        self, task_dir: Path, custom_config_service: ConfigService
    ):
        repo = FilesystemRepository(task_dir, custom_config_service)
        service = BoardService(repo, custom_config_service)

        assert service._next_state("backlog") == "todo"
        assert service._next_state("todo") == "in_progress"
        assert service._next_state("done") is None

    def test_archived_cannot_move(self, task_dir: Path):
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = BoardService(repo, config_service)

        assert service._previous_state("archived") is None
        assert service._next_state("archived") is None

    def test_unknown_state_cannot_move(self, task_dir: Path):
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = BoardService(repo, config_service)

        assert service._previous_state("unknown") is None
        assert service._next_state("unknown") is None


class TestBoardServiceMovement:
    def test_move_task_left(self, task_dir: Path):
        # Create task file
        (task_dir / "task.md").write_text("---\nstate: in_progress\n---\n")

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = BoardService(repo, config_service)

        task = service.move_task_left("task.md")

        assert task is not None
        assert task.state == "todo"

    def test_move_task_right(self, task_dir: Path):
        (task_dir / "task.md").write_text("---\nstate: todo\n---\n")

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = BoardService(repo, config_service)

        task = service.move_task_right("task.md")

        assert task is not None
        assert task.state == "in_progress"

    def test_move_task_left_at_start(self, task_dir: Path):
        (task_dir / "task.md").write_text("---\nstate: todo\n---\n")

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = BoardService(repo, config_service)

        task = service.move_task_left("task.md")

        assert task is None  # Can't move left from first column

    def test_unarchive_goes_to_first_column(
        self, task_dir: Path, custom_config_service: ConfigService
    ):
        (task_dir / "task.md").write_text("---\nstate: archived\n---\n")

        repo = FilesystemRepository(task_dir, custom_config_service)
        service = BoardService(repo, custom_config_service)

        task = service.unarchive_task("task.md")

        assert task is not None
        assert task.state == "backlog"  # First column in custom config
```

### FilterService Tests

```python
class TestFilterServiceStates:
    def test_parse_state_filter(self):
        service = FilterService()
        f = service.parse("state:todo")

        assert f.states == ["todo"]

    def test_parse_custom_state(self):
        service = FilterService()
        f = service.parse("state:review")

        assert f.states == ["review"]

    def test_parse_multiple_states(self):
        service = FilterService()
        f = service.parse("state:todo state:in_progress")

        assert f.states == ["todo", "in_progress"]

    def test_apply_state_filter(self):
        service = FilterService()
        tasks = [
            Task(filename="a.md", state="todo"),
            Task(filename="b.md", state="review"),
            Task(filename="c.md", state="done"),
        ]
        f = service.parse("state:review")

        result = service.apply(tasks, f)

        assert len(result) == 1
        assert result[0].filename == "b.md"

    def test_apply_multiple_states(self):
        service = FilterService()
        tasks = [
            Task(filename="a.md", state="todo"),
            Task(filename="b.md", state="review"),
            Task(filename="c.md", state="done"),
        ]
        f = service.parse("state:todo state:review")

        result = service.apply(tasks, f)

        assert len(result) == 2
        assert {t.filename for t in result} == {"a.md", "b.md"}
```

### TaskService Tests

```python
class TestTaskServiceCreate:
    def test_create_task_default_state(self, task_dir: Path):
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = TaskService(repo, config_service)

        task = service.create_task("My Task")

        assert task.state == "todo"  # Default first column

    def test_create_task_custom_state(self, task_dir: Path):
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        service = TaskService(repo, config_service)

        task = service.create_task("My Task", state="review")

        assert task.state == "review"

    def test_create_task_custom_config_default(
        self, task_dir: Path, custom_config_service: ConfigService
    ):
        repo = FilesystemRepository(task_dir, custom_config_service)
        service = TaskService(repo, custom_config_service)

        task = service.create_task("My Task")

        assert task.state == "backlog"  # First column in custom config
```

## Verification Steps

1. Run `uv run pytest tests/test_board_service.py -v` - all tests pass
2. Run `uv run pytest tests/test_filter.py -v` - all tests pass
3. Run `uv run pytest tests/test_task_service.py -v` - all tests pass
4. Start app with custom `sltasks.yml`
5. Move tasks with H/L keys - respects custom column order
6. Filter by custom state `state:review` - works correctly
7. Create new task - defaults to first custom column

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|

## Completion Notes

**Phase 4 status: Pending**

## Key Notes

- `BoardService` now requires `ConfigService` for column order
- State navigation is entirely driven by config, not hardcoded
- Archived tasks are special - always valid, never in navigation order
- Unknown states cannot be navigated (return None)
- `FilterService` accepts any state string, no validation
- New tasks default to first configured column, not hardcoded "todo"
- All services wired through app properties for consistent config access
