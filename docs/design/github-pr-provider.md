# GitHub Pull Request Provider Requirements Document

## Overview

This document outlines the requirements and design considerations for adding GitHub Pull Requests as a repository backend for sltasks. Unlike the GitHub Projects integration (which shows items from a GitHub Project board), this provider displays pull requests directly from one or more GitHub repositories, enabling developers to visualize and track their PR workflow in a Kanban-style TUI.

## Problem Statement

Developers working with GitHub repositories need visibility into pull request status across their workflow. Current challenges include:

1. **Scattered PR visibility**: PRs are viewed one-at-a-time in the GitHub web UI or CLI, making it hard to see the full picture
2. **Multi-repo complexity**: Developers often work across multiple repositories, requiring them to check each repo's PR list separately
3. **Review queue management**: It's difficult to quickly see which PRs need your review vs. which of your PRs are waiting on others
4. **Status tracking**: Understanding which PRs are draft, awaiting review, have changes requested, or are approved requires navigating to each PR

A Kanban-style view of PRs would solve these problems by showing all relevant PRs in a single, organized board with columns representing PR states.

## Goals

1. **Visualize PRs as a Kanban board** - Display pull requests in columns based on their state (draft, needs review, approved, merged)
2. **Multi-repo support** - Query PRs across multiple repositories or an entire organization
3. **Comprehensive filtering** - Show PRs you authored, PRs requesting your review, and team PRs
4. **Quick actions** - Open PRs in browser, copy URLs, refresh data
5. **Leverage existing architecture** - Implement as a `RepositoryProtocol` backend, reusing Task model and UI

## Non-Goals (MVP)

- Write operations (approve, request changes, merge from TUI)
- PR comments or review threads
- CI/CD status details (show pass/fail only)
- Branch management or conflict resolution
- Issue integration (separate from GitHub Projects provider)
- Webhook-based real-time updates

---

## Architecture Overview

### Current Architecture

The `RepositoryProtocol` is implemented in `src/sltasks/repositories/protocol.py`, defining the interface for task storage backends:

```
CLI → App → Services → RepositoryProtocol ←─┬─ FilesystemRepository → Filesystem
                ↓                           ├─ JiraRepository → Jira API (planned)
         UI (Textual)                       ├─ GitHubProjectsRepository → GitHub GraphQL API (planned)
                                            └─ GitHubPRRepository → GitHub REST API (this document)
```

### Foundational Work Complete

The following preparatory work has been completed to support GitHub PR integration:

1. **Provider selection**: `SltasksConfig.provider` supports "github-prs" value
2. **Provider data model**: `GitHubPRProviderData` is defined with PR-specific fields (owner, repo, pr_number, branches, author, review_summary, ci_status, is_draft)
3. **Provider validation**: `RepositoryProtocol.validate()` enables startup checks

### Key Insight: PRs Map to Tasks

A GitHub Pull Request maps naturally to the Task model:

| Task Field | PR Equivalent | Notes |
|------------|---------------|-------|
| `id` | `owner/repo#123` | Unique identifier |
| `title` | PR title | Direct mapping |
| `state` | PR state + review state | Mapped to columns |
| `type` | `"pull_request"` | Always this value |
| `body` | PR description | Markdown |
| `tags` | Labels | Direct mapping |
| `priority` | Draft status or label-based | Optional |
| `created` | `created_at` | ISO datetime |
| `updated` | `updated_at` | ISO datetime |
| `provider_data` | Multiple fields | `GitHubPRProviderData` with branches, author, review_summary, ci_status |

Additional PR-specific data (branches, author, review counts, CI status) is stored in the `GitHubPRProviderData` model for type-safe access.

---

## Configuration Design

### sltasks.yml Extensions

```yaml
version: 1

# Backend selection
backend: github-prs  # New backend type

# GitHub PR configuration
github_prs:
  # Authentication (uses GITHUB_TOKEN environment variable)
  # Required scopes: repo (for private repos), read:org (for org queries)

  # Scope: specify repositories or organization
  repositories:
    - owner/repo1
    - owner/repo2
  # OR query all repos in an organization:
  organization: myorg

  # Query filter (GitHub search syntax)
  # Supports: author, assignee, involves, review-requested, org, repo, is:open, is:draft, etc.
  query: "involves:@me is:open"

  # Alternative: multiple named queries (for future advanced filtering)
  # queries:
  #   my_prs: "author:@me is:open"
  #   needs_review: "review-requested:@me is:open"
  #   team: "org:myorg is:open"

  # Include closed/merged PRs (default: false)
  include_closed: false

  # Column mapping: PR state → sltasks column
  # Keys are sltasks column IDs, values are PR states to match
  column_mapping:
    draft:
      - "draft"
    needs_review:
      - "open"              # Open but no reviews yet
    in_review:
      - "review_pending"    # Has pending reviews
    changes_requested:
      - "changes_requested"
    approved:
      - "approved"
    merged:
      - "merged"
      - "closed"

# Board configuration for PR columns
board:
  columns:
    - id: draft
      title: Draft
    - id: needs_review
      title: Needs Review
    - id: in_review
      title: In Review
    - id: changes_requested
      title: Changes Requested
    - id: approved
      title: Approved
    - id: merged
      title: Merged
```

### Environment Variables

```bash
# Required: GitHub Personal Access Token
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Required scopes:
# - repo (for private repository access)
# - read:org (for organization queries)
# - read:user (for @me resolution)

# Alternative: Use GitHub CLI authentication
# If gh is installed and authenticated, sltasks can use `gh auth token`
```

### Why This Approach?

1. **Query-based flexibility**: GitHub's search syntax is powerful and familiar to developers
2. **Multi-repo by default**: One board can show PRs from many repos
3. **Column mapping is explicit**: User controls how PR states map to columns
4. **Environment-based auth**: Follows GitHub CLI conventions, avoids secrets in config

---

## Data Model Mapping

### PR State to Column Mapping

GitHub PRs don't have a single "state" field—their effective state is a combination of:
- `state`: "open" or "closed"
- `draft`: true or false
- `merged`: true or false
- Review states: "PENDING", "APPROVED", "CHANGES_REQUESTED", "DISMISSED"

The provider must synthesize these into a single column assignment:

```python
def determine_column(pr: dict, reviews: list[dict]) -> str:
    """Determine the sltasks column for a PR based on its state."""
    # Merged PRs
    if pr.get("merged"):
        return "merged"

    # Closed but not merged
    if pr["state"] == "closed":
        return "closed"  # or "merged" depending on config

    # Draft PRs
    if pr.get("draft"):
        return "draft"

    # Check review states
    review_states = [r["state"] for r in reviews]

    if "CHANGES_REQUESTED" in review_states:
        return "changes_requested"

    if "APPROVED" in review_states:
        return "approved"

    if "PENDING" in review_states:
        return "in_review"

    # Open with no reviews
    return "needs_review"
```

### Task ID Format

For multi-repo support, task IDs include the repository:

- Multi-repo: `"owner/repo#123"`
- Single-repo (optional shorthand): `"#123"`

The ID format is consistent and can be parsed to construct GitHub URLs.

### PR Metadata in Body

Since Task.body is markdown and PRs are markdown, the PR description becomes the body. Additional metadata can be prepended as a formatted header:

```markdown
**Repository:** owner/repo
**Branch:** feature/auth → main
**Author:** @alice
**Reviews:** ✓2 ○1 ✗0
**CI:** passing

---

[Original PR description follows]
```

Or alternatively, store metadata in a structured comment block that the UI can parse.

---

## API Integration

### GitHub REST API Endpoints

| Operation | Endpoint | Notes |
|-----------|----------|-------|
| Search PRs | `GET /search/issues?q=is:pr+...` | Uses search API for flexible queries |
| List repo PRs | `GET /repos/{owner}/{repo}/pulls` | Per-repo listing |
| Get PR details | `GET /repos/{owner}/{repo}/pulls/{number}` | Full PR data |
| Get PR reviews | `GET /repos/{owner}/{repo}/pulls/{number}/reviews` | Review states |
| Get review requests | `GET /repos/{owner}/{repo}/pulls/{number}/requested_reviewers` | Pending reviews |

### Authentication

```python
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}
```

### Rate Limits

| Limit Type | Value | Notes |
|------------|-------|-------|
| Authenticated | 5,000 requests/hour | Per-user |
| Search API | 30 requests/minute | More restrictive |
| Conditional requests | Use ETags | Reduces rate limit impact |

**Mitigation strategies**:
- Cache PR data in memory
- Use conditional requests (If-None-Match) for refreshes
- Batch repository queries where possible
- Show rate limit status to user if approaching limits

---

## Implementation Plan

### Phase 1: Configuration and Models

**Goal**: Add GitHub PR configuration to the config model.

**Files to modify**:
- `src/sltasks/models/sltasks_config.py`

**New models**:
```python
class GitHubPRConfig(BaseModel):
    """Configuration for GitHub PR backend."""
    repositories: list[str] = Field(default_factory=list)
    organization: str | None = None
    query: str = "involves:@me is:open"
    include_closed: bool = False
    column_mapping: dict[str, list[str]] = Field(default_factory=dict)

class SltasksConfig(BaseModel):
    # ... existing fields ...
    backend: str = "filesystem"
    github_prs: GitHubPRConfig | None = None
```

### Phase 2: GitHub API Client

**Goal**: Create HTTP client wrapper for GitHub REST API.

**New files**:
- `src/sltasks/clients/github.py`

**Key features**:
- Token-based authentication
- Rate limit tracking
- Pagination handling
- Error handling (401, 403, 404, 429)
- Optional: GitHub CLI token fallback

```python
class GitHubClient:
    def __init__(self, token: str):
        self.client = httpx.Client(
            base_url="https://api.github.com",
            headers={...},
            timeout=30.0
        )

    def search_prs(self, query: str) -> list[dict]: ...
    def get_pr(self, owner: str, repo: str, number: int) -> dict: ...
    def get_reviews(self, owner: str, repo: str, number: int) -> list[dict]: ...
```

### Phase 3: GitHub PR Repository

**Goal**: Implement `RepositoryProtocol` for GitHub PRs.

**New files**:
- `src/sltasks/repositories/github_prs.py`

**Implementation**:
```python
class GitHubPRRepository:
    """Repository backed by GitHub Pull Requests."""

    def __init__(self, config: GitHubPRConfig, board_config: BoardConfig):
        self.config = config
        self.board_config = board_config
        self._client = GitHubClient(os.environ["GITHUB_TOKEN"])
        self._cache: dict[str, Task] = {}

    def get_all(self) -> list[Task]:
        """Fetch PRs and convert to Task objects."""
        prs = self._client.search_prs(self.config.query)
        tasks = [self._pr_to_task(pr) for pr in prs]
        return tasks

    def get_by_id(self, task_id: str) -> Task | None:
        """Fetch a specific PR by ID."""
        owner, repo, number = self._parse_id(task_id)
        pr = self._client.get_pr(owner, repo, number)
        return self._pr_to_task(pr) if pr else None

    def save(self, task: Task) -> Task:
        """Not supported for read-only backend."""
        raise NotImplementedError("GitHub PR backend is read-only")

    def delete(self, task_id: str) -> None:
        """Not supported for read-only backend."""
        raise NotImplementedError("GitHub PR backend is read-only")

    def get_board_order(self) -> BoardOrder:
        """Return ordering from cached PRs."""
        # Group by column based on PR state
        ...

    def save_board_order(self, order: BoardOrder) -> None:
        """No-op for GitHub PRs (ordering is by updated time)."""
        pass

    def reload(self) -> None:
        """Clear cache and re-fetch from GitHub."""
        self._cache.clear()
```

### Phase 4: PR-Specific Task Card Display

**Goal**: Show PR-specific information in the TaskCard widget.

**Files to modify**:
- `src/sltasks/ui/widgets/task_card.py`

**PR-specific display**:
```
┌──────────────────────────────────────────┐
│ ● #123 Add user authentication           │  ← Type indicator + PR# + title
│ myorg/myrepo                             │  ← Repository
│ feature/auth → main                      │  ← Source → target branch
│ ✓2 ○1 ✗0  •  CI passing                  │  ← Review summary + CI status
│ @alice  •  Updated 2 hours ago           │  ← Author + recency
└──────────────────────────────────────────┘
```

**Implementation approach**:
- Check if `task.type == "pull_request"`
- Parse PR metadata from structured body section
- Render PR-specific layout instead of standard task preview

### Phase 5: PR Actions

**Goal**: Add keybindings for PR-specific actions.

**Files to modify**:
- `src/sltasks/app.py`

**Actions**:
| Key | Action | Implementation |
|-----|--------|----------------|
| `o` | Open in browser | `webbrowser.open(pr_url)` |
| `y` | Copy PR URL | Copy to system clipboard |
| `Enter` | Preview | Show full PR details in modal |
| `r` | Refresh | Call `repository.reload()` |

**Disabled actions** (with user feedback):
- `e` (edit) → "Cannot edit remote PR"
- `n` (new) → "Cannot create PR from TUI"
- `H`/`L` (move) → "PR state is managed by GitHub"
- `d` (delete) → "Cannot close PR from TUI"

### Phase 6: Backend Selection

**Goal**: Wire up backend selection in App initialization.

**Files to modify**:
- `src/sltasks/app.py`

**Backend factory**:
```python
def _create_repository(self, config: SltasksConfig) -> RepositoryProtocol:
    if config.backend == "github-prs":
        if not config.github_prs:
            raise ConfigError("github_prs section required when backend is 'github-prs'")
        return GitHubPRRepository(config.github_prs, config.board)
    else:
        return FilesystemRepository(...)
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| `GITHUB_TOKEN` not set | Clear error message with setup instructions |
| Auth failure (401) | "Invalid GitHub token. Check GITHUB_TOKEN environment variable." |
| Rate limited (429) | Show remaining quota, suggest waiting or reducing query scope |
| Not found (404) | Skip missing repos/PRs, log warning |
| Network error | Show error, allow manual refresh |
| Invalid query syntax | Parse error with suggestion |

---

## Testing Strategy

### Unit Tests
- Config parsing and validation
- PR → Task mapping logic
- Column determination from PR state
- ID parsing (owner/repo#number format)

### Integration Tests
- GitHub API client with mocked responses
- Repository protocol compliance
- Error handling scenarios

### Manual Testing
- Real GitHub repos with various PR states
- Multi-repo queries
- Rate limit behavior
- Authentication flows (token and gh CLI)

---

## Dependencies

```toml
# pyproject.toml
[project.dependencies]
httpx = "^0.27"  # HTTP client for GitHub REST API
```

Same dependency planned for Jira and GitHub Projects integrations—can share client infrastructure.

---

## Future Extensions

1. **Write operations**: Approve, request changes, merge from TUI
2. **GitLab support**: Similar provider for GitLab merge requests
3. **Composite backend**: Mix filesystem tasks + GitHub PRs in one view
4. **Real-time updates**: GitHub webhooks for instant refresh
5. **CI details**: Expand CI status to show individual check names
6. **PR timeline**: Show recent activity (comments, commits, reviews)

---

## Open Questions

1. **ID format**: Should single-repo mode use `#123` or always `owner/repo#123`?
   - Recommendation: Always use full format for consistency

2. **Closed PRs**: Separate "Closed" column vs. grouping with "Merged"?
   - Recommendation: Make it configurable via column_mapping

3. **Ordering**: Order by updated time, created time, or allow user preference?
   - Recommendation: Default to updated time, configurable later

4. **Stale PR indicator**: Show visual indicator for PRs not updated recently?
   - Recommendation: Add to future phase, not MVP

5. **Multiple queries**: Support separate query results in different columns?
   - Recommendation: Single query for MVP, named queries later

---

## Summary

The GitHub PR Provider extends sltasks with a read-only Kanban view of pull requests across one or more GitHub repositories. It:

- Implements `RepositoryProtocol` with PRs mapped to Tasks
- Uses GitHub REST API with `GITHUB_TOKEN` authentication
- Maps PR states (draft, open, reviews, merged) to configurable columns
- Displays PR-specific info (branches, reviews, CI) in TaskCard
- Supports multi-repo queries via GitHub search syntax
- Disables write operations with clear user feedback

This design complements the planned GitHub Projects and Jira integrations, sharing the same architectural patterns while addressing a distinct use case: developer-focused PR workflow visualization.
