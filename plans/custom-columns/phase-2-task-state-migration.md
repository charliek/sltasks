# Phase 2: Task State Migration

## Overview

This phase migrates the `Task.state` field from the `TaskState` enum to a string type. This is required because Python enums cannot be dynamically extended with custom status values. After this phase, tasks can have any string status value while maintaining backwards compatibility with existing files.

## Goals

1. Change `Task.state` from `TaskState` to `str`
2. Update `to_frontmatter()` to handle string state
3. Update `from_frontmatter()` to accept both enum values and strings
4. Keep `TaskState` enum for backwards compatibility (deprecate later)
5. Update all existing tests to use string states
6. Ensure existing task files continue to work

## Task Checklist

- [ ] Update `src/kosmos/models/task.py`:
  - [ ] Change `state: TaskState = TaskState.TODO` to `state: str = "todo"`
  - [ ] Update `to_frontmatter()` - no `.value` needed for strings
  - [ ] Update `from_frontmatter()` to handle both legacy enum and string
- [ ] Update `src/kosmos/models/enums.py`:
  - [ ] Keep `TaskState` enum (for backwards compat)
  - [ ] Add module-level constants for common states
- [ ] Update tests:
  - [ ] `tests/test_models.py` - use string states
  - [ ] Any other tests referencing `TaskState`
- [ ] Verify existing task files load correctly
- [ ] Run full test suite

## Detailed Specifications

### Task Model Changes

**Before:**
```python
from .enums import TaskState, Priority

class Task(BaseModel):
    # ...
    state: TaskState = TaskState.TODO
    # ...

    def to_frontmatter(self) -> dict:
        data: dict = {}
        if self.title:
            data["title"] = self.title
        data["state"] = self.state.value  # Enum needs .value
        data["priority"] = self.priority.value
        # ...
```

**After:**
```python
from .enums import Priority

# Common state constants for convenience
STATE_TODO = "todo"
STATE_IN_PROGRESS = "in_progress"
STATE_DONE = "done"
STATE_ARCHIVED = "archived"


class Task(BaseModel):
    # ...
    state: str = STATE_TODO
    # ...

    def to_frontmatter(self) -> dict:
        data: dict = {}
        if self.title:
            data["title"] = self.title
        data["state"] = self.state  # String, no .value needed
        data["priority"] = self.priority.value
        # ...
```

### Updated from_frontmatter()

```python
@classmethod
def from_frontmatter(
    cls,
    filename: str,
    metadata: dict,
    body: str,
    filepath: Path | None = None,
) -> "Task":
    """Create Task from parsed front matter."""
    # Handle state - could be string or legacy TaskState enum
    state_value = metadata.get("state", STATE_TODO)
    if hasattr(state_value, "value"):
        # Legacy TaskState enum - extract string value
        state_value = state_value.value

    return cls(
        filename=filename,
        filepath=filepath,
        title=metadata.get("title"),
        state=state_value,
        priority=Priority(metadata.get("priority", "medium")),
        tags=metadata.get("tags", []),
        created=_parse_datetime(metadata.get("created")),
        updated=_parse_datetime(metadata.get("updated")),
        body=body,
    )
```

### Enums Module Updates

```python
# src/kosmos/models/enums.py
from enum import Enum


class TaskState(str, Enum):
    """
    Valid states for a task.

    DEPRECATED: Use string states directly instead.
    This enum is kept for backwards compatibility only.
    """

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ARCHIVED = "archived"


class Priority(str, Enum):
    """Priority levels for tasks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

### Model __init__.py Updates

```python
# src/kosmos/models/__init__.py
from .enums import TaskState, Priority  # Keep for backwards compat
from .task import Task, STATE_TODO, STATE_IN_PROGRESS, STATE_DONE, STATE_ARCHIVED
from .board import Board, BoardOrder
from .sltasks_config import SltasksConfig, BoardConfig, ColumnConfig

__all__ = [
    "TaskState",  # Deprecated but kept
    "Priority",
    "Task",
    "STATE_TODO",
    "STATE_IN_PROGRESS",
    "STATE_DONE",
    "STATE_ARCHIVED",
    "Board",
    "BoardOrder",
    "SltasksConfig",
    "BoardConfig",
    "ColumnConfig",
]
```

## Test Updates

### test_models.py Changes

**Before:**
```python
from kosmos.models import Task, TaskState, Priority

def test_task_default_state():
    task = Task(filename="test.md")
    assert task.state == TaskState.TODO

def test_from_frontmatter_with_state():
    task = Task.from_frontmatter(
        filename="test.md",
        metadata={"state": "in_progress"},
        body="",
    )
    assert task.state == TaskState.IN_PROGRESS
```

**After:**
```python
from kosmos.models import Task, Priority, STATE_TODO, STATE_IN_PROGRESS

def test_task_default_state():
    task = Task(filename="test.md")
    assert task.state == STATE_TODO
    assert task.state == "todo"  # String comparison works too

def test_from_frontmatter_with_state():
    task = Task.from_frontmatter(
        filename="test.md",
        metadata={"state": "in_progress"},
        body="",
    )
    assert task.state == STATE_IN_PROGRESS
    assert task.state == "in_progress"

def test_from_frontmatter_custom_state():
    """Custom states are now allowed."""
    task = Task.from_frontmatter(
        filename="test.md",
        metadata={"state": "review"},
        body="",
    )
    assert task.state == "review"

def test_to_frontmatter_preserves_state():
    task = Task(filename="test.md", state="custom_state")
    fm = task.to_frontmatter()
    assert fm["state"] == "custom_state"
```

### Files to Update

Search for `TaskState` usage and update:

```bash
# Find all files using TaskState
grep -r "TaskState" src/ tests/
```

Expected files needing updates:
- `src/kosmos/models/task.py` - Primary change
- `src/kosmos/models/board.py` - Uses TaskState for grouping (Phase 3)
- `src/kosmos/services/board_service.py` - State transitions (Phase 4)
- `src/kosmos/services/filter_service.py` - State filtering (Phase 4)
- `src/kosmos/ui/screens/board.py` - COLUMN_STATES constant (Phase 5)
- `src/kosmos/ui/widgets/column.py` - Column state property (Phase 5)
- `tests/test_models.py` - Task tests
- `tests/test_board_service.py` - Service tests (Phase 4)
- `tests/test_filter.py` - Filter tests (Phase 4)

**Note:** Only update `task.py` and related tests in this phase. Other files are updated in later phases.

## Backwards Compatibility

### Existing Task Files

Files with standard states continue to work:
```yaml
---
title: "My Task"
state: todo          # String "todo" works
priority: medium
---
```

### Legacy Code

Code using `TaskState` enum still works for comparisons:
```python
from kosmos.models import TaskState

# This still works
if task.state == TaskState.TODO.value:
    print("Todo!")

# But this is preferred now
if task.state == "todo":
    print("Todo!")
```

## Testing Strategy

### Unit Tests

```python
class TestTaskStateMigration:
    def test_state_is_string(self):
        task = Task(filename="test.md")
        assert isinstance(task.state, str)

    def test_default_state_value(self):
        task = Task(filename="test.md")
        assert task.state == "todo"

    def test_custom_state_allowed(self):
        task = Task(filename="test.md", state="backlog")
        assert task.state == "backlog"

    def test_from_frontmatter_standard_state(self):
        task = Task.from_frontmatter(
            filename="test.md",
            metadata={"state": "in_progress"},
            body="",
        )
        assert task.state == "in_progress"

    def test_from_frontmatter_custom_state(self):
        task = Task.from_frontmatter(
            filename="test.md",
            metadata={"state": "review"},
            body="",
        )
        assert task.state == "review"

    def test_from_frontmatter_missing_state(self):
        task = Task.from_frontmatter(
            filename="test.md",
            metadata={},
            body="",
        )
        assert task.state == "todo"

    def test_to_frontmatter_string_state(self):
        task = Task(filename="test.md", state="review")
        fm = task.to_frontmatter()
        assert fm["state"] == "review"

    def test_to_frontmatter_roundtrip(self):
        original = Task(
            filename="test.md",
            title="Test",
            state="custom_state",
            priority=Priority.HIGH,
        )
        fm = original.to_frontmatter()
        restored = Task.from_frontmatter(
            filename="test.md",
            metadata=fm,
            body="",
        )
        assert restored.state == "custom_state"
```

### Integration Test

```python
def test_existing_task_file_loads(task_dir: Path):
    """Ensure existing task files with standard states still load."""
    task_file = task_dir / "existing-task.md"
    task_file.write_text("""---
title: "Existing Task"
state: in_progress
priority: high
---
Task body here.
""")

    repo = FilesystemRepository(task_dir)
    tasks = repo.get_all()

    assert len(tasks) == 1
    assert tasks[0].state == "in_progress"
    assert tasks[0].title == "Existing Task"
```

## Verification Steps

1. Run `uv run pytest tests/test_models.py -v` - all tests pass
2. Run `uv run pytest` - full test suite passes
3. Start app with existing task files - tasks display correctly
4. Create new task via app - state saved correctly
5. Edit task file manually with custom state - loads without error

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|

## Completion Notes

**Phase 2 status: Pending**

## Key Notes

- `TaskState` enum is preserved but deprecated for backwards compatibility
- String states allow any value - validation happens at ConfigService level (Phase 4)
- Priority remains an enum (no change needed)
- This phase focuses only on Task model - Board/Service/UI changes come in later phases
- Existing test files may temporarily fail until Phase 4 updates filter/service tests
