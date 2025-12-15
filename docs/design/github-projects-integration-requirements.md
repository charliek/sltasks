# GitHub Projects Integration Requirements Document

## Overview

This document outlines the requirements and design for adding GitHub Projects as an alternative backend for sltasks. The integration provides a **hybrid model** where GitHub is the source of truth, while the filesystem serves as a cache for offline viewing and a workspace for creating issues from local files (e.g., LLM-generated).

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Separate `github` provider | Can share code with `file` provider but distinct behavior |
| Source of truth | GitHub when online | Filesystem serves as cache and workspace for LLM/offline access |
| Display format | `owner/repo#123` | Clear context for multi-repo projects |
| Edit workflow | Temp file + $EDITOR | Consistent with `gh issue edit` workflow |
| Sync timing | Startup + manual refresh (`r`) | Fresh data at launch, user control during session |
| Push UI | Inline indicators + dedicated sync screen | Quick status view + bulk review capability |
| Create from file | Auto-detect new files, review before push | LLMs can write issues as files, user confirms push |
| After push | Rename to `owner-repo#123-slug.md` | Clear visual indicator of GitHub-managed files |
| Target repo | Default from config, per-file override | Flexible for multi-repo projects |
| Sync filters | Filter list (OR'd together) | Readable config, easy to add/remove criteria |
| Enterprise | Supported via `base_url` config | Minimal complexity, enables work use cases |

---

## Goals

1. **View GitHub Project boards** - Display issues/PRs from a GitHub Project in the sltasks TUI
2. **Full state management** - Move items between columns, reorder within columns
3. **Full CRUD** - Create issues, edit details, view content, archive/close
4. **Create issues from local files** - Write .md files locally (or via LLM), push to GitHub
5. **Filesystem sync** - Cache issues locally for offline viewing and LLM access
6. **GitHub Enterprise support** - Work with self-hosted GitHub instances

## Non-Goals (MVP)

- Pull Request management (view only, no review/merge)
- Draft Issues (GitHub-specific, not portable)
- Custom field management beyond Status
- Multiple project support in single view
- Milestone/Sprint management
- Sub-issues / task lists
- Real-time sync (webhooks)

---

## Phased Implementation

### Phase 1: GitHub-Only (Online Mode)

**Goal:** View and manage GitHub Project issues in the TUI without filesystem sync.

**Scope:**
- GitHub GraphQL client with authentication (token or `gh` CLI)
- Enterprise support via configurable `base_url`
- Fetch project metadata and Status field configuration
- Fetch and display issues/PRs as Tasks
- Move issues between columns (update Status field)
- Reorder within columns
- Create new issues (via TUI, prompts for title/body)
- Edit issues (fetch body → temp file → $EDITOR → push back)
- Manual refresh keybinding (`r`)
- Display format: `owner/repo#123`

**Not in Phase 1:**
- Filesystem cache/sync
- Create from local file
- Offline mode

### Phase 2: Filesystem Sync

**Goal:** Add bidirectional sync between GitHub and local filesystem.

**Scope:**
- Sync from GitHub on startup (configurable filter list)
- Write fetched issues to `.tasks/` as markdown files
- Detect new local files (no GitHub metadata) as "local-only"
- Detect modified local files (edited since last sync) as "modified"
- Inline sync status indicators on task cards
- Dedicated sync screen to review pending changes
- Push selected new/modified files to GitHub
- After push, rename file to `owner-repo#123-slug.md` format
- Validate target repo against allowed repos
- Conflict handling: GitHub wins by default, user marks file for push via `push_changes: true`
- CLI commands: `sltasks sync`, `sltasks push`, with `--dry-run` option
- Multi-repo push support (files targeting different repos in one operation)

---

## Configuration Design

### sltasks.yml

```yaml
version: 1
provider: github  # "file", "github", "github-prs", "jira"

# Existing board config applies to all providers
board:
  columns:
    - id: todo
      title: To Do
    - id: in_progress
      title: In Progress
    - id: done
      title: Done

# GitHub-specific configuration
github:
  # API target (defaults to api.github.com)
  base_url: api.github.com  # or "github.mycompany.com" for Enterprise

  # Project identification (one required)
  project_url: "https://github.com/orgs/myorg/projects/5"
  # OR explicit specification:
  # owner: myorg
  # owner_type: org  # "org" or "user"
  # project_number: 5

  # Default repository for new issues
  default_repo: myorg/myrepo

  # Allowed repositories (auto-detected from project if omitted)
  # Used to validate per-file repo overrides
  allowed_repos:
    - myorg/repo1
    - myorg/repo2

  # Column mapping (optional - auto-detects from project Status field)
  column_mapping:
    todo:
      - "Todo"
      - "Backlog"
    in_progress:
      - "In Progress"
      - "In Review"
    done:
      - "Done"
      - "Closed"

  # Include options
  include_closed: false      # Include closed issues (default: false)
  include_prs: true          # Include pull requests (default: true)
  include_drafts: false      # Include draft issues (default: false)

  # Filesystem sync configuration (Phase 2)
  sync:
    enabled: true
    task_root: .tasks  # Where to write synced files

    # Filters OR'd together - issue syncs if it matches ANY filter
    filters:
      - "assignee:@me"           # All my issues
      - "priority:high"          # All high priority
      - "label:urgent"           # Anything labeled urgent

    # Special filter values:
    # "*" or omit filters entirely = sync all issues on board
    # "assignee:@me" = current authenticated user
```

### Environment Variables

```bash
# Option 1: Explicit token
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Option 2: Use GitHub CLI authentication (if installed)
# sltasks can shell out to `gh auth token` to get the token

# Required scopes:
# - read:project (queries)
# - project (mutations)
# - repo (for issue operations)
```

### Enterprise Support

GitHub Enterprise is supported by setting `base_url`:

```yaml
github:
  base_url: github.mycompany.com
  project_url: "https://github.mycompany.com/orgs/myorg/projects/5"
```

The GraphQL schema is nearly identical, so all features work on both.

---

## Data Model

### Task ↔ GitHub Issue/PR Mapping

| Task Field | GitHub Field | Notes |
|------------|--------------|-------|
| `id` | Display: `owner/repo#123` | Internal: issue_node_id for queries |
| `title` | `issue.title` | Direct mapping |
| `state` | Project Status field | Via `ProjectV2ItemFieldSingleSelectValue` |
| `priority` | Labels (convention) | e.g., "priority:high" label |
| `tags` | `issue.labels` | Direct mapping (minus type/priority labels) |
| `type` | Labels (convention) | e.g., "bug", "feature" labels |
| `created` | `issue.createdAt` | ISO datetime |
| `updated` | `issue.updatedAt` | ISO datetime |
| `body` | `issue.body` | Already markdown! |
| `provider_data` | `GitHubProviderData` | project_item_id, issue_node_id, repository, issue_number |

### GitHubProviderData

```python
class GitHubProviderData(BaseModel):
    provider: Literal["github"] = "github"
    project_item_id: str      # "PVTI_..." for GraphQL mutations
    issue_node_id: str        # "I_kw..." for issue queries
    repository: str           # "owner/repo"
    issue_number: int         # 123
    type_label: str | None    # Label used for type (for roundtrip)
    priority_label: str | None # Label used for priority (for roundtrip)
```

### Display Format

Issues are displayed with full repository context:

```
owner/repo#123 - Fix login validation bug
```

Used in:
- Task cards in the TUI
- Local file names after sync: `owner-repo#123-fix-login-bug.md`
- Status messages and logs

### Local File Frontmatter (Sync Mode)

```markdown
---
title: Fix login validation bug
state: todo
priority: high
type: bug
tags:
  - auth
  - validation

# GitHub sync metadata (managed by sltasks)
github:
  synced: true
  issue_number: 123
  repository: myorg/myrepo
  project_item_id: PVTI_xxx
  issue_node_id: I_xxx
  last_synced: '2025-01-15T12:00:00Z'

# User-controlled flags
push_changes: false  # Set to true to push local edits to GitHub
---

Bug description here...
```

**Sync status rules:**
- No `github:` section → local-only file, can be pushed as new issue
- `github.synced: true` + no local edits → fully synced
- `github.synced: true` + local edits + `push_changes: false` → modified but GitHub wins
- `github.synced: true` + local edits + `push_changes: true` → will push to GitHub

### File Naming Convention

After pushing a new local file to GitHub:

```
fix-login-bug.md  →  myorg-myrepo#123-fix-login-bug.md
```

Format: `{owner}-{repo}#{issue_number}-{original-slug}.md`

---

## UI/UX Design

### Sync Status Indicators (Inline)

Task cards show sync status (Phase 2):
- `[local]` - Local-only file, not on GitHub
- `[modified]` - Local edits pending (`push_changes: true`)
- `[synced]` - Fully synced with GitHub
- No indicator - GitHub-only mode (Phase 1)

### Dedicated Sync Screen

Accessed via `S` keybinding or `sltasks sync` command:

```
┌─────────────────────────────────────────────────────────────┐
│ Sync Status                                          [ESC] │
├─────────────────────────────────────────────────────────────┤
│ New Local Files (will create issues):                       │
│   [x] fix-login-bug.md → myorg/myrepo                      │
│   [ ] add-dark-mode.md → myorg/myrepo                      │
│                                                             │
│ Modified Files (will update issues):                        │
│   [x] myorg-myrepo#45-update-readme.md                     │
│                                                             │
│ Conflicts (GitHub changed since last sync):                 │
│   [ ] myorg-myrepo#67-api-refactor.md                      │
│       Local: 2025-01-15 10:30  GitHub: 2025-01-15 11:00    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ [Space] Toggle  [Enter] Push Selected  [r] Refresh  [ESC]  │
└─────────────────────────────────────────────────────────────┘
```

### Keybindings

| Key | Action |
|-----|--------|
| `r` | Refresh from GitHub (manual sync) |
| `S` | Open sync status screen (Phase 2) |
| `p` | Push current task (if local/modified) (Phase 2) |

### CLI Commands

```bash
# Normal operation
sltasks                    # Launch TUI

# Sync operations (Phase 2)
sltasks sync               # Sync from GitHub to filesystem
sltasks sync --dry-run     # Show what would sync without making changes
sltasks push               # Interactive push of local changes
sltasks push --dry-run     # Show what would be pushed
```

---

## API Analysis

### GraphQL API (Primary)

GitHub Projects V2 requires the GraphQL API. Key operations:

#### Queries

| Operation | Query | Notes |
|-----------|-------|-------|
| Get project | `node(id: PROJECT_ID)` | By node ID |
| Get fields | `project.fields(first: 20)` | Includes Status field |
| Get items | `project.items(first: 100)` | Issues, PRs, drafts |
| Get project by URL | Parse URL, then `organization.projectV2` or `user.projectV2` | To get node ID |

#### Mutations

| Operation | Mutation | Notes |
|-----------|----------|-------|
| Add issue to project | `addProjectV2ItemById` | Returns item ID |
| Update field value | `updateProjectV2ItemFieldValue` | For Status changes |
| Reorder item | `updateProjectV2ItemPosition` | Move within column |
| Create issue | `createIssue` | Issues API, not Projects |
| Update issue | `updateIssue` | Title, body, labels |
| Close issue | `updateIssue(state: CLOSED)` | Archive action |

#### Critical Constraint

> "You cannot add and update an item in the same call."

Creating a new task requires: create issue → add to project → update status (3 calls).

### Sample Queries

#### Get Project and Items

```graphql
query GetProject($projectId: ID!) {
  node(id: $projectId) {
    ... on ProjectV2 {
      id
      title
      fields(first: 20) {
        nodes {
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name }
          }
        }
      }
      items(first: 100) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          fieldValues(first: 10) {
            nodes {
              ... on ProjectV2ItemFieldSingleSelectValue {
                field { ... on ProjectV2SingleSelectField { name } }
                name
                optionId
              }
            }
          }
          content {
            ... on Issue {
              id
              number
              title
              body
              state
              labels(first: 10) { nodes { name } }
              createdAt
              updatedAt
              repository { nameWithOwner }
            }
            ... on PullRequest {
              id
              number
              title
              body
              state
              labels(first: 10) { nodes { name } }
              createdAt
              updatedAt
              repository { nameWithOwner }
            }
          }
        }
      }
    }
  }
}
```

#### Update Status

```graphql
mutation UpdateStatus($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
  updateProjectV2ItemFieldValue(
    input: {
      projectId: $projectId
      itemId: $itemId
      fieldId: $fieldId
      value: { singleSelectOptionId: $optionId }
    }
  ) {
    projectV2Item { id }
  }
}
```

### Rate Limits

| Limit Type | Value | Notes |
|------------|-------|-------|
| Primary | 5,000 points/hour | Cost-based, not request-based |
| Per-minute | 2,000 points | Secondary limit |
| Pagination | 100 items max | Per connection |

---

## Challenges and Solutions

### Challenge 1: GraphQL Complexity

**Problem:** GraphQL requires building complex queries with proper field selection.

**Solution:**
- Use httpx for HTTP, pre-define query templates
- Consider `gql` library if validation becomes valuable

### Challenge 2: Node IDs

**Problem:** GitHub uses opaque node IDs that aren't human-readable.

**Solution:**
- Store all IDs in `GitHubProviderData`
- Display human-readable `owner/repo#123` to users
- Node IDs only used internally for API calls

### Challenge 3: Multi-Repository Projects

**Problem:** A GitHub Project can contain issues from multiple repositories.

**Solution:**
- Track `repository` for each issue
- Display full `owner/repo#123` format
- For new issues: use `default_repo` from config, allow per-file override
- Validate repos against `allowed_repos` list

### Challenge 4: Status Field Discovery

**Problem:** Need to find the Status field and its options.

**Solution:**
- Query project fields on startup
- Find field where `name == "Status"` (or configured name)
- Cache field ID and option IDs
- Map options to sltasks columns via `column_mapping`

### Challenge 5: Offline/Sync Conflicts

**Problem:** Local edits may conflict with GitHub changes.

**Solution:**
- GitHub wins by default (source of truth)
- User sets `push_changes: true` to override
- Sync screen shows conflicts with timestamps
- `--dry-run` option to preview changes

---

## Error Handling

| Error | Handling |
|-------|----------|
| Auth failure (401) | Clear message: check GITHUB_TOKEN or `gh auth login` |
| Not found (404) | Project/issue deleted, suggest refresh |
| Forbidden (403) | Missing permissions, list required scopes |
| Rate limited (429) | Backoff, show remaining quota |
| Enterprise not reachable | Check `base_url` and network |

### Error Messages

```
Error: GITHUB_TOKEN not set
  Set the GITHUB_TOKEN environment variable with a personal access token.
  Required scopes: read:project, project, repo
  Create one at: https://github.com/settings/tokens

Error: GitHub CLI not authenticated
  Run 'gh auth login' to authenticate, or set GITHUB_TOKEN.

Error: Project not found
  Could not find project 5 for organization 'myorg'
  Check the project URL or number and your access permissions.

Error: Status field not found
  The project doesn't have a Status field configured.
  Add a Status field to your GitHub Project board.

Error: Repository not allowed
  Cannot create issue in 'other/repo' - not in allowed_repos list.
  Add it to github.allowed_repos in sltasks.yml or use the default repo.
```

---

## Technical Implementation

### Dependencies

```toml
# pyproject.toml
[project.dependencies]
httpx = "^0.27"  # HTTP client for GitHub GraphQL API
```

### Key Components

1. **GitHubClient** - HTTP/GraphQL client with auth and rate limiting
2. **GitHubProjectsRepository** - Implements `RepositoryProtocol`
3. **GitHubSyncEngine** - Handles filesystem sync (Phase 2)
4. **SyncScreen** - TUI screen for reviewing sync status (Phase 2)

### RepositoryProtocol Implementation

| Method | GitHub Implementation |
|--------|----------------------|
| `get_all()` | Query project items, map to Tasks |
| `get_by_id(id)` | Lookup from cached items or query |
| `save(task)` | Update issue title/body/labels, update Status field |
| `delete(id)` | Close issue (or remove from project) |
| `get_board_order()` | Derived from project item positions |
| `save_board_order()` | `updateProjectV2ItemPosition` mutations |
| `reload()` | Re-fetch all project data |
| `validate()` | Test auth, fetch project, discover Status field |

---

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| Multi-repo display | Show `owner/repo#123` format |
| PR handling | Include by default (`include_prs: true`) |
| Draft issues | Exclude by default (`include_drafts: false`) |
| Closed issues | Exclude by default (`include_closed: false`) |
| Label conventions | Use existing `type_alias`/`priority_alias` config |
| Enterprise support | Via `base_url` config (minimal complexity) |
| Offline mode | Filesystem sync in Phase 2 |
| LLM integration | Create issues from local files, push via sync screen |

---

## Comparison: GitHub vs Jira

| Aspect | GitHub Projects | Jira |
|--------|-----------------|------|
| **API Type** | GraphQL (moderate) | REST (simple) |
| **Status changes** | Simple field update | Workflow transitions |
| **Body format** | Markdown native | ADF conversion needed |
| **Ordering** | Native position API | Rank field |
| **Authentication** | Token or `gh` CLI | Token only |
| **Priority/Type** | Label conventions | Native fields |

**Verdict:** GitHub Projects is recommended as the first external integration due to lower complexity and better alignment with sltasks' markdown-centric design.

---

## References

- [Using the API to manage Projects - GitHub Docs](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects)
- [GitHub GraphQL API Documentation](https://docs.github.com/en/graphql)
- [GraphQL Objects Reference](https://docs.github.com/en/graphql/reference/objects)
- [Rate limits for GraphQL API](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)
