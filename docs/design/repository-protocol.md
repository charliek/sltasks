# Repository Protocol

This document describes the repository protocol that enables sltasks to support multiple task storage backends.

## Overview

The `RepositoryProtocol` defines a contract for task storage backends. This allows the application to work with different data sources:

- **Filesystem** - Markdown files with YAML frontmatter (current implementation)
- **GitHub Projects** - GitHub project items via GraphQL API (future)
- **Jira** - Jira issues via REST API (future)

## Protocol Definition

```python
class RepositoryProtocol(Protocol):
    """Interface for task storage backends."""

    def get_all(self) -> list[Task]:
        """Load all tasks from the backend."""
        ...

    def get_by_id(self, task_id: str) -> Task | None:
        """Get a single task by ID."""
        ...

    def save(self, task: Task) -> Task:
        """Create or update a task. Returns saved task."""
        ...

    def delete(self, task_id: str) -> None:
        """Delete a task by ID."""
        ...

    def get_board_order(self) -> BoardOrder:
        """Get task ordering within columns."""
        ...

    def save_board_order(self, order: BoardOrder) -> None:
        """Save task ordering."""
        ...

    def reload(self) -> None:
        """Clear caches and reload from source."""
        ...
```

## Task ID Abstraction

Task IDs are strings that uniquely identify tasks within a repository. The format depends on the backend:

| Backend | ID Format | Examples |
|---------|-----------|----------|
| Filesystem | Filename | `fix-login-bug.md`, `add-feature.md` |
| GitHub Projects | Issue reference | `#123`, `owner/repo#456` |
| Jira | Issue key | `PROJ-123`, `MYAPP-456` |

The application treats IDs as opaque strings, allowing each backend to use its natural identifier format.

## Method Contracts

### `get_all()`

Returns all tasks from the backend, ordered by board position within each state column.

**Implementation notes:**
- Should include caching for performance
- Tasks should be ordered according to `get_board_order()` positions
- Archived tasks should be included in the result

### `get_by_id(task_id)`

Returns a single task by its identifier, or `None` if not found.

**Implementation notes:**
- May use cached data from `get_all()` if available
- Should be case-sensitive for IDs

### `save(task)`

Creates a new task or updates an existing one. Returns the saved task, which may have updated fields (e.g., `filepath` for filesystem, `updated` timestamp).

**Implementation notes:**
- Should update `task.updated` timestamp automatically
- For new tasks, should add to board order in the appropriate column
- For existing tasks, should not change board order position

### `delete(task_id)`

Removes a task by ID. Should not raise an error if the task doesn't exist.

**Implementation notes:**
- Should remove from board order as well
- Should clean up any associated resources

### `get_board_order()`

Returns the current task ordering within columns as a `BoardOrder` object.

**Implementation notes:**
- For filesystem, this is stored in `tasks.yaml`
- For remote backends, may be derived from API ordering

### `save_board_order(order)`

Persists changes to task ordering.

**Implementation notes:**
- Should validate that referenced task IDs exist
- May trigger reconciliation with actual task states

### `reload()`

Clears internal caches and forces a fresh load from the backend.

**Implementation notes:**
- Should be called after external changes (e.g., file edits, API updates)
- Next `get_all()` call should return fresh data

## Filesystem Implementation

The `FilesystemRepository` is the reference implementation:

- Tasks are stored as `.md` files with YAML frontmatter
- Board order is stored in `tasks.yaml`
- File state is the source of truth (overrides YAML column placement)
- State aliases are normalized on load

### Additional Filesystem-Specific Methods

The filesystem implementation includes methods not in the protocol:

- `ensure_directory()` - Creates the task directory if needed
- `rename_in_board_order(old_id, new_id)` - Handles task file renames

## Future Extensions

When implementing new backends, consider:

1. **Capability flags** - Not all backends support all operations (e.g., some may be read-only)
2. **Provider mappings** - Priority/type values may need mapping (e.g., Jira priority IDs)
3. **Synchronization** - Two-way sync between local and remote data
4. **Rate limiting** - API quotas for remote backends
5. **Authentication** - Token management for remote services

These will be added when needed for specific integrations.
