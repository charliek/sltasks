# Phase 3: Repository Layer

## Overview

This phase implements the `FilesystemRepository` class that handles all file I/O operations. It reads task files from the `.tasks/` directory, parses their YAML front matter, and manages the `tasks.yaml` ordering file. The repository is the boundary between the application and the filesystem.

## Goals

1. Scan `.tasks/` directory for markdown files
2. Parse YAML front matter using python-frontmatter
3. Load and save the tasks.yaml ordering file
4. Implement reconciliation logic (files are truth, yaml provides order)
5. Provide CRUD operations for tasks
6. Design for future file watching support (reload method)

## Task Checklist

- [ ] Create `src/kosmos/repositories/filesystem.py`:
  - [ ] `FilesystemRepository` class
  - [ ] `__init__(task_root: Path)` constructor
  - [ ] `get_all() -> list[Task]` - load all tasks
  - [ ] `get_by_id(filename: str) -> Task | None` - load single task
  - [ ] `save(task: Task) -> Task` - create or update task file
  - [ ] `delete(filename: str) -> None` - remove task file
  - [ ] `get_board_order() -> BoardOrder` - load tasks.yaml
  - [ ] `save_board_order(order: BoardOrder) -> None` - save tasks.yaml
  - [ ] `reload() -> None` - refresh from filesystem
  - [ ] `ensure_directory() -> None` - create .tasks if missing
- [ ] Implement reconciliation logic:
  - [ ] If file exists but not in yaml, add to yaml
  - [ ] If file's state differs from yaml column, use file's state
  - [ ] If yaml references missing file, remove from yaml
- [ ] Update `src/kosmos/repositories/__init__.py` with exports
- [ ] Write integration tests for file operations

## Detailed Specifications

### FilesystemRepository (repositories/filesystem.py)

```python
from pathlib import Path
from typing import Iterator
import frontmatter
import yaml

from ..models import Task, BoardOrder, TaskState


class FilesystemRepository:
    """
    Repository for task files stored on the filesystem.

    Tasks are stored as individual .md files with YAML front matter.
    Ordering is maintained in a tasks.yaml file.
    """

    TASKS_YAML = "tasks.yaml"

    def __init__(self, task_root: Path) -> None:
        """
        Initialize repository.

        Args:
            task_root: Path to the tasks directory (e.g., .tasks/)
        """
        self.task_root = task_root
        self._tasks: dict[str, Task] = {}
        self._board_order: BoardOrder | None = None

    def ensure_directory(self) -> None:
        """Create the tasks directory if it doesn't exist."""
        self.task_root.mkdir(parents=True, exist_ok=True)

    # --- Task Operations ---

    def get_all(self) -> list[Task]:
        """Load and return all tasks from the filesystem."""
        self._load_tasks()
        self._load_board_order()
        self._reconcile()
        return self._sorted_tasks()

    def get_by_id(self, filename: str) -> Task | None:
        """Load a single task by filename."""
        filepath = self.task_root / filename
        if not filepath.exists():
            return None
        return self._parse_task_file(filepath)

    def save(self, task: Task) -> Task:
        """
        Save a task to the filesystem.

        Creates or updates the markdown file with front matter.
        Updates the tasks.yaml ordering.
        """
        self.ensure_directory()

        filepath = self.task_root / task.filename
        task.filepath = filepath

        # Build front matter document
        post = frontmatter.Post(task.body)
        post.metadata = task.to_frontmatter()

        # Write file
        with open(filepath, "w") as f:
            f.write(frontmatter.dumps(post))

        # Update board order
        self._ensure_board_order()
        self._board_order.add_task(task.filename, task.state.value)
        self._save_board_order()

        return task

    def delete(self, filename: str) -> None:
        """Delete a task file from the filesystem."""
        filepath = self.task_root / filename
        if filepath.exists():
            filepath.unlink()

        # Remove from board order
        self._ensure_board_order()
        self._board_order.remove_task(filename)
        self._save_board_order()

    # --- Board Order Operations ---

    def get_board_order(self) -> BoardOrder:
        """Load and return the board order."""
        self._load_board_order()
        return self._board_order

    def save_board_order(self, order: BoardOrder) -> None:
        """Save the board order to tasks.yaml."""
        self._board_order = order
        self._save_board_order()

    # --- Reload Support ---

    def reload(self) -> None:
        """Clear caches and reload from filesystem."""
        self._tasks.clear()
        self._board_order = None

    # --- Private Methods ---

    def _load_tasks(self) -> None:
        """Scan directory and load all task files."""
        self._tasks.clear()

        if not self.task_root.exists():
            return

        for filepath in self._iter_task_files():
            task = self._parse_task_file(filepath)
            if task:
                self._tasks[task.filename] = task

    def _iter_task_files(self) -> Iterator[Path]:
        """Iterate over all .md files in the task root."""
        for filepath in self.task_root.glob("*.md"):
            yield filepath

    def _parse_task_file(self, filepath: Path) -> Task | None:
        """Parse a single task file."""
        try:
            post = frontmatter.load(filepath)
            return Task.from_frontmatter(
                filename=filepath.name,
                metadata=post.metadata,
                body=post.content,
                filepath=filepath,
            )
        except Exception:
            # Skip files that can't be parsed
            # TODO: Consider logging this
            return None

    def _load_board_order(self) -> None:
        """Load tasks.yaml if it exists."""
        if self._board_order is not None:
            return

        yaml_path = self.task_root / self.TASKS_YAML
        if yaml_path.exists():
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            self._board_order = BoardOrder(**data)
        else:
            self._board_order = BoardOrder()

    def _ensure_board_order(self) -> None:
        """Ensure board order is loaded."""
        if self._board_order is None:
            self._load_board_order()

    def _save_board_order(self) -> None:
        """Write tasks.yaml to disk."""
        self.ensure_directory()
        yaml_path = self.task_root / self.TASKS_YAML

        data = self._board_order.model_dump()
        with open(yaml_path, "w") as f:
            f.write("# Auto-generated - do not edit manually\n")
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def _reconcile(self) -> None:
        """
        Reconcile tasks with board order.

        - Files are the source of truth for task state
        - YAML provides ordering within columns
        - Missing files are removed from YAML
        - New files are added to YAML based on their state
        """
        self._ensure_board_order()
        modified = False

        # Get set of actual task filenames
        actual_files = set(self._tasks.keys())

        # Remove references to missing files from yaml
        for state, filenames in list(self._board_order.columns.items()):
            for filename in filenames[:]:  # Copy list for safe iteration
                if filename not in actual_files:
                    self._board_order.columns[state].remove(filename)
                    modified = True

        # Add new files and fix misplaced files
        all_in_yaml = set()
        for filenames in self._board_order.columns.values():
            all_in_yaml.update(filenames)

        for filename, task in self._tasks.items():
            state_value = task.state.value

            if filename not in all_in_yaml:
                # New file - add to appropriate column
                self._board_order.add_task(filename, state_value)
                modified = True
            else:
                # Check if in wrong column (file state takes precedence)
                current_column = self._find_task_column(filename)
                if current_column and current_column != state_value:
                    self._board_order.move_task(filename, current_column, state_value)
                    modified = True

        if modified:
            self._save_board_order()

    def _find_task_column(self, filename: str) -> str | None:
        """Find which column a task is currently in."""
        for state, filenames in self._board_order.columns.items():
            if filename in filenames:
                return state
        return None

    def _sorted_tasks(self) -> list[Task]:
        """Return tasks sorted by their board order position."""
        # Build a position map for sorting
        position_map: dict[str, tuple[int, int]] = {}

        state_order = ["todo", "in_progress", "done", "archived"]
        for state_idx, state in enumerate(state_order):
            filenames = self._board_order.columns.get(state, [])
            for pos_idx, filename in enumerate(filenames):
                position_map[filename] = (state_idx, pos_idx)

        def sort_key(task: Task) -> tuple[int, int, str]:
            if task.filename in position_map:
                state_idx, pos_idx = position_map[task.filename]
                return (state_idx, pos_idx, task.filename)
            # Tasks not in yaml go to end
            return (999, 999, task.filename)

        return sorted(self._tasks.values(), key=sort_key)
```

## Reconciliation Logic

The repository performs automatic reconciliation between task files and the ordering YAML:

```
┌─────────────────┐     ┌─────────────────┐
│  Task Files     │     │   tasks.yaml    │
│  (.md files)    │     │   (ordering)    │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
              ┌──────▼──────┐
              │ Reconcile   │
              └──────┬──────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
   File exists but          File missing but
   not in yaml?             referenced in yaml?
         │                       │
         ▼                       ▼
   Add to yaml              Remove from yaml
   (use file's state)       (clean up stale ref)
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
            File state differs
            from yaml column?
                     │
                     ▼
            Move to correct column
            (file wins)
```

## File Format

### Task File (.md)

```markdown
---
title: "Fix login timeout bug"
state: todo
priority: high
tags: [bug, auth]
created: 2025-01-01T12:00:00Z
updated: 2025-01-02T14:00:00Z
---

## Description

Task content here...
```

### Ordering File (tasks.yaml)

```yaml
# Auto-generated - do not edit manually
version: 1
columns:
  todo:
    - fix-login-bug.md
    - add-user-auth.md
  in_progress:
    - refactor-api.md
  done:
    - setup-ci.md
  archived:
    - old-feature.md
```

## Error Handling

- Files that can't be parsed are skipped (not fatal)
- Missing `.tasks/` directory is created automatically
- Missing `tasks.yaml` is created with empty structure

## Testing Notes

Integration tests should:
- Create a temp directory with sample .md files
- Verify `get_all()` returns correct tasks
- Verify `save()` writes proper front matter format
- Verify reconciliation updates yaml correctly
- Verify state changes in files update yaml columns

## Deviations from Plan

_This section will be updated if implementation differs from the plan._

| Date | Deviation | Reason |
|------|-----------|--------|
| - | - | - |

## Key Notes

- The repository caches tasks after loading - call `reload()` to refresh
- File state always takes precedence over yaml column placement
- The `_tasks` dict uses filename as key for O(1) lookup
- We use `frontmatter.dumps()` to preserve content formatting
- The yaml file header warns users not to edit manually
