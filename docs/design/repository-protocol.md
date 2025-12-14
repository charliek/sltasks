# Repository Protocol

This document describes the repository protocol that enables sltasks to support multiple task storage backends.

## Overview

The `RepositoryProtocol` defines a contract for task storage backends. This allows the application to work with different data sources:

- **Filesystem** - Markdown files with YAML frontmatter (current implementation)
- **GitHub Projects** - GitHub project items via GraphQL API (planned)
- **GitHub PRs** - Pull requests via REST API (planned)
- **Jira** - Jira issues via REST API (planned)

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

    def rename_in_board_order(self, old_task_id: str, new_task_id: str) -> None:
        """Rename a task in the board order (filesystem-specific)."""
        ...

    def validate(self) -> tuple[bool, str | None]:
        """Validate provider connectivity and configuration.

        Returns (is_valid, error_message_if_invalid).
        """
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

Creates a new task or updates an existing one. Returns the saved task, which may have updated fields (e.g., `provider_data` for filesystem, `updated` timestamp).

**Implementation notes:**
- Should update `task.updated` timestamp automatically
- For new tasks, should add to board order in the appropriate column
- For existing tasks, should not change board order position
- Should set appropriate `provider_data` for the backend

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

### `rename_in_board_order(old_task_id, new_task_id)`

Renames a task ID in the board order. This is primarily used by the filesystem provider when task files are renamed to match their title.

**Implementation notes:**
- Should update all references in board order from old_task_id to new_task_id
- Called by TaskService.rename_task_to_match_title()
- Non-filesystem providers may implement as no-op

### `validate()`

Validates provider connectivity and configuration. Returns a tuple of `(is_valid, error_message)`.

**Implementation notes:**
- Filesystem: Validates directory is accessible and writable
- Remote providers: Validates credentials, connectivity, and resource access
- Should be called during startup to catch configuration errors early
- Returns `(True, None)` on success, `(False, "error message")` on failure

## Provider Data

Tasks include a `provider_data` field containing backend-specific metadata. This uses a discriminated union pattern:

```python
from typing import Literal
from pydantic import BaseModel

class FileProviderData(BaseModel):
    """Provider data for filesystem tasks."""
    provider: Literal["file"] = "file"
    # filepath is derived from task.id + task_root

class GitHubProviderData(BaseModel):
    """Provider data for GitHub Projects tasks."""
    provider: Literal["github"] = "github"
    project_item_id: str          # For GraphQL mutations
    issue_node_id: str            # For GraphQL queries
    repository: str               # "owner/repo"
    issue_number: int
    type_label: str | None = None
    priority_label: str | None = None

class GitHubPRProviderData(BaseModel):
    """Provider data for GitHub PR tasks."""
    provider: Literal["github-prs"] = "github-prs"
    owner: str
    repo: str
    pr_number: int
    head_branch: str
    base_branch: str
    author: str
    # ... additional PR-specific fields

class JiraProviderData(BaseModel):
    """Provider data for Jira tasks."""
    provider: Literal["jira"] = "jira"
    issue_key: str                # "PROJ-123"
    project_key: str              # "PROJ"

ProviderData = FileProviderData | GitHubProviderData | GitHubPRProviderData | JiraProviderData
```

This allows type-safe access to provider-specific fields while keeping the Task model generic.

## Filesystem Implementation

The `FilesystemRepository` is the reference implementation:

- Tasks are stored as `.md` files with YAML frontmatter
- Board order is stored in `tasks.yaml`
- File state is the source of truth (overrides YAML column placement)
- State aliases are normalized on load
- Tasks receive `FileProviderData` with `provider="file"`
- Filepath is derived from `task_root / task.id`

### Additional Filesystem-Specific Methods

The filesystem implementation includes methods not in the protocol:

- `ensure_directory()` - Creates the task directory if needed
- `get_filepath(task)` - Returns the full path to a task file

## Configuration

The `SltasksConfig` model includes a `provider` field to select the backend:

```yaml
version: 1
provider: file  # "file", "github", "github-prs", or "jira"
task_root: .tasks
board:
  # ... column and type configuration
```

### Canonical Aliases for External Providers

When writing back to external systems (GitHub labels, Jira fields), types and priorities can specify a `canonical_alias` - the exact string to use when writing:

```yaml
board:
  types:
    - id: bug
      type_alias: [Bug, Defect, bug-label]
      canonical_alias: bug-label  # Use this when writing to GitHub

  priorities:
    - id: high
      priority_alias: [P1, priority:high]
      canonical_alias: priority:high  # Use this when writing to GitHub
```

If `canonical_alias` is not set, the `id` is used for write operations.

## Future Extensions

When implementing new backends, consider:

1. **Capability flags** - Not all backends support all operations (e.g., some may be read-only)
2. **Provider mappings** - Priority/type values may need mapping (e.g., Jira priority IDs)
3. **Synchronization** - Two-way sync between local and remote data
4. **Rate limiting** - API quotas for remote backends
5. **Authentication** - Token management for remote services

These will be added when needed for specific integrations.
