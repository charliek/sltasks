# GitHub Projects Integration Phase 1

This document details the implementation of the GitHub Projects V2 integration for sltasks.

## Overview

The goal of this feature is to allow `sltasks` to fetch and display tasks directly from a GitHub Project V2 board. This implementation is "Phase 1", which focuses on a **read-only** view. This ensures stability and allows users to visualize their work without risking accidental modifications while the feature is in beta.

## Architecture

### Repository Abstraction

Previously, `sltasks` was tightly coupled to the filesystem. To support GitHub (and future backends like Jira), we introduced a `RepositoryProtocol` abstraction.

```python
class RepositoryProtocol(Protocol):
    @property
    def capabilities(self) -> RepositoryCapabilities: ...
    def get_all(self) -> list[Task]: ...
    def get_by_id(self, filename: str) -> Task | None: ...
    def save(self, task: Task) -> Task: ...
    def delete(self, filename: str) -> None: ...
    # ... board order methods ...
```

This decoupling allows the application services (`TaskService`, `BoardService`) to operate on generic tasks without knowing the underlying storage mechanism.

### Repository Capabilities

To handle the differences between backends (e.g., read-only vs. read-write), we introduced `RepositoryCapabilities`.

```python
class RepositoryCapabilities(BaseModel):
    can_create: bool = True
    can_edit: bool = True
    can_delete: bool = True
    can_move_column: bool = True
    can_reorder: bool = True
    can_archive: bool = True
```

The UI (`BoardScreen`) uses these flags to dynamically enable or disable features. For the GitHub backend in Phase 1, all modification capabilities are set to `False`.

### GitHub Implementation (`GitHubRepository`)

The `GitHubRepository` class implements the `RepositoryProtocol` using the GitHub GraphQL API.

-   **Authentication**: Uses a `GITHUB_TOKEN` environment variable.
-   **Fetching**: Queries the `projectV2` API to fetch items (Issues and Pull Requests).
-   **Mapping**:
    -   **ID**: The task `filename` maps to `owner/repo#number` (e.g., `charliek/sltasks#123`).
    -   **Status**: The Project "Status" field is mapped to sltasks columns.
    -   **Priority/Type**: Labels are parsed to determine priority (e.g., `priority:high`) and type (e.g., `type:bug`).

## Configuration Design

Users configure the backend in `sltasks.yml`. The design allows for easy switching between backends.

```yaml
backend: github  # Default is 'filesystem'

github:
  project_url: "https://github.com/users/charliek/projects/2"
  include_closed: false
  include_prs: true
```

## Future Roadmap

This foundation sets the stage for future enhancements:

### Phase 2: State Management (Write Access)
-   **Goal**: Allow moving tasks between columns in the TUI to update the Status in GitHub.
-   **Technical**: Implement `can_move_column=True`. Use the `updateProjectV2ItemFieldValue` mutation.
-   **Challenge**: Handling permissions and optimistic UI updates.

### Phase 3: Task Creation & Editing
-   **Goal**: Create new issues from the TUI.
-   **Technical**: Implement `can_create=True`. Requires selecting a target repository (since a Project can span multiple repos).
-   **UI**: A "Repository Selector" modal will be needed.

### Phase 4: Offline Caching & Performance
-   **Goal**: Faster startup and offline viewing.
-   **Technical**: Cache the GraphQL response or mapped tasks locally. Implement a "sync" command to refresh.

### Phase 5: Advanced Filtering
-   **Goal**: Filter by assignee, milestone, or custom fields.
-   **Technical**: Expose more fields in the `Task` model and update the `FilterService`.

## Verification & Testing

The implementation was verified using a real GitHub Project (https://github.com/users/charliek/projects/2/views/1) ensuring that:
1.  URL parsing handles view suffixes correctly.
2.  Tasks (Issues) are correctly fetched and mapped to columns.
3.  The UI correctly disables "New Task", "Move", and "Edit" actions.
