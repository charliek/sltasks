# Status Alias Feature Implementation Plan

## Overview

This plan implements a `status_alias` feature for sltasks column configuration. Status aliases allow users to define alternative status values that map to a column's primary ID. When a task has a status matching an alias, it will be placed in the corresponding column, and when saved, the status will be normalized to the column's primary ID.

### Use Case

Users may have existing task files with various status values (e.g., "completed", "finished", "complete") that should all map to the "done" column. Rather than manually editing all files, they can configure aliases.

### Example Configuration

```yaml
version: 1
task_root: .tasks
board:
  columns:
  - id: todo
    title: To Do
    status_alias:
      - new
  - id: in_progress
    title: In Progress
  - id: done
    title: Done
    status_alias:
      - completed
      - finished
      - complete
```

## Design Decisions

### Key Behavior

1. **Alias resolution at load time**: When loading a task from a markdown file, if its `state` matches an alias, the state is immediately normalized to the canonical column ID. The original alias value is not preserved in memory.
2. **State normalization on save**: When a task is saved, it writes the canonical column ID (since that's what's in memory). Files with alias states get normalized when the task is next saved (e.g., via edit, move, archive).
3. **Aliases are optional**: Columns without `status_alias` work exactly as before
4. **Default aliases**: Built-in default aliases for common variations (see below)
5. **Alias validation**: Aliases must follow same rules as column IDs (lowercase, alphanumeric, underscores)
6. **No alias conflicts**: Aliases cannot duplicate column IDs or other aliases - validation error if attempted
7. **Non-breaking change**: Existing configs without `status_alias` continue to work (field defaults to empty list)

### Default Aliases

When no `sltasks.yml` exists (or when columns don't specify aliases), these defaults apply:

| Column ID | Default Aliases |
|-----------|-----------------|
| `todo` | `new` |
| `in_progress` | (none) |
| `done` | `completed`, `finished`, `complete` |

These defaults are only applied to columns with matching IDs. Custom columns get no default aliases unless explicitly configured.

## Task Checklist

### Phase 1: Model Changes

- [ ] Update `ColumnConfig` model in `src/sltasks/models/sltasks_config.py`:
  - [ ] Add `status_alias: list[str] = Field(default_factory=list)` field
  - [ ] Add validator to ensure aliases follow column ID format rules (lowercase, alphanumeric, underscores, starts with letter)

- [ ] Update `BoardConfig` model in `src/sltasks/models/sltasks_config.py`:
  - [ ] Add validator to ensure no alias duplicates a column ID
  - [ ] Add validator to ensure no alias duplicates another alias (across all columns)
  - [ ] Add validator to ensure no alias equals "archived" (reserved)
  - [ ] Add `resolve_status(status: str) -> str` method that returns canonical column ID for a status (or the status unchanged if not found)
  - [ ] Add `get_column_for_status(status: str) -> str | None` method that returns the column ID for a status or alias
  - [ ] Update `is_valid_status(status: str)` to also accept aliases as valid

- [ ] Update `BoardConfig.default()` to include default aliases:
  - [ ] `todo` column: `status_alias: ["new"]`
  - [ ] `done` column: `status_alias: ["completed", "finished", "complete"]`

### Phase 2: Board Model Changes

- [ ] Update `Board.from_tasks()` in `src/sltasks/models/board.py`:
  - [ ] Use `BoardConfig.get_column_for_status()` to resolve task state to column
  - [ ] This replaces direct column ID lookup with alias-aware lookup

### Phase 3: Service Layer Changes

- [ ] Update `TaskService.create_task()` in `src/sltasks/services/task_service.py`:
  - [ ] Ensure new tasks always use canonical column ID (not alias)
  - [ ] No changes needed if state parameter already uses column ID

- [ ] Update `BoardService` in `src/sltasks/services/board_service.py`:
  - [ ] Update `move_task()` to always use canonical column ID
  - [ ] Update `_previous_state()` and `_next_state()` to work with canonical IDs only
  - [ ] These should already work correctly since they navigate by column ID

### Phase 4: Repository Layer Changes

- [ ] Update `FilesystemRepository._parse_task_file()` in `src/sltasks/repositories/filesystem.py`:
  - [ ] After creating the Task object, normalize its state using `config.resolve_status()`
  - [ ] This ensures the internal representation always uses canonical column IDs
  - [ ] Add `logger.debug()` call when an alias is resolved (silent by default, useful for future debugging)

- [ ] Update `FilesystemRepository._reconcile()`:
  - [ ] No changes needed for alias handling (normalization happens at load time)
  - [ ] The existing "wrong column" check will work because task.state is already canonical

**Note on normalization timing**: Normalization happens at load time in `_parse_task_file()`. The original alias value in the markdown file is preserved until the task is next saved (via edit, move, etc.). This is intentional - we don't rewrite files just because they have an alias state.

### Phase 5: Tests

- [ ] Add tests to `tests/test_sltasks_config.py`:
  - [ ] Test `ColumnConfig` with valid aliases
  - [ ] Test `ColumnConfig` with invalid alias format (uppercase, starts with number, etc.)
  - [ ] Test `BoardConfig` default includes expected aliases
  - [ ] Test `BoardConfig` rejects alias that duplicates column ID
  - [ ] Test `BoardConfig` rejects alias that duplicates another alias
  - [ ] Test `BoardConfig` rejects "archived" as alias
  - [ ] Test `BoardConfig.resolve_status()` returns canonical ID for alias
  - [ ] Test `BoardConfig.resolve_status()` returns canonical ID unchanged
  - [ ] Test `BoardConfig.resolve_status()` returns unknown status unchanged
  - [ ] Test `BoardConfig.get_column_for_status()` returns correct column for alias
  - [ ] Test `BoardConfig.is_valid_status()` returns True for aliases

- [ ] Add tests to `tests/test_config_service.py`:
  - [ ] Test loading config with custom aliases
  - [ ] Test default config has expected aliases
  - [ ] Test fallback on invalid aliases (duplicate, reserved)

- [ ] Add tests to `tests/test_models.py` for Board:
  - [ ] Test task with alias state is placed in correct column
  - [ ] Test multiple tasks with different aliases for same column

- [ ] Add tests to `tests/test_repository.py`:
  - [ ] Test task with alias state is loaded correctly
  - [ ] Test task with alias state is normalized when saved
  - [ ] Test reconciliation normalizes alias states

- [ ] Add tests to `tests/test_board_service.py`:
  - [ ] Test moving task updates to canonical ID (not alias)

### Phase 6: Update --generate Command

- [ ] Update `src/sltasks/cli/generate.py`:
  - [ ] Update `CONFIG_HEADER` comments to document `status_alias` field
  - [ ] Exclude empty `status_alias` fields from YAML output for cleaner generated config (columns with aliases will show them, columns without will omit the field entirely)
  - [ ] Update `generate_config_yaml()` to use custom serialization or post-process the YAML to remove empty `status_alias: []` entries

- [ ] Add test to `tests/test_cli_generate.py` (or appropriate test file):
  - [ ] Test that generated config includes `status_alias` for columns that have them (todo, done)
  - [ ] Test that generated config omits `status_alias` for columns without aliases (in_progress)

**Note**: The `--generate` command uses `SltasksConfig.default()` as its source of truth (line 77 of `generate.py`), so updating `BoardConfig.default()` in Phase 1 will automatically include aliases in generated configs. This phase handles the output formatting.

### Phase 7: Documentation

- [ ] Update `docs/user-guide/configuration.md`:
  - [ ] Add `status_alias` to column configuration table
  - [ ] Add example configuration with aliases
  - [ ] Document default aliases
  - [ ] Explain normalization behavior

### Phase 8: Final Verification

- [ ] Run full test suite: `uv run pytest`
- [ ] Manual testing:
  - [ ] Create task file with alias state (e.g., `state: completed`)
  - [ ] Verify task appears in correct column
  - [ ] Edit task in TUI and verify state is normalized to canonical ID
  - [ ] Test with custom config including aliases
  - [ ] Test with default config (no sltasks.yml)
- [ ] Update this plan with any deviations and completion notes

## Detailed Implementation

### ColumnConfig Changes

```python
# src/sltasks/models/sltasks_config.py

class ColumnConfig(BaseModel):
    """Configuration for a single board column."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    status_alias: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        # ... existing validation ...

    @field_validator("status_alias")
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        """Validate that aliases follow column ID format rules."""
        for alias in v:
            if not alias:
                raise ValueError("Alias cannot be empty")
            if not alias[0].isalpha():
                raise ValueError(f"Alias '{alias}' must start with a letter")
            if not alias.islower():
                raise ValueError(f"Alias '{alias}' must be lowercase")
            if not all(c.isalnum() or c == "_" for c in alias):
                raise ValueError(
                    f"Alias '{alias}' can only contain lowercase letters, numbers, and underscores"
                )
        return v
```

### BoardConfig Changes

```python
# src/sltasks/models/sltasks_config.py

class BoardConfig(BaseModel):
    """Configuration for board columns."""

    columns: list[ColumnConfig] = Field(..., min_length=2, max_length=6)

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v: list[ColumnConfig]) -> list[ColumnConfig]:
        # ... existing ID uniqueness and "archived" validation ...

        # Collect all column IDs
        ids = [col.id for col in v]

        # Collect all aliases
        all_aliases: list[str] = []
        for col in v:
            all_aliases.extend(col.status_alias)

        # Check no alias duplicates a column ID
        for alias in all_aliases:
            if alias in ids:
                raise ValueError(f"Alias '{alias}' conflicts with column ID")

        # Check no alias duplicates another alias
        if len(all_aliases) != len(set(all_aliases)):
            raise ValueError("Duplicate alias found across columns")

        # Check no alias is "archived"
        if "archived" in all_aliases:
            raise ValueError("'archived' is reserved and cannot be used as an alias")

        return v

    def resolve_status(self, status: str) -> str:
        """
        Resolve a status to its canonical column ID.

        If status matches a column ID, returns it unchanged.
        If status matches an alias, returns the column's primary ID.
        If status is unknown, returns it unchanged.
        """
        # Check if it's already a column ID
        if status in self.column_ids:
            return status

        # Check if it's an alias
        for col in self.columns:
            if status in col.status_alias:
                return col.id

        # Unknown status - return unchanged (let caller handle)
        return status

    def get_column_for_status(self, status: str) -> str | None:
        """
        Get the column ID for a status (including aliases).

        Returns None if status is not a valid column ID or alias.
        """
        # Check if it's a column ID
        if status in self.column_ids:
            return status

        # Check if it's "archived"
        if status == "archived":
            return "archived"

        # Check if it's an alias
        for col in self.columns:
            if status in col.status_alias:
                return col.id

        return None

    def is_valid_status(self, status: str) -> bool:
        """Check if status is valid (column ID, alias, or 'archived')."""
        return self.get_column_for_status(status) is not None

    @classmethod
    def default(cls) -> "BoardConfig":
        """Return default 3-column configuration with default aliases."""
        return cls(
            columns=[
                ColumnConfig(id="todo", title="To Do", status_alias=["new"]),
                ColumnConfig(id="in_progress", title="In Progress"),
                ColumnConfig(id="done", title="Done", status_alias=["completed", "finished", "complete"]),
            ]
        )
```

### Board.from_tasks() Changes

```python
# src/sltasks/models/board.py

@classmethod
def from_tasks(
    cls,
    tasks: list[Task],
    ordering: BoardOrder,
    config: BoardConfig,
) -> "Board":
    """Create a Board from a list of tasks, ordered by BoardOrder."""
    # ... existing initialization ...

    for task in tasks:
        # Resolve status to canonical column ID (handles aliases)
        column_id = config.get_column_for_status(task.state)

        if column_id is not None and column_id in board.columns:
            board.columns[column_id].append(task)
        else:
            # Unknown state - place in first column
            unknown_states.add(task.state)
            first_col = config.columns[0].id
            board.columns[first_col].append(task)

    # ... rest of method ...
```

### Repository Changes

```python
# src/sltasks/repositories/filesystem.py

import logging

logger = logging.getLogger(__name__)

def _parse_task_file(self, filepath: Path) -> Task | None:
    """Parse a single task file."""
    try:
        post = frontmatter.load(filepath)
        task = Task.from_frontmatter(
            filename=filepath.name,
            metadata=post.metadata,
            body=post.content,
            filepath=filepath,
        )

        # Normalize alias states to canonical column IDs
        config = self._get_board_config()
        canonical_state = config.resolve_status(task.state)
        if canonical_state != task.state:
            logger.debug(
                f"Resolved alias '{task.state}' to '{canonical_state}' for {filepath.name}"
            )
            task.state = canonical_state

        return task
    except Exception:
        # Skip files that can't be parsed
        return None
```

**Note**: The `_reconcile()` method does not need changes for alias handling since normalization happens at load time. Tasks always have canonical states in memory.

## File Changes Summary

| File | Changes |
|------|---------|
| `src/sltasks/models/sltasks_config.py` | Add `status_alias` field, validators, `resolve_status()`, update `get_column_for_status()`, `is_valid_status()`, `default()` |
| `src/sltasks/models/board.py` | Update `from_tasks()` to use alias resolution |
| `src/sltasks/repositories/filesystem.py` | Add state normalization in `_reconcile()` |
| `src/sltasks/cli/generate.py` | Update `CONFIG_HEADER` comments, optionally clean up empty alias lists in output |
| `docs/user-guide/configuration.md` | Document `status_alias` feature |
| `tests/test_sltasks_config.py` | Add alias validation and resolution tests |
| `tests/test_config_service.py` | Add alias loading tests |
| `tests/test_models.py` | Add Board alias placement tests |
| `tests/test_repository.py` | Add alias normalization tests |
| `tests/test_board_service.py` | Add move task normalization test |

## Execution Notes

When executing this plan:

1. **Update checkboxes**: Mark each `[ ]` as `[x]` when completed
2. **Document deviations**: If implementation differs from plan, add a note in the "Deviations" section below
3. **Run tests frequently**: Run `uv run pytest` after each phase to catch regressions early
4. **Commit after each phase**: Keep commits focused and atomic

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|
| | | |

## Completion Notes

**Status: Not Started**

(Add notes here when complete, including files created/modified, test counts, etc.)
