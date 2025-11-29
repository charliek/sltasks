# Phase 6: Polish & Edge Cases

## Overview

This final phase handles edge cases, improves error handling, adds documentation, and ensures the feature is production-ready. This includes graceful handling of invalid configurations, helpful error messages, and comprehensive test coverage.

## Goals

1. Handle invalid `sltasks.yml` gracefully with user feedback
2. Handle tasks with unknown states appropriately
3. Add config validation feedback in UI (optional notification)
4. Update help screen with dynamic column info
5. Ensure comprehensive test coverage
6. Add inline documentation and update README

## Task Checklist

- [ ] Error handling improvements:
  - [ ] Log warning when `sltasks.yml` is invalid
  - [ ] Log warning when task has unknown state
  - [ ] Consider notification on config load failure (optional)
- [ ] Edge case handling:
  - [ ] Test behavior when config changes while app running
  - [ ] Handle `sltasks.yml` with syntax errors
  - [ ] Handle `sltasks.yml` with validation errors
  - [ ] Ensure archived tasks never appear in columns
- [ ] Help screen updates:
  - [ ] Show dynamic column names in help
  - [ ] Update key binding descriptions if needed
- [ ] Documentation:
  - [ ] Add docstrings to new classes/methods
  - [ ] Update README with custom columns info
  - [ ] Add example `sltasks.yml` to docs or examples
- [ ] Code cleanup (no backwards compatibility - early project):
  - [ ] Remove deprecated `TaskState` enum from `models/enums.py`
  - [ ] Remove `TaskState` from `models/__init__.py` exports
  - [ ] Update any remaining code that imports `TaskState`
  - [ ] Search for and remove any `.value` usage on task states
  - [ ] Remove backwards compatibility properties from Board (`todo`, `in_progress`, `done`)
  - [ ] Remove any other deprecated/compatibility code
- [ ] Test coverage:
  - [ ] Ensure >90% coverage on new code
  - [ ] Add edge case tests
  - [ ] Add integration tests for full workflow
- [ ] Final verification:
  - [ ] Run full test suite
  - [ ] Manual testing with various configs
  - [ ] Grep for any remaining TaskState references

## Detailed Specifications

### Enhanced ConfigService Error Handling

```python
import logging
from pathlib import Path
import yaml
from kosmos.models import SltasksConfig, BoardConfig

logger = logging.getLogger(__name__)


class ConfigService:
    """Service for loading and caching application configuration."""

    CONFIG_FILE = "sltasks.yml"

    def __init__(self, task_root: Path) -> None:
        self.task_root = task_root
        self._config: SltasksConfig | None = None
        self._config_error: str | None = None

    @property
    def has_config_error(self) -> bool:
        """Check if there was an error loading config."""
        return self._config_error is not None

    @property
    def config_error(self) -> str | None:
        """Get the config error message if any."""
        return self._config_error

    def get_config(self) -> SltasksConfig:
        """Get configuration, loading from file if not cached."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> SltasksConfig:
        """Load configuration from file or return default."""
        config_path = self.task_root / self.CONFIG_FILE
        self._config_error = None

        if not config_path.exists():
            logger.debug(f"No {self.CONFIG_FILE} found, using defaults")
            return SltasksConfig.default()

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f)

            if data is None:
                self._config_error = f"{self.CONFIG_FILE} is empty"
                logger.warning(self._config_error)
                return SltasksConfig.default()

            config = SltasksConfig(**data)
            logger.info(
                f"Loaded {self.CONFIG_FILE} with {len(config.board.columns)} columns"
            )
            return config

        except yaml.YAMLError as e:
            self._config_error = f"Invalid YAML in {self.CONFIG_FILE}: {e}"
            logger.warning(self._config_error)
            return SltasksConfig.default()

        except Exception as e:
            self._config_error = f"Error loading {self.CONFIG_FILE}: {e}"
            logger.warning(self._config_error)
            return SltasksConfig.default()
```

### Unknown State Handling in Board

```python
class Board(BaseModel):
    @classmethod
    def from_tasks(cls, tasks: list[Task], config: BoardConfig | None = None) -> "Board":
        if config is None:
            config = BoardConfig.default()

        board = cls()
        board._config = config

        # Initialize columns
        for col in config.columns:
            board.columns[col.id] = []
        board.columns["archived"] = []

        # Track unknown states for logging
        unknown_states: set[str] = set()

        for task in tasks:
            if task.state in board.columns:
                board.columns[task.state].append(task)
            else:
                # Unknown state - place in first column
                unknown_states.add(task.state)
                first_col = config.columns[0].id
                board.columns[first_col].append(task)

        # Log unknown states (if any)
        if unknown_states:
            logger.warning(
                f"Tasks with unknown states placed in first column: {unknown_states}"
            )

        return board
```

### Optional Config Error Notification

If we want to show a notification when config loading fails:

```python
# In BoardScreen.on_mount()
def on_mount(self) -> None:
    """Handle mount event."""
    # Check for config errors
    if self.app.config_service.has_config_error:
        self.notify(
            f"Config error: {self.app.config_service.config_error}\n"
            "Using default columns.",
            severity="warning",
            timeout=5,
        )

    self.load_tasks()
    self._update_focus()
```

### Help Screen Updates

Update the help screen to show dynamic column information:

```python
class HelpScreen(Screen):
    def compose(self) -> ComposeResult:
        config = self.app.config_service.get_board_config()
        column_names = ", ".join(col.title for col in config.columns)

        yield Container(
            Static("Kosmos Help", classes="help-title"),
            Static(f"Columns: {column_names}", classes="help-info"),
            Static(""),
            Static("Navigation", classes="help-section"),
            Static("  h/l     Move between columns"),
            Static("  j/k     Move between tasks"),
            Static("  g/G     First/last task"),
            Static("  0/$     First/last column"),
            Static(""),
            Static("Actions", classes="help-section"),
            Static("  H/L     Move task left/right"),
            Static("  s       Cycle task state"),
            Static("  a       Archive task"),
            Static("  n       New task"),
            Static("  e       Edit task"),
            Static("  d       Delete task"),
            Static("  Enter   Preview task"),
            Static(""),
            Static("Other", classes="help-section"),
            Static("  /       Filter tasks"),
            Static("  r       Reload board"),
            Static("  ?       This help"),
            Static("  q       Quit"),
            id="help-content",
        )
```

### Comprehensive Test Cases

```python
# tests/test_edge_cases.py

import pytest
from pathlib import Path
from kosmos.services import ConfigService
from kosmos.repositories import FilesystemRepository
from kosmos.models import Board, Task, BoardConfig, ColumnConfig


class TestInvalidConfig:
    """Test handling of invalid sltasks.yml files."""

    def test_empty_yaml_file(self, task_dir: Path):
        """Empty file uses defaults."""
        (task_dir / "sltasks.yml").write_text("")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error
        assert "empty" in service.config_error.lower()

    def test_invalid_yaml_syntax(self, task_dir: Path):
        """Syntax errors fall back to defaults."""
        (task_dir / "sltasks.yml").write_text("invalid: yaml: syntax:")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert service.has_config_error

    def test_missing_columns_key(self, task_dir: Path):
        """Missing required key falls back to defaults."""
        (task_dir / "sltasks.yml").write_text("version: 1\n")

        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3

    def test_too_few_columns(self, task_dir: Path):
        """Single column fails validation."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: only
      title: "Only Column"
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3  # Default
        assert service.has_config_error

    def test_too_many_columns(self, task_dir: Path):
        """More than 6 columns fails validation."""
        columns = "\n".join([
            f"    - id: col{i}\n      title: 'Column {i}'"
            for i in range(7)
        ])
        (task_dir / "sltasks.yml").write_text(f"""
version: 1
board:
  columns:
{columns}
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3  # Default
        assert service.has_config_error

    def test_duplicate_column_ids(self, task_dir: Path):
        """Duplicate IDs fail validation."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: todo
      title: "Also To Do"
    - id: done
      title: "Done"
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert len(config.board.columns) == 3  # Default
        assert service.has_config_error

    def test_archived_as_column_id(self, task_dir: Path):
        """Using 'archived' as column ID fails."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: archived
      title: "Archive"
    - id: done
      title: "Done"
""")
        service = ConfigService(task_dir)
        config = service.get_config()

        assert "archived" not in config.board.column_ids
        assert service.has_config_error


class TestUnknownStates:
    """Test handling of tasks with unknown states."""

    def test_unknown_state_in_first_column(self, task_dir: Path):
        """Tasks with unknown states go to first column."""
        (task_dir / "task.md").write_text("---\nstate: weird_state\n---\n")

        config = BoardConfig.default()
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        tasks = repo.get_all()

        board = Board.from_tasks(tasks, config)

        assert len(board.get_column("todo")) == 1
        assert board.get_column("todo")[0].state == "weird_state"

    def test_multiple_unknown_states(self, task_dir: Path):
        """Multiple unknown states all go to first column."""
        (task_dir / "task1.md").write_text("---\nstate: weird\n---\n")
        (task_dir / "task2.md").write_text("---\nstate: strange\n---\n")
        (task_dir / "task3.md").write_text("---\nstate: todo\n---\n")

        config = BoardConfig.default()
        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        tasks = repo.get_all()

        board = Board.from_tasks(tasks, config)

        # 2 unknown + 1 todo = 3 in first column
        assert len(board.get_column("todo")) == 3

    def test_archived_always_works(self, task_dir: Path):
        """Archived state always valid even with custom config."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: done
      title: "Done"
""")
        (task_dir / "task.md").write_text("---\nstate: archived\n---\n")

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        tasks = repo.get_all()

        config = config_service.get_board_config()
        board = Board.from_tasks(tasks, config)

        assert len(board.archived) == 1
        assert len(board.get_column("backlog")) == 0


class TestConfigReload:
    """Test config reload behavior."""

    def test_reload_clears_cache(self, task_dir: Path):
        """Reload clears cached config."""
        service = ConfigService(task_dir)

        config1 = service.get_config()
        assert len(config1.board.columns) == 3

        # Add custom config
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: a
      title: "A"
    - id: b
      title: "B"
""")

        # Still cached
        config2 = service.get_config()
        assert config1 is config2

        # After reload
        service.reload()
        config3 = service.get_config()
        assert len(config3.board.columns) == 2


class TestFullWorkflow:
    """Integration tests for complete workflows."""

    def test_create_move_archive_workflow(self, task_dir: Path):
        """Test creating, moving, and archiving a task."""
        # Setup custom config
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: active
      title: "Active"
    - id: done
      title: "Done"
""")

        from kosmos.services import ConfigService, TaskService, BoardService
        from kosmos.repositories import FilesystemRepository

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        task_service = TaskService(repo, config_service)
        board_service = BoardService(repo, config_service)

        # Create task - should be in first column
        task = task_service.create_task("Test Task")
        assert task.state == "backlog"

        # Move right
        task = board_service.move_task_right(task.filename)
        assert task.state == "active"

        # Move right again
        task = board_service.move_task_right(task.filename)
        assert task.state == "done"

        # Can't move right anymore
        result = board_service.move_task_right(task.filename)
        assert result is None

        # Archive
        task = board_service.archive_task(task.filename)
        assert task.state == "archived"

        # Unarchive goes to first column
        task = board_service.unarchive_task(task.filename)
        assert task.state == "backlog"

    def test_filter_custom_states(self, task_dir: Path):
        """Test filtering by custom state names."""
        (task_dir / "sltasks.yml").write_text("""
version: 1
board:
  columns:
    - id: idea
      title: "Ideas"
    - id: planned
      title: "Planned"
    - id: shipped
      title: "Shipped"
""")
        (task_dir / "task1.md").write_text("---\nstate: idea\n---\n")
        (task_dir / "task2.md").write_text("---\nstate: planned\n---\n")
        (task_dir / "task3.md").write_text("---\nstate: shipped\n---\n")

        from kosmos.services import ConfigService, FilterService
        from kosmos.repositories import FilesystemRepository

        config_service = ConfigService(task_dir)
        repo = FilesystemRepository(task_dir, config_service)
        filter_service = FilterService()

        tasks = repo.get_all()
        filter_obj = filter_service.parse("state:planned")
        filtered = filter_service.apply(tasks, filter_obj)

        assert len(filtered) == 1
        assert filtered[0].state == "planned"
```

### Documentation Updates

**README.md section to add:**

```markdown
## Custom Columns

By default, Kosmos uses three columns: To Do, In Progress, and Done. You can
customize this by creating a `sltasks.yml` file in your `.tasks` directory:

```yaml
# .tasks/sltasks.yml
version: 1

board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: todo
      title: "To Do"
    - id: in_progress
      title: "In Progress"
    - id: review
      title: "Code Review"
    - id: done
      title: "Done"
```

### Column Configuration

- **id**: The status value used in task files (lowercase, underscores allowed)
- **title**: Display name shown in the column header
- **Minimum**: 2 columns
- **Maximum**: 6 columns

### Reserved Status

The `archived` status is always available and cannot be used as a column ID.
Archived tasks are hidden from the board but can be restored.

### Task States

When you define custom columns, use the column `id` values in your task files:

```yaml
---
title: "My Task"
state: review  # Matches column id
priority: medium
---
```

If a task has an unknown state (not matching any column), it will appear in
the first column.
```

## Verification Steps

1. Run `uv run pytest` - all tests pass (including new edge case tests)
2. Run `uv run pytest --cov=kosmos --cov-report=term-missing` - check coverage
3. Test with invalid `sltasks.yml`:
   - Empty file
   - Invalid YAML syntax
   - Too few/many columns
   - Duplicate IDs
4. Test with tasks having unknown states
5. Test config reload (`r` key or restart)
6. Verify help screen shows correct column names
7. Check logs for appropriate warnings
8. Review all new code has docstrings

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|

## Completion Notes

**Phase 6 status: Pending**

## Key Notes

- Config errors are logged as warnings, not errors (app still works)
- Unknown task states don't crash - they go to first column with a log warning
- Optional notification can alert users to config problems
- Help screen dynamically shows configured columns
- Test coverage should be comprehensive for all edge cases
- Documentation should be clear about constraints and behavior
