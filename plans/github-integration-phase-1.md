# GitHub Projects Integration

This document outlines the design and implementation of the GitHub Projects integration for sltasks.

## Design

### Repository Protocol

To support multiple backends (Filesystem, GitHub, Jira), we introduced a `RepositoryProtocol` that defines the contract for data storage:

- `get_all()`: Retrieve all tasks.
- `get_by_id(id)`: Retrieve a single task.
- `save(task)`: Create or update a task.
- `delete(id)`: Delete a task.
- `get_board_order()`: Get the column ordering.
- `capabilities`: A `RepositoryCapabilities` object indicating supported features.

### GitHub Repository (Phase 1)

The `GitHubRepository` implements the protocol for GitHub Projects V2 using the GraphQL API.

**Capabilities:**
- Read-only (`can_create=False`, etc.) for Phase 1.
- Tasks are fetched from the configured project.
- Task status is mapped to board columns via `sltasks.yml`.

**Configuration:**
In `sltasks.yml`:
```yaml
backend: github
github:
  project_url: "https://github.com/users/myuser/projects/1"
  # Optional: Map GitHub statuses to board columns
  # column_mapping will use status_alias in board columns
```

## Setup

1.  **Dependencies**: `httpx` is required.
2.  **Environment**: `GITHUB_TOKEN` must be set with `read:project`, `project`, and `repo` scopes.
3.  **Config**: Set `backend: github` and provide `project_url`.

## Future Phases

-   **Phase 2**: Write support (moving cards updates GitHub status).
-   **Phase 3**: Creation support (requires repository selection logic).
-   **Phase 4**: Caching and performance improvements.
