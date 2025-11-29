# Phase 12: Test Coverage for Regression Protection

## Overview

This phase adds targeted tests that provide maximum regression protection with minimal maintenance overhead. Following the project's testing philosophy: integration tests for workflows, unit tests only for complex/error-prone logic.

## Goals

1. Add service-level integration tests for TaskService and BoardService
2. Add unit tests for model edge cases (datetime parsing, invalid enum handling)
3. Focus on complex logic and boundary conditions
4. Avoid brittle tests that require mocking or break on UI changes

## Task Checklist

- [x] Create `tests/test_task_service.py`:
  - [x] `test_create_task_basic` - Happy path
  - [x] `test_create_task_in_specific_state` - State parameter works
  - [x] `test_create_task_unique_filename_collision` - Filename deduplication
  - [x] `test_create_task_multiple_collisions` - Handles 3+ same-title tasks
  - [x] `test_update_task_changes_updated_timestamp` - Timestamp auto-updated
  - [x] `test_delete_task_removes_file` - File removed, board order updated
  - [x] `test_get_task_returns_none_for_missing` - Graceful handling
- [x] Create `tests/test_board_service.py`:
  - [x] `test_load_board_groups_by_state` - Tasks in correct columns
  - [x] `test_move_task_updates_state_and_file` - State change persists
  - [x] `test_move_task_left_from_in_progress` - in_progress → todo
  - [x] `test_move_task_left_from_todo_stays` - Boundary: can't go left from first
  - [x] `test_move_task_right_from_done_stays` - Boundary: can't go right from last
  - [x] `test_move_task_from_archived_does_nothing` - Archived excluded from left/right
  - [x] `test_archive_task_changes_state` - Archive sets state
  - [x] `test_reorder_task_up` - Move task up within column
  - [x] `test_reorder_task_down` - Move task down within column
  - [x] `test_reorder_task_at_top_stays` - Boundary: can't move up from 0
  - [x] `test_reorder_task_at_bottom_stays` - Boundary: can't move down from last
- [x] Create `tests/test_models.py`:
  - [x] `test_task_from_frontmatter_invalid_state_uses_default` - Raises ValueError
  - [x] `test_task_from_frontmatter_invalid_priority_uses_default` - Raises ValueError
  - [x] `test_task_from_frontmatter_missing_state_uses_default` - Defaults to 'todo'
  - [x] `test_task_from_frontmatter_missing_priority_uses_default` - Defaults to 'medium'
  - [x] `test_task_display_title_with_title_set` - Returns title when set
  - [x] `test_task_display_title_without_title` - Filename transformation
  - [x] `test_task_display_title_complex_filename` - Multiple hyphens
  - [x] `test_parse_datetime_z_suffix` - ISO with 'Z' parsed as UTC
  - [x] `test_parse_datetime_explicit_offset` - ISO with +00:00
  - [x] `test_parse_datetime_none_returns_none` - Null handling
  - [x] `test_parse_datetime_passthrough` - datetime objects pass through
  - [x] `test_board_from_tasks_groups_all_states` - All 4 states sorted
  - [x] `test_board_from_tasks_empty_list` - Empty input handling
  - [x] `test_board_from_tasks_multiple_same_state` - Multiple tasks per state

## Detailed Specifications

### Test Pattern (Matching Existing Style)

Service tests use real temp directories (same as test_repository.py):

```python
# tests/test_task_service.py
import pytest
from pathlib import Path
from kosmos.repositories import FilesystemRepository
from kosmos.services import TaskService

@pytest.fixture
def task_root(tmp_path: Path) -> Path:
    """Create temp task directory."""
    task_dir = tmp_path / ".tasks"
    task_dir.mkdir()
    return task_dir

@pytest.fixture
def task_service(task_root: Path) -> TaskService:
    """Create TaskService with temp directory."""
    repo = FilesystemRepository(task_root)
    return TaskService(repo)

class TestTaskService:
    def test_create_task_unique_filename_collision(self, task_service: TaskService):
        """Creating tasks with same title generates unique filenames."""
        task1 = task_service.create_task("Fix Bug")
        task2 = task_service.create_task("Fix Bug")
        task3 = task_service.create_task("Fix Bug")

        assert task1.filename == "fix-bug.md"
        assert task2.filename == "fix-bug-1.md"
        assert task3.filename == "fix-bug-2.md"
```

### What NOT to Test

- **UI/Textual widgets** - Change frequently, require special testing setup
- **Simple passthroughs** - `get_task()`, `reload()` just delegate to repository
- **`open_in_editor()`** - Subprocess testing is brittle, editor availability varies
- **Already-tested operations** - Repository CRUD well covered in test_repository.py

## Testing Notes

Integration test scenarios verify:
1. TaskService filename collision handling (critical for data integrity)
2. BoardService state transitions respect column boundaries
3. BoardService reorder operations respect position boundaries
4. Model parsing handles invalid/missing values gracefully

All service tests use real filesystem via `tmp_path` fixture - no mocking.

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|
| 2025-11-29 | Invalid state/priority tests verify ValueError is raised | Pydantic enum validation raises ValueError, not default fallback |
| 2025-11-29 | Added additional model tests (14 total vs 7 planned) | Better coverage of display_title, datetime parsing, Board.from_tasks |

## Completion Notes

**Phase 12 completed on 2025-11-29**

Files created:
- `tests/test_task_service.py` - 7 integration tests
- `tests/test_board_service.py` - 11 integration tests
- `tests/test_models.py` - 14 unit tests

**Total: 32 new tests (93 total, up from 61)**

Test breakdown:
- TaskService: create (4), update (1), delete (1), get (1)
- BoardService: load (1), move (5), archive (1), reorder (4)
- Models: from_frontmatter (4), display_title (3), _parse_datetime (4), Board.from_tasks (3)

## Key Notes

- Tests focus on business logic complexity (services, model parsing)
- Uses real filesystem (no mocking) for service tests
- Catches regressions from state transitions and filename handling
- Won't break when UI code changes
- Won't require test changes for most code changes (stable interfaces)
