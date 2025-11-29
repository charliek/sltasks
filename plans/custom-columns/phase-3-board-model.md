# Phase 3: Board Model Refactor

## Overview

This phase refactors the `Board` and `BoardOrder` models to support dynamic columns instead of the hardcoded `todo`, `in_progress`, `done`, `archived` fields. After this phase, the repository can load tasks into any number of columns defined by the configuration.

## Goals

1. Refactor `Board` model to use `dict[str, list[Task]]` instead of fixed fields
2. Update `Board.from_tasks()` to accept column configuration
3. Update `BoardOrder` to handle dynamic column names
4. Update `FilesystemRepository` for dynamic column ordering
5. Ensure existing `tasks.yaml` files continue to work

## Task Checklist

- [ ] Update `src/kosmos/models/board.py`:
  - [ ] Replace fixed `todo`, `in_progress`, `done`, `archived` fields with `columns: dict[str, list[Task]]`
  - [ ] Update `from_tasks()` to accept `BoardConfig` parameter
  - [ ] Add method to get tasks for a specific column
  - [ ] Update `visible_columns` property to use config
  - [ ] Update `BoardOrder` default columns to be dynamic
- [ ] Update `src/kosmos/repositories/filesystem.py`:
  - [ ] Inject `ConfigService` dependency
  - [ ] Update `_load_board_order()` for dynamic columns
  - [ ] Update `_reconcile()` for dynamic columns
  - [ ] Update `_sorted_tasks()` for dynamic column order
  - [ ] Update `_save_board_order()` to preserve custom columns
- [ ] Update `src/kosmos/services/board_service.py`:
  - [ ] Update `load_board()` to pass config to `Board.from_tasks()`
- [ ] Add/update tests:
  - [ ] Test Board with custom columns
  - [ ] Test BoardOrder with custom columns
  - [ ] Test repository with custom column ordering

## Detailed Specifications

### Board Model (Before)

```python
class Board(BaseModel):
    """Full board state with tasks grouped by column."""

    todo: list[Task] = Field(default_factory=list)
    in_progress: list[Task] = Field(default_factory=list)
    done: list[Task] = Field(default_factory=list)
    archived: list[Task] = Field(default_factory=list)

    @classmethod
    def from_tasks(cls, tasks: list[Task]) -> "Board":
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

    @property
    def visible_columns(self) -> list[tuple[TaskState, list[Task]]]:
        return [
            (TaskState.TODO, self.todo),
            (TaskState.IN_PROGRESS, self.in_progress),
            (TaskState.DONE, self.done),
        ]
```

### Board Model (After)

```python
from kosmos.models.sltasks_config import BoardConfig, ColumnConfig


class Board(BaseModel):
    """Full board state with tasks grouped by column."""

    columns: dict[str, list[Task]] = Field(default_factory=dict)
    _config: BoardConfig | None = None

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_tasks(cls, tasks: list[Task], config: BoardConfig | None = None) -> "Board":
        """
        Create Board from tasks, grouping by state.

        Args:
            tasks: List of tasks to group
            config: Board configuration for column definitions.
                    If None, uses default 3-column config.
        """
        if config is None:
            config = BoardConfig.default()

        board = cls()
        board._config = config

        # Initialize all columns from config
        for col in config.columns:
            board.columns[col.id] = []

        # Always have archived column
        board.columns["archived"] = []

        # Sort tasks into columns
        for task in tasks:
            if task.state in board.columns:
                board.columns[task.state].append(task)
            else:
                # Unknown state - place in first column
                first_col = config.columns[0].id
                board.columns[first_col].append(task)

        return board

    def get_column(self, column_id: str) -> list[Task]:
        """Get tasks for a specific column."""
        return self.columns.get(column_id, [])

    def visible_columns(self, config: BoardConfig | None = None) -> list[tuple[str, str, list[Task]]]:
        """
        Get visible columns (excludes archived) with their config.

        Returns:
            List of (column_id, title, tasks) tuples in display order.
        """
        if config is None:
            config = self._config or BoardConfig.default()

        return [
            (col.id, col.title, self.columns.get(col.id, []))
            for col in config.columns
        ]

    @property
    def archived(self) -> list[Task]:
        """Convenience property for archived tasks."""
        return self.columns.get("archived", [])

    # Backwards compatibility properties
    @property
    def todo(self) -> list[Task]:
        """Backwards compatibility - get 'todo' column."""
        return self.columns.get("todo", [])

    @property
    def in_progress(self) -> list[Task]:
        """Backwards compatibility - get 'in_progress' column."""
        return self.columns.get("in_progress", [])

    @property
    def done(self) -> list[Task]:
        """Backwards compatibility - get 'done' column."""
        return self.columns.get("done", [])
```

### BoardOrder Model (Before)

```python
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
```

### BoardOrder Model (After)

```python
class BoardOrder(BaseModel):
    """Represents the ordering of tasks in tasks.yaml."""

    version: int = 1
    columns: dict[str, list[str]] = Field(default_factory=dict)

    @classmethod
    def from_config(cls, config: BoardConfig) -> "BoardOrder":
        """Create BoardOrder with columns from config."""
        order = cls()
        for col in config.columns:
            order.columns[col.id] = []
        order.columns["archived"] = []
        return order

    @classmethod
    def default(cls) -> "BoardOrder":
        """Create default BoardOrder with standard 3 columns."""
        return cls(columns={
            "todo": [],
            "in_progress": [],
            "done": [],
            "archived": [],
        })

    def ensure_column(self, column_id: str) -> None:
        """Ensure a column exists in the order."""
        if column_id not in self.columns:
            self.columns[column_id] = []

    def add_task(self, filename: str, state: str, position: int = -1) -> None:
        """Add task to column at position (-1 = end)."""
        self.ensure_column(state)
        self.remove_task(filename)

        if position < 0:
            self.columns[state].append(filename)
        else:
            self.columns[state].insert(position, filename)

    # ... rest of methods unchanged ...
```

### FilesystemRepository Updates

```python
class FilesystemRepository:
    """Repository for task files stored on the filesystem."""

    TASKS_YAML = "tasks.yaml"

    def __init__(self, task_root: Path, config_service: ConfigService | None = None) -> None:
        self.task_root = task_root
        self._config_service = config_service
        self._tasks: dict[str, Task] = {}
        self._board_order: BoardOrder | None = None

    @property
    def config_service(self) -> ConfigService | None:
        return self._config_service

    @config_service.setter
    def config_service(self, service: ConfigService) -> None:
        self._config_service = service

    def _get_board_config(self) -> BoardConfig:
        """Get board config, using default if no config service."""
        if self._config_service:
            return self._config_service.get_board_config()
        return BoardConfig.default()

    def _load_board_order(self) -> None:
        """Load tasks.yaml if it exists."""
        yaml_path = self.task_root / self.TASKS_YAML

        if yaml_path.exists():
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            self._board_order = BoardOrder(**data)
        else:
            # Create from config
            config = self._get_board_config()
            self._board_order = BoardOrder.from_config(config)

    def _ensure_board_order(self) -> None:
        """Ensure board order exists and has all config columns."""
        if self._board_order is None:
            self._load_board_order()

        # Ensure all config columns exist
        config = self._get_board_config()
        for col in config.columns:
            self._board_order.ensure_column(col.id)
        self._board_order.ensure_column("archived")

    def _reconcile(self) -> None:
        """Reconcile task files with board order."""
        self._ensure_board_order()
        config = self._get_board_config()
        valid_columns = set(col.id for col in config.columns) | {"archived"}

        # Get all tracked filenames from board order
        tracked: set[str] = set()
        for column in self._board_order.columns.values():
            tracked.update(column)

        # Get all actual task filenames
        actual = set(self._tasks.keys())

        # Remove missing files from board order
        missing = tracked - actual
        for filename in missing:
            self._board_order.remove_task(filename)

        # Add new files to appropriate column
        new = actual - tracked
        for filename in new:
            task = self._tasks[filename]
            state = task.state

            # Map unknown states to first column
            if state not in valid_columns:
                state = config.columns[0].id

            self._board_order.add_task(filename, state)

        # Move tasks whose file state doesn't match YAML column
        for filename, task in self._tasks.items():
            file_state = task.state

            # Map unknown states to first column
            if file_state not in valid_columns:
                file_state = config.columns[0].id

            # Find current column in YAML
            yaml_column = None
            for col_id, filenames in self._board_order.columns.items():
                if filename in filenames:
                    yaml_column = col_id
                    break

            # Move if mismatch (file state wins)
            if yaml_column and yaml_column != file_state:
                self._board_order.move_task(filename, yaml_column, file_state)

    def _sorted_tasks(self) -> list[Task]:
        """Return tasks sorted by board order position."""
        if self._board_order is None:
            return list(self._tasks.values())

        config = self._get_board_config()
        sorted_tasks: list[Task] = []

        # Process columns in config order
        for col in config.columns:
            col_id = col.id
            if col_id in self._board_order.columns:
                for filename in self._board_order.columns[col_id]:
                    if filename in self._tasks:
                        sorted_tasks.append(self._tasks[filename])

        # Add archived
        if "archived" in self._board_order.columns:
            for filename in self._board_order.columns["archived"]:
                if filename in self._tasks:
                    sorted_tasks.append(self._tasks[filename])

        # Add any orphaned tasks (shouldn't happen after reconcile)
        seen = {t.filename for t in sorted_tasks}
        for task in self._tasks.values():
            if task.filename not in seen:
                sorted_tasks.append(task)

        return sorted_tasks
```

### BoardService Update

```python
class BoardService:
    def __init__(
        self,
        repository: FilesystemRepository,
        config_service: ConfigService | None = None,
    ) -> None:
        self.repository = repository
        self._config_service = config_service

        # Wire config service to repository
        if config_service:
            self.repository.config_service = config_service

    def _get_board_config(self) -> BoardConfig:
        if self._config_service:
            return self._config_service.get_board_config()
        return BoardConfig.default()

    def load_board(self) -> Board:
        """Load the full board with all tasks grouped by state."""
        tasks = self.repository.get_all()
        config = self._get_board_config()
        return Board.from_tasks(tasks, config)
```

## Testing Strategy

### Board Model Tests

```python
from kosmos.models import Board, Task, BoardConfig, ColumnConfig


class TestBoardDynamicColumns:
    def test_from_tasks_default_config(self):
        tasks = [
            Task(filename="a.md", state="todo"),
            Task(filename="b.md", state="in_progress"),
            Task(filename="c.md", state="done"),
        ]
        board = Board.from_tasks(tasks)

        assert len(board.get_column("todo")) == 1
        assert len(board.get_column("in_progress")) == 1
        assert len(board.get_column("done")) == 1

    def test_from_tasks_custom_config(self):
        config = BoardConfig(columns=[
            ColumnConfig(id="backlog", title="Backlog"),
            ColumnConfig(id="active", title="Active"),
            ColumnConfig(id="complete", title="Complete"),
        ])
        tasks = [
            Task(filename="a.md", state="backlog"),
            Task(filename="b.md", state="active"),
            Task(filename="c.md", state="complete"),
        ]
        board = Board.from_tasks(tasks, config)

        assert len(board.get_column("backlog")) == 1
        assert len(board.get_column("active")) == 1
        assert len(board.get_column("complete")) == 1

    def test_unknown_state_goes_to_first_column(self):
        config = BoardConfig(columns=[
            ColumnConfig(id="todo", title="To Do"),
            ColumnConfig(id="done", title="Done"),
        ])
        tasks = [
            Task(filename="a.md", state="unknown_state"),
        ]
        board = Board.from_tasks(tasks, config)

        # Unknown state placed in first column
        assert len(board.get_column("todo")) == 1
        assert board.get_column("todo")[0].filename == "a.md"

    def test_visible_columns(self):
        config = BoardConfig(columns=[
            ColumnConfig(id="a", title="Column A"),
            ColumnConfig(id="b", title="Column B"),
        ])
        tasks = [
            Task(filename="1.md", state="a"),
            Task(filename="2.md", state="b"),
            Task(filename="3.md", state="archived"),
        ]
        board = Board.from_tasks(tasks, config)

        visible = board.visible_columns(config)
        assert len(visible) == 2
        assert visible[0][0] == "a"
        assert visible[0][1] == "Column A"
        assert visible[1][0] == "b"

    def test_archived_always_available(self):
        config = BoardConfig(columns=[
            ColumnConfig(id="todo", title="To Do"),
            ColumnConfig(id="done", title="Done"),
        ])
        tasks = [
            Task(filename="archived.md", state="archived"),
        ]
        board = Board.from_tasks(tasks, config)

        assert len(board.archived) == 1

    def test_backwards_compat_properties(self):
        tasks = [
            Task(filename="a.md", state="todo"),
            Task(filename="b.md", state="in_progress"),
        ]
        board = Board.from_tasks(tasks)

        # Old property access still works
        assert len(board.todo) == 1
        assert len(board.in_progress) == 1


class TestBoardOrderDynamic:
    def test_from_config(self):
        config = BoardConfig(columns=[
            ColumnConfig(id="a", title="A"),
            ColumnConfig(id="b", title="B"),
        ])
        order = BoardOrder.from_config(config)

        assert "a" in order.columns
        assert "b" in order.columns
        assert "archived" in order.columns

    def test_ensure_column(self):
        order = BoardOrder.default()
        order.ensure_column("new_column")

        assert "new_column" in order.columns
```

### Repository Integration Tests

```python
def test_repository_with_custom_columns(task_dir: Path):
    # Create config
    config_file = task_dir / "sltasks.yml"
    config_file.write_text("""
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: active
      title: "Active"
    - id: complete
      title: "Complete"
""")

    # Create task files
    (task_dir / "task1.md").write_text("---\nstate: backlog\n---\n")
    (task_dir / "task2.md").write_text("---\nstate: active\n---\n")

    config_service = ConfigService(task_dir)
    repo = FilesystemRepository(task_dir, config_service)
    tasks = repo.get_all()

    assert len(tasks) == 2

    # Check tasks.yaml was created with custom columns
    yaml_path = task_dir / "tasks.yaml"
    assert yaml_path.exists()
    yaml_content = yaml.safe_load(yaml_path.read_text())
    assert "backlog" in yaml_content["columns"]
    assert "active" in yaml_content["columns"]


def test_repository_unknown_state_mapped(task_dir: Path):
    # Create task with unknown state
    (task_dir / "task.md").write_text("---\nstate: weird_state\n---\n")

    config_service = ConfigService(task_dir)  # Default config
    repo = FilesystemRepository(task_dir, config_service)
    tasks = repo.get_all()

    # Check task was placed in first column (todo)
    yaml_path = task_dir / "tasks.yaml"
    yaml_content = yaml.safe_load(yaml_path.read_text())
    assert "task.md" in yaml_content["columns"]["todo"]
```

## Verification Steps

1. Run `uv run pytest tests/test_models.py -v` - Board tests pass
2. Run `uv run pytest tests/test_repository.py -v` - Repository tests pass
3. Create custom `sltasks.yml` and verify tasks sort into correct columns
4. Verify `tasks.yaml` is created with custom column names
5. Verify tasks with unknown states appear in first column

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|

## Completion Notes

**Phase 3 status: Pending**

## Key Notes

- Board model now uses `dict[str, list[Task]]` for flexibility
- Backwards compatibility properties (`todo`, `in_progress`, `done`) preserved
- Unknown states silently map to first configured column
- `BoardOrder.from_config()` creates order with config-defined columns
- Repository needs ConfigService injected to know valid columns
- `visible_columns()` now returns tuples of (id, title, tasks)
