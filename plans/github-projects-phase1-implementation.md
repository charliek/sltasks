# GitHub Projects Integration - Phase 1 Implementation

## Overview

Phase 1 implements a **GitHub-only mode** for sltasks where GitHub Projects V2 is the source of truth. Issues from a GitHub Project are displayed in the sltasks TUI, and all changes (status updates, edits) are pushed directly to GitHub via the GraphQL API.

This phase does **not** include filesystem sync (saving issues as local markdown files). That is planned for Phase 2.

## Implementation Status: COMPLETE

All Phase 1 tasks have been implemented and tested:

- [x] Add httpx dependency
- [x] Add GitHubConfig model
- [x] Create GitHub GraphQL client
- [x] Create GraphQL query templates
- [x] Create GitHubProjectsRepository
- [x] Update app.py for provider selection
- [x] Test read-only flow with real GitHub project
- [x] Test mutations (move task between columns)
- [x] Update TaskService for GitHub edit workflow
- [x] Write unit tests (34 new tests, 291 total passing)

---

## Architecture

### Provider Selection Flow

```
sltasks.yml (provider: github)
         ↓
    ConfigService
         ↓
   app._init_services()
         ↓
   GitHubProjectsRepository (instead of FilesystemRepository)
         ↓
   GitHub GraphQL API
```

### Key Design Decisions

1. **Separate provider, not a mode**: `provider: github` creates a completely separate repository implementation rather than adding sync logic to FilesystemRepository.

2. **GitHub is source of truth**: All data comes from GitHub. No local caching beyond in-memory during the session.

3. **RepositoryProtocol compliance**: GitHubProjectsRepository implements the same interface as FilesystemRepository, so all existing services work unchanged.

4. **Task ID format**: `owner/repo#123` (e.g., `charliek/sltasks#42`)

5. **Edit workflow**: Opens temp file in $EDITOR, then pushes changes back via API.

---

## Files Created

### `src/sltasks/github/__init__.py`

Package init that exports:
- `GitHubClient`
- `GitHubClientError` (base exception)
- `GitHubAuthError`
- `GitHubRateLimitError`
- `GitHubNotFoundError`
- `GitHubForbiddenError`

### `src/sltasks/github/client.py`

GraphQL client for GitHub API with:

**Authentication:**
- Uses `GITHUB_TOKEN` environment variable
- Falls back to `gh auth token` CLI command
- Raises `GitHubAuthError` if no token available

**Enterprise Support:**
- Configurable `base_url` (default: `api.github.com`)
- Enterprise uses `https://{base_url}/graphql`

**Error Handling:**
- 401 → `GitHubAuthError`
- 403 with "rate limit" → `GitHubRateLimitError`
- 403 otherwise → `GitHubForbiddenError`
- 404 → `GitHubNotFoundError`
- GraphQL errors with type NOT_FOUND → `GitHubNotFoundError`
- Other GraphQL errors → `GitHubClientError`

**Methods:**
- `execute(query, variables)` - Execute GraphQL query/mutation
- `query(query, variables)` - Alias for execute
- `mutate(query, variables)` - Alias for execute
- `close()` - Close HTTP client
- `from_environment(base_url)` - Factory method

### `src/sltasks/github/queries.py`

GraphQL query and mutation templates:

**Queries:**
- `GET_USER_PROJECT` - Fetch user project with fields
- `GET_ORG_PROJECT` - Fetch organization project with fields
- `GET_PROJECT_ITEMS` - Fetch all items (issues/PRs) with pagination
- `GET_REPOSITORY` - Get repository ID by owner/name

**Mutations:**
- `UPDATE_ITEM_FIELD` - Update Status field value (move between columns)
- `UPDATE_ITEM_POSITION` - Reorder within column (not yet used)
- `CREATE_ISSUE` - Create new issue
- `UPDATE_ISSUE` - Update issue title/body
- `CLOSE_ISSUE` - Close issue (used for delete)
- `ADD_ITEM_TO_PROJECT` - Add issue to project
- `ADD_LABELS` / `REMOVE_LABELS` - Label management (not yet used)

### `src/sltasks/repositories/github_projects.py`

Full `RepositoryProtocol` implementation:

**Core Methods:**
- `get_all()` - Fetches all project items, maps to Task objects
- `get_by_id(task_id)` - Returns cached task by ID
- `save(task)` - Creates or updates issue
- `delete(task_id)` - Closes the issue
- `get_board_order()` - Returns order derived from tasks
- `save_board_order(order)` - Updates internal state
- `reload()` - Clears cache, refetches from GitHub
- `validate()` - Checks config, auth, project access

**Status Mapping:**
- Explicit `column_mapping` config takes priority
- Falls back to fuzzy matching column titles to Status field options
- Unknown statuses map to first column

**Label Mapping:**
- Task type extracted from labels using `type_alias` config
- Priority extracted from labels using `priority_alias` config
- Remaining labels become task tags

**Issue Operations:**
- Create: Creates issue via API, adds to project, sets Status field
- Update: Updates title/body via API, updates Status field if changed
- Delete: Closes issue (does not remove from project)

### `tests/test_github_client.py`

16 unit tests covering:
- Client initialization
- Token from environment
- Token from gh CLI
- Error when no token
- Successful execution
- Variables passing
- 401/403/404 error handling
- GraphQL error handling
- Query/mutate aliases

### `tests/test_github_repository.py`

18 unit tests covering:
- Validation success/failure
- Project not found
- Missing Status field
- Issue to task mapping
- Pagination handling
- Status to state mapping (explicit and fuzzy)
- Label to type/priority mapping
- Creating new issues
- Updating existing issues
- Closing issues on delete
- Board order building

---

## Files Modified

### `pyproject.toml`

Added httpx dependency:
```toml
dependencies = [
    "textual>=0.89.0",
    "pydantic-settings>=2.6.0",
    "python-frontmatter>=1.1.0",
    "httpx>=0.27",
]
```

### `src/sltasks/models/sltasks_config.py`

Added `GitHubConfig` model:

```python
class GitHubConfig(BaseModel):
    base_url: str = "api.github.com"  # Enterprise support
    project_url: str | None = None     # e.g., https://github.com/users/owner/projects/1
    owner: str | None = None           # Alternative to project_url
    owner_type: str = "user"           # "user" or "organization"
    project_number: int | None = None  # Alternative to project_url
    default_repo: str | None = None    # For creating new issues
    allowed_repos: list[str] = []      # Filter (empty = all)
    column_mapping: dict[str, list[str]] = {}  # sltasks column -> GitHub statuses
    include_closed: bool = False
    include_prs: bool = True
    include_drafts: bool = False

    def get_project_info(self) -> tuple[str, str, int]:
        """Returns (owner, owner_type, project_number)"""
```

Added to `SltasksConfig`:
```python
provider: str = "file"  # "file" or "github"
github: GitHubConfig | None = None
```

### `src/sltasks/repositories/__init__.py`

Added export:
```python
from .github_projects import GitHubProjectsRepository
```

### `src/sltasks/app.py`

Updated `_init_services()` for provider selection:

```python
def _init_services(self) -> None:
    self.config_service = ConfigService(self.settings.project_root)
    config = self.config_service.get_config()

    if config.provider == "github":
        from .repositories import GitHubProjectsRepository
        self.repository = GitHubProjectsRepository(self.config_service)
    else:
        task_root = self.config_service.task_root
        self.repository = FilesystemRepository(task_root, self.config_service)

    # Validate repository
    valid, error = self.repository.validate()
    if not valid:
        self._init_error = error
```

Added error display in `on_mount()`:
```python
def on_mount(self) -> None:
    if self._init_error:
        self.notify(f"Error: {self._init_error}", severity="error", timeout=10)
```

### `src/sltasks/services/task_service.py`

Updated `open_in_editor()` to handle GitHub tasks:

```python
def open_in_editor(self, task: Task, task_root: Path | None = None) -> bool:
    if isinstance(task.provider_data, GitHubProviderData):
        return self._open_github_issue_in_editor(task)
    elif isinstance(task.provider_data, FileProviderData):
        return self._open_file_in_editor(task, task_root)
    else:
        return False
```

Added GitHub-specific edit workflow:
- Creates temp file with `# Title` and body
- Opens in $EDITOR
- Parses edited content
- Pushes changes to GitHub via repository.save()
- Cleans up temp file

---

## Configuration Example

```yaml
# sltasks.yml
version: 1
provider: github
task_root: .tasks  # Still needed for templates

github:
  project_url: "https://github.com/users/charliek/projects/2"
  default_repo: "charliek/sltasks"
  column_mapping:
    backlog:
      - "Backlog"
    todo:
      - "Ready"
    in_progress:
      - "In progress"
      - "In review"
    done:
      - "Done"

board:
  columns:
  - id: backlog
    title: Backlog
  - id: todo
    title: Ready
  - id: in_progress
    title: In Progress
  - id: done
    title: Done
  # ... types and priorities as usual
```

---

## Testing Results

### Live Testing with Real GitHub Project

Tested against: `https://github.com/users/charliek/projects/2`

**Read Flow:**
- Successfully fetched 4 issues from project
- Correctly mapped GitHub "Backlog" status to sltasks "backlog" column
- TUI displayed tasks correctly with 4 columns

**Write Flow - Move Task:**
```python
task.state = 'todo'  # Was 'backlog'
repo.save(task)
# Result: Issue moved to "Ready" column in GitHub Project
```

**Write Flow - Update Issue:**
```python
task.body = 'Updated body content...'
repo.save(task)
# Result: Issue body updated in GitHub
```

**Write Flow - Create Issue:**
```python
task = task_service.create_task(title='Test Task from sltasks', state='backlog')
# Result: Created issue #6 in charliek/sltasks, added to project with Backlog status
```

### Unit Tests

All 291 tests passing:
- 257 existing tests (unchanged)
- 34 new tests for GitHub integration

---

## Known Limitations (Phase 1)

1. **No offline support** - Requires internet connection
2. **No local file sync** - Issues exist only in GitHub (Phase 2 will add this)
3. **No label write-back** - Type/priority changes don't update labels yet
4. **No reordering** - Position mutations not yet implemented
5. **Archive = Close** - Archiving closes the issue rather than moving to a separate state

---

## Next Steps (Phase 2)

Phase 2 will add **filesystem sync**:

1. **Fetch to files** - Download issues as markdown files on startup
2. **Create from files** - Push local markdown files to GitHub
3. **Bidirectional sync** - Detect conflicts, provide resolution UI
4. **Offline mode** - Work locally, sync when online

See `docs/design/github-projects-integration-requirements.md` for full Phase 2 design.

---

## Environment Setup for Development

```bash
# Set GitHub token
export GITHUB_TOKEN="ghp_..."

# Or use gh CLI (token retrieved automatically)
gh auth login

# Run sltasks with GitHub provider
uv run sltasks

# Run tests
uv run python -m pytest tests/ -v
```

---

## Troubleshooting

### "No GitHub token found"
- Set `GITHUB_TOKEN` environment variable
- Or run `gh auth login` to authenticate via CLI

### "Project not found"
- Check project URL format: `https://github.com/users/{owner}/projects/{number}`
- Ensure token has `read:project` scope

### "Status field not found"
- GitHub Project must have a Status field configured
- This is the default for new projects

### Column not mapping correctly
- Add explicit `column_mapping` in config
- Check that GitHub Status option names match exactly
