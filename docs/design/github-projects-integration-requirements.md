# GitHub Projects Integration Requirements Document

## Overview

This document outlines the requirements and design for adding GitHub Projects as an alternative backend for sltasks. The integration provides a **hybrid model** where GitHub is the source of truth, while the filesystem can serve as a cache for offline viewing and a workspace for creating issues from local files (e.g., LLM-generated).

**Phase 1 Status: COMPLETE** - GitHub-only mode is fully implemented.
**Phase 2 Status: PLANNED** - See [Phase 2: Filesystem Sync](github-phase2-filesystem-sync.md) for detailed design.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Separate `github` provider | Implements `RepositoryProtocol`, distinct from file provider |
| Source of truth | GitHub when online | Filesystem serves as cache and workspace for LLM/offline access |
| Column mapping | Auto-detect via `slugify_column_id()` | GitHub Status options map 1:1 to column IDs (e.g., "In Progress" → `in_progress`) |
| Column validation | Strict matching | `board.columns` must match GitHub Status options or validation fails |
| Priority source | Project field OR labels | Check `priority_field` first, fall back to label-based detection |
| Config generation | `--github-setup` CLI | Interactive setup fetches project metadata and generates config |
| Display format | `owner/repo#123` | Clear context for multi-repo projects |
| Edit workflow | Temp file + $EDITOR | Consistent with `gh issue edit` workflow |
| Sync timing | Startup + manual refresh (`r`) | Fresh data at launch, user control during session |
| Enterprise | Supported via `base_url` config | Minimal complexity, enables work use cases |

---

## Goals

1. **View GitHub Project boards** - Display issues/PRs from a GitHub Project in the sltasks TUI
2. **Full state management** - Move items between columns, reorder within columns
3. **Full CRUD** - Create issues, edit details, view content, archive/close
4. **Create issues from local files** - Write .md files locally (or via LLM), push to GitHub (Phase 2)
5. **Filesystem sync** - Cache issues locally for offline viewing and LLM access (Phase 2)
6. **GitHub Enterprise support** - Work with self-hosted GitHub instances

## Non-Goals (MVP)

- Pull Request management (view only, no review/merge)
- Draft Issues (GitHub-specific, not portable)
- Custom field management beyond Status and Priority
- Multiple project support in single view
- Milestone/Sprint management
- Sub-issues / task lists
- Real-time sync (webhooks)

---

## Phased Implementation

### Phase 1: GitHub-Only (Online Mode) - COMPLETE

**Goal:** View and manage GitHub Project issues in the TUI without filesystem sync.

**What Was Built:**

- **GitHub GraphQL client** with authentication (token or `gh` CLI fallback)
- **Enterprise support** via configurable `base_url`
- **Status field auto-detection** - Columns derived from project Status options via slugification
- **Priority from project fields** - Optional `priority_field` config for project-based priority
- **Priority from labels** - Fallback to label-based priority detection
- **Interactive setup** - `--github-setup` CLI command generates config from project metadata
- **Full CRUD operations** - Create, read, update, close issues
- **Column movement** - Update Status field via GraphQL mutations
- **Edit workflow** - Fetch body → temp file → $EDITOR → push back
- **Manual refresh** - `r` keybinding to reload from GitHub
- **Validation** - Strict column/field validation with actionable error messages

**Files Implemented:**
- `src/sltasks/github/client.py` - GraphQL client with auth and error handling
- `src/sltasks/github/queries.py` - GraphQL query templates
- `src/sltasks/repositories/github_projects.py` - Full `RepositoryProtocol` implementation
- `src/sltasks/cli/github_setup.py` - Interactive config generation
- `src/sltasks/utils/slug.py` - `slugify_column_id()` function

### Phase 2: Filesystem Sync - PLANNED

**Goal:** Add bidirectional sync between GitHub and local filesystem.

See [Phase 2: Filesystem Sync Design](github-phase2-filesystem-sync.md) for complete specification.

**Summary:**
- Sync from GitHub on startup (configurable filter list using GitHub search syntax)
- Write fetched issues to `.tasks/` as markdown files with GitHub metadata
- Detect new local files (no GitHub metadata) as "local-only"
- Detect modified local files (edited since last sync) as "modified"
- Inline sync status indicators on task cards
- Dedicated sync screen to review pending changes
- Push selected new/modified files to GitHub
- CLI commands: `sltasks sync`, `sltasks push`, with `--dry-run` option

---

## Configuration Design

### Interactive Setup

The recommended way to configure GitHub integration is via the interactive setup command:

```bash
# Start interactive setup
sltasks --github-setup

# Or provide project URL directly
sltasks --github-setup https://github.com/users/owner/projects/1
```

The setup command:
1. Prompts for project URL
2. Authenticates using `GITHUB_TOKEN` or `gh auth token`
3. Fetches project metadata via GraphQL
4. Detects Status field options and maps to columns
5. Detects Priority/Severity/Urgency fields
6. Prompts for default status and repository
7. Generates `sltasks.yml` with all detected configuration

### sltasks.yml

```yaml
version: 1
provider: github  # "file" or "github"

# GitHub-specific configuration
github:
  # API target (defaults to api.github.com)
  base_url: api.github.com  # or "github.mycompany.com" for Enterprise

  # Project identification
  project_url: "https://github.com/users/owner/projects/1"
  # OR explicit specification:
  # owner: myorg
  # owner_type: org  # "org" or "user"
  # project_number: 5

  # Default repository for new issues
  default_repo: owner/repo

  # Default status for new issues (must match a slugified Status option)
  default_status: backlog

  # Optional: Priority from project field (instead of labels)
  # Checked case-insensitively: "Priority", "Severity", "Urgency"
  priority_field: "Priority"

  # Optional: Labels to highlight in TUI for quick assignment
  featured_labels:
    - "needs-design"
    - "blocked"

  # Allowed repositories (auto-detected from project if omitted)
  allowed_repos:
    - owner/repo1
    - owner/repo2

  # Include options
  include_closed: false      # Include closed issues (default: false)
  include_prs: true          # Include pull requests (default: true)
  include_drafts: false      # Include draft issues (default: false)

  # Filesystem sync configuration (Phase 2)
  sync:
    enabled: false  # Enable filesystem sync
    task_root: .tasks

    # Filters use GitHub search syntax (OR'd together)
    filters:
      - "assignee:@me"
      - "label:urgent"

# Board configuration
board:
  # Column IDs MUST match slugified GitHub Status options
  # If omitted, columns are auto-generated from Status field
  columns:
    - id: backlog
      title: "Backlog"           # Display override (optional)
      color: gray
    - id: ready
      title: "Ready"
      color: blue
    - id: in_progress
      title: "In Progress"
      color: yellow
    - id: in_review
      title: "In Review"
      color: orange
    - id: done
      title: "Done"
      color: green

  # Type/priority use canonical_alias for label write-back
  types:
    - id: feature
      color: blue
      canonical_alias: "type:feature"  # Label to apply on GitHub
    - id: bug
      color: red
      canonical_alias: "type:bug"
    - id: task
      color: white
      canonical_alias: "type:task"

  priorities:
    # When github.priority_field is set, these map to project field options by position
    # When github.priority_field is unset, canonical_alias is used for label-based priority
    - id: low
      label: "Low"
      color: green
      canonical_alias: "priority:low"
    - id: medium
      label: "Medium"
      color: yellow
      canonical_alias: "priority:medium"
    - id: high
      label: "High"
      color: orange
      canonical_alias: "priority:high"
    - id: critical
      label: "Critical"
      color: red
      canonical_alias: "priority:critical"
```

### Column Slugification

GitHub Status option names are converted to column IDs using `slugify_column_id()`:

| GitHub Status | Column ID |
|---------------|-----------|
| "Backlog" | `backlog` |
| "Ready" | `ready` |
| "In Progress" | `in_progress` |
| "In Review" | `in_review` |
| "Done" | `done` |
| "Done ✓" | `done` |
| "123 Numbers First" | `col_123_numbers_first` |

Rules:
- Lowercase
- Spaces/hyphens → underscores
- Remove non-alphanumeric (except underscores)
- Prefix with `col_` if starts with digit

### Environment Variables

```bash
# Option 1: Explicit token
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Option 2: Use GitHub CLI authentication (if installed)
# sltasks shells out to `gh auth token` to get the token

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

---

## Data Model

### Task ↔ GitHub Issue/PR Mapping

| Task Field | GitHub Field | Notes |
|------------|--------------|-------|
| `id` | Display: `owner/repo#123` | Internal: issue_node_id for queries |
| `title` | `issue.title` | Direct mapping |
| `state` | Project Status field | Slugified (e.g., "In Progress" → `in_progress`) |
| `priority` | Project field OR labels | Via `priority_field` or label detection |
| `tags` | `issue.labels` | Minus type/priority labels |
| `type` | Labels (convention) | Matched via type config aliases |
| `created` | `issue.createdAt` | ISO datetime |
| `updated` | `issue.updatedAt` | ISO datetime |
| `body` | `issue.body` | Already markdown |
| `provider_data` | `GitHubProviderData` | See below |

### GitHubProviderData

```python
class GitHubProviderData(BaseModel):
    provider: Literal["github"] = "github"
    project_item_id: str      # "PVTI_..." for GraphQL mutations
    issue_node_id: str        # "I_kw..." for issue queries
    repository: str           # "owner/repo"
    issue_number: int         # 123
    type_label: str | None    # Actual label matched (for roundtrip)
    priority_label: str | None # Actual label matched (for roundtrip)
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

### Local File Frontmatter (Phase 2 - Sync Mode)

```markdown
---
title: Fix login validation bug
state: in_progress              # Slugified status
priority: high
type: bug
tags:
  - auth
  - validation
created: '2025-01-15T12:00:00Z'
updated: '2025-01-15T14:30:00Z'

# GitHub sync metadata (managed by sltasks)
github:
  synced: true
  issue_number: 123
  repository: owner/repo
  project_item_id: PVTI_xxx
  issue_node_id: I_xxx
  last_synced: '2025-01-15T14:00:00Z'
  priority_source: field        # "field" or "label"
  priority_label: null          # Original label if from labels

# User-controlled
push_changes: false
close_on_github: false          # Set true to close issue when file deleted
---

Issue body here...
```

**Sync status rules:**
- No `github:` section → local-only file, can be pushed as new issue
- `github.synced: true` + no local edits → fully synced
- `github.synced: true` + local edits + `push_changes: false` → modified but GitHub wins
- `github.synced: true` + local edits + `push_changes: true` → will push to GitHub

### File Naming Convention

After pushing a new local file to GitHub:

```
fix-login-bug.md  →  owner-repo#123-fix-login-bug.md
```

Format: `{owner}-{repo}#{issue_number}-{original-slug}.md`

---

## UI/UX Design

### Keybindings

| Key | Action | Phase |
|-----|--------|-------|
| `r` | Refresh from GitHub | 1 |
| `S` | Open sync status screen | 2 |
| `p` | Push current task (if local/modified) | 2 |

### CLI Commands

```bash
# Interactive config setup
sltasks --github-setup
sltasks --github-setup https://github.com/users/owner/projects/1

# Normal operation
sltasks                    # Launch TUI

# Sync operations (Phase 2)
sltasks sync               # Sync from GitHub to filesystem
sltasks sync --dry-run     # Show what would sync
sltasks push               # Interactive push of local changes
sltasks push --dry-run     # Show what would be pushed
```

### Sync Status Indicators (Phase 2)

Task cards show sync status:
- `[local]` - Local-only file, not on GitHub
- `[modified]` - Local edits pending (`push_changes: true`)
- `[synced]` - Fully synced with GitHub
- No indicator - GitHub-only mode (Phase 1)

---

## API Analysis

### GraphQL API (Primary)

GitHub Projects V2 requires the GraphQL API. Key operations:

#### Queries

| Operation | Query | Notes |
|-----------|-------|-------|
| Get project | `user.projectV2` or `organization.projectV2` | By owner and number |
| Get fields | `project.fields(first: 20)` | Includes Status, Priority fields |
| Get items | `project.items(first: 100)` | Issues, PRs, drafts with pagination |

#### Mutations

| Operation | Mutation | Notes |
|-----------|----------|-------|
| Add issue to project | `addProjectV2ItemById` | Returns item ID |
| Update field value | `updateProjectV2ItemFieldValue` | For Status/Priority changes |
| Create issue | `createIssue` | Issues API, not Projects |
| Update issue | `updateIssue` | Title, body, labels |
| Close issue | `closeIssue` | Archive action |

#### Critical Constraint

> "You cannot add and update an item in the same call."

Creating a new task requires: create issue → add to project → update status (3 calls).

### Rate Limits

| Limit Type | Value | Notes |
|------------|-------|-------|
| Primary | 5,000 points/hour | Cost-based, not request-based |
| Per-minute | 2,000 points | Secondary limit |
| Pagination | 100 items max | Per connection |

---

## Error Handling

| Error | Handling |
|-------|----------|
| Auth failure (401) | Clear message: check GITHUB_TOKEN or `gh auth login` |
| Not found (404) | Project/issue deleted, suggest refresh |
| Forbidden (403) | Missing permissions, list required scopes |
| Rate limited (429) | Backoff, show remaining quota |
| Enterprise not reachable | Check `base_url` and network |
| Column mismatch | Point to `--github-setup` to regenerate config |
| Priority field not found | Point to `--github-setup` to reconfigure |

### Error Messages

```
Error: GITHUB_TOKEN not set
  Set the GITHUB_TOKEN environment variable with a personal access token.
  Required scopes: read:project, project, repo
  Create one at: https://github.com/settings/tokens

Error: GitHub CLI not authenticated
  Run 'gh auth login' to authenticate, or set GITHUB_TOKEN.

Error: Project not found
  Could not find project 5 for user 'owner'
  Check the project URL or number and your access permissions.

Error: Column 'review' not found in GitHub project.
  Available columns: backlog, ready, in_progress, in_review, done
  Run 'sltasks --github-setup' to regenerate configuration.

Error: Priority field 'Priority' not found in GitHub project.
  Available single-select fields: Status, Size
  Run 'sltasks --github-setup' to reconfigure.
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

| Component | Status | Description |
|-----------|--------|-------------|
| `GitHubClient` | Complete | HTTP/GraphQL client with auth and error handling |
| `GitHubProjectsRepository` | Complete | Full `RepositoryProtocol` implementation |
| `github_setup.py` | Complete | Interactive CLI config generation |
| `slugify_column_id()` | Complete | Column ID derivation from Status names |
| `GitHubSyncEngine` | Phase 2 | Handles filesystem sync |
| `SyncScreen` | Phase 2 | TUI screen for reviewing sync status |

### RepositoryProtocol Implementation

| Method | GitHub Implementation |
|--------|----------------------|
| `get_all()` | Query project items with pagination, map to Tasks |
| `get_by_id(id)` | Lookup from cached items |
| `save(task)` | Create/update issue, update Status/Priority fields |
| `delete(id)` | Close issue |
| `get_board_order()` | Derived from task cache |
| `save_board_order()` | Update Status field for moved tasks |
| `reload()` | Clear cache, re-fetch all project data |
| `validate()` | Test auth, fetch project, validate columns against Status options |

---

## References

- [Using the API to manage Projects - GitHub Docs](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects)
- [GitHub GraphQL API Documentation](https://docs.github.com/en/graphql)
- [GraphQL Objects Reference](https://docs.github.com/en/graphql/reference/objects)
- [Rate limits for GraphQL API](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)
