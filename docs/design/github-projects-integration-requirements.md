# GitHub Projects Integration Requirements Document

## Overview

This document outlines the requirements and design considerations for adding GitHub Projects as an alternative backend repository for sltasks. This is a companion document to the Jira integration requirements, analyzing the feasibility and approach for GitHub's project management system.

## Executive Summary: GitHub vs Jira Comparison

| Aspect | GitHub Projects | Jira |
|--------|-----------------|------|
| **API Type** | GraphQL (primary), REST (new, limited) | REST |
| **Authentication** | PAT or GitHub App token | Email + API token |
| **Rate Limits** | 5,000 points/hour (cost-based) | ~100 requests/minute |
| **Column/Status** | Custom fields (SingleSelect) | Workflow statuses |
| **Ordering** | Native position API | Rank field |
| **Item Types** | Issues, PRs, Draft Issues | Issues only |
| **Complexity** | Medium | Higher (workflows) |
| **Offline editing** | Yes (issues are markdown) | No |

**Verdict:** GitHub Projects is **easier to integrate** than Jira due to simpler status management (no workflows), native item ordering API, and issues already being markdown-based.

---

## Goals

1. **Read GitHub Project boards** - Display issues/PRs from a GitHub Project in the sltasks TUI
2. **Manage item state** - Move items between columns via the TUI
3. **Basic CRUD** - Create issues, edit details, view content
4. **Leverage existing GitHub workflow** - Issues are already markdown, minimal friction

## Non-Goals (MVP)

- Pull Request management (view only, no review/merge)
- Draft Issues (GitHub-specific, not portable)
- Custom field management beyond Status
- Multiple project support in single view
- Milestone/Sprint management
- Sub-issues / task lists

---

## Architecture Overview

### Current Architecture

The `RepositoryProtocol` is already implemented in `src/sltasks/repositories/protocol.py`, defining the interface for task storage backends:

```
CLI → App → Services → RepositoryProtocol ←─┬─ FilesystemRepository → Filesystem
                ↓                           ├─ JiraRepository → Jira API (future)
         UI (Textual)                       └─ GitHubProjectsRepository → GitHub GraphQL API (future)
```

The protocol defines: `get_all()`, `get_by_id()`, `save()`, `delete()`, `get_board_order()`, `save_board_order()`, and `reload()`.

### Key Insight: Issues ARE Markdown

Unlike Jira, GitHub Issues are already markdown documents with a title and body. This maps almost perfectly to sltasks' Task model, making the integration more natural.

---

## API Analysis

### GraphQL API (Primary - Required)

GitHub Projects V2 requires the GraphQL API for most operations. There is no REST API for the core project management features (though a limited REST API was added in September 2025).

#### Required Queries

| Operation | GraphQL Query/Mutation | Notes |
|-----------|----------------------|-------|
| List projects | `organization.projectsV2` or `user.projectsV2` | Paginated, max 100 |
| Get project | `node(id: PROJECT_ID)` | By node ID |
| Get fields | `project.fields(first: 20)` | Includes Status field |
| Get items | `project.items(first: 100)` | Issues, PRs, drafts |
| Get issue details | `node(id: ISSUE_ID)` on `Issue` | Full issue content |

#### Required Mutations

| Operation | GraphQL Mutation | Notes |
|-----------|-----------------|-------|
| Add issue to project | `addProjectV2ItemById` | Returns item ID |
| Update field value | `updateProjectV2ItemFieldValue` | For Status changes |
| Reorder item | `updateProjectV2ItemPosition` | Move within column |
| Remove from project | `deleteProjectV2Item` | Doesn't delete issue |
| Create issue | `createIssue` (Issues API) | Separate from Projects |
| Update issue | `updateIssue` (Issues API) | Title, body, labels |

#### Critical Constraint

> "You cannot add and update an item in the same call. You must use `addProjectV2ItemById` to add the item and then use `updateProjectV2ItemFieldValue` to update the item."

This means creating a new task requires two API calls: create issue → add to project → update status.

### REST API (New - September 2025)

A REST API for GitHub Projects was released, supporting:
- List projects and project details
- Add/delete issues and PRs from projects
- Update field values

This could simplify some operations but may not cover all needs. Evaluate during implementation.

### Authentication

```bash
# Personal Access Token (classic or fine-grained)
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Required scopes:
# - read:project (queries)
# - project (mutations)
# - repo (for issue operations)
```

GitHub CLI (`gh`) can also provide authentication, which users may already have configured.

### Rate Limits

| Limit Type | Value | Notes |
|------------|-------|-------|
| Primary | 5,000 points/hour | Cost-based, not request-based |
| Concurrent | 100 requests | Shared with REST |
| Per-minute | 2,000 points | Secondary limit |
| Pagination | 100 items max | Per connection |
| Total nodes | 500,000 per query | Query complexity limit |

Rate limits are more generous than Jira but use a cost-based system where complex queries consume more points.

---

## Configuration Design

### sltasks.yml Extensions

```yaml
version: 1

# Backend selection
backend: github  # or "filesystem" or "jira"

# Existing filesystem config
task_root: .tasks
board:
  columns:
    - id: todo
      title: To Do
    - id: in_progress
      title: In Progress
    - id: done
      title: Done

# GitHub Projects configuration
github:
  # Project identification (one required)
  project_url: "https://github.com/orgs/myorg/projects/5"
  # OR explicit specification:
  owner: myorg           # org or username
  owner_type: org        # "org" or "user"
  project_number: 5

  # Optional: specific repository for new issues
  default_repo: myorg/myrepo

  # Column mapping (optional - auto-detects from project if omitted)
  # Maps sltasks column IDs to GitHub Project Status field options
  column_mapping:
    todo:
      - "Todo"
      - "Backlog"
      - "New"
    in_progress:
      - "In Progress"
      - "In Review"
    done:
      - "Done"
      - "Closed"

  # Filter options
  include_closed: false      # Include closed issues (default: false)
  include_prs: true          # Include pull requests (default: true)
  include_drafts: false      # Include draft issues (default: false)
```

### Environment Variables

```bash
# Option 1: Explicit token
GITHUB_TOKEN=ghp_xxxxxxxxxxxx

# Option 2: Use GitHub CLI authentication (if installed)
# sltasks can shell out to `gh auth token` to get the token
```

### Why This Approach?

1. **Project URL is intuitive** - Users can copy from browser
2. **Auto-detect columns** - Fetch Status field options from project
3. **Flexible filtering** - Users control what appears on board
4. **GitHub CLI integration** - Leverage existing auth if available

---

## Data Model Mapping

### Task ↔ GitHub Issue/PR

| Task Field | GitHub Field | Notes |
|------------|--------------|-------|
| `id` | `issue.number` | e.g., "123" or "owner/repo#123" |
| `title` | `issue.title` | Direct mapping |
| `state` | Project Status field | Via `ProjectV2ItemFieldSingleSelectValue` |
| `priority` | Labels (convention) | e.g., "priority:high" label |
| `tags` | `issue.labels` | Direct mapping |
| `type` | Labels (convention) | e.g., "bug", "feature" labels |
| `created` | `issue.createdAt` | ISO datetime |
| `updated` | `issue.updatedAt` | ISO datetime |
| `body` | `issue.body` | Already markdown! |
| `filepath` | N/A | Not applicable |

### Key Advantage: Body is Already Markdown

GitHub Issues use markdown natively. No conversion needed unlike Jira's ADF format.

### Item Identification

GitHub Projects items have multiple IDs:
- **Issue number**: `#123` (human-readable, repo-scoped)
- **Issue node ID**: `I_kwDOABC...` (global, for GraphQL)
- **Project item ID**: `PVTI_...` (project-scoped, for mutations)

We need to track both the issue identifier and the project item ID.

### Priority via Labels

GitHub doesn't have a native priority field. sltasks now supports configurable priorities with aliases, making GitHub label mapping straightforward:

```yaml
board:
  priorities:
    - id: critical
      label: Critical
      color: red
      priority_alias:
        - P0
        - priority:critical
    - id: high
      label: High
      color: orange1
      priority_alias:
        - P1
        - priority:high
    - id: medium
      label: Medium
      color: yellow
      priority_alias:
        - P2
        - priority:medium
    - id: low
      label: Low
      color: green
      priority_alias:
        - P3
        - priority:low
```

The `priority_alias` field maps GitHub label conventions to sltasks priority IDs. When loading issues, labels matching any alias are resolved to the canonical priority ID.

### Task Type via Labels

Similar to priority, use labels:
- `type:bug` or `bug`
- `type:feature` or `feature`
- `type:task` or `task`

---

## Feature Mapping

### What Works Naturally

| sltasks Feature | GitHub Equivalent | Complexity |
|-----------------|-------------------|------------|
| View board | Project items query | Low |
| Move between columns | Update Status field | Low |
| Edit task title | Update issue title | Low |
| Edit task body | Update issue body | Low |
| Create task | Create issue + add to project | Medium |
| Filter by tag | Labels in query | Low |
| Filter by type | Labels in query | Low |
| Reorder within column | `updateProjectV2ItemPosition` | Low |
| Archive | Close issue or remove from project | Low |
| Delete | Close issue (or actually delete) | Low |

### What's Different

| Feature | Difference | Proposed Handling |
|---------|-----------|-------------------|
| **External editor** | Issues are in GitHub, not local files | Fetch body → temp file → edit → push back |
| **New task** | Must specify repository | Use `default_repo` config or prompt |
| **Filename** | Issues use numbers, not slugs | Display as `repo#123` or just `#123` |
| **Archive** | No direct equivalent | Close issue and/or remove from project |
| **Priority** | No native field | Use labels with configurable patterns |

### External Editor Workflow

Unlike filesystem where you edit .md files directly:

1. Fetch issue body from GitHub
2. Write to temp file (e.g., `/tmp/sltasks-issue-123.md`)
3. Open in `$EDITOR`
4. On save, detect changes and push back to GitHub
5. Clean up temp file

This is similar to `gh issue edit --editor`.

---

## Challenges and Solutions

### Challenge 1: GraphQL Complexity

**Problem:** GraphQL requires building complex queries with proper field selection.

**Solution:**
- Use a thin GraphQL client (httpx + query strings)
- Pre-define query templates for common operations
- Consider using `gql` library for validation

### Challenge 2: Node IDs

**Problem:** GitHub uses opaque node IDs that aren't human-readable.

**Solution:**
- Cache node ID ↔ issue number mappings
- Store project item IDs for each issue
- Display human-readable `#123` to users

### Challenge 3: Multi-Repository Projects

**Problem:** A GitHub Project can contain issues from multiple repositories.

**Solution:**
- Track `owner/repo` for each issue
- Display repository context in UI if mixed
- For new issues, require `default_repo` or prompt

### Challenge 4: Status Field Discovery

**Problem:** Need to find the Status field and its options.

**Solution:**
```graphql
query {
  node(id: "PROJECT_ID") {
    ... on ProjectV2 {
      fields(first: 20) {
        nodes {
          ... on ProjectV2SingleSelectField {
            id
            name
            options { id name }
          }
        }
      }
    }
  }
}
```
Find field where `name == "Status"`, cache field ID and option IDs.

### Challenge 5: Closed Issues

**Problem:** Should closed issues appear? In what column?

**Solution:**
- Config option `include_closed: false` (default)
- If included, map to "done" column or based on last status

---

## MVP Scope

### Phase 1: Read-Only Board View

- [ ] Parse GitHub config from sltasks.yml
- [ ] Authenticate with GitHub token (env var or gh CLI)
- [ ] Fetch project metadata and Status field configuration
- [ ] Fetch project items (issues/PRs)
- [ ] Map to Task model
- [ ] Display in TUI
- [ ] Navigation and basic filtering

### Phase 2: State Management

- [ ] Move items between columns (update Status field)
- [ ] Reorder items within column (updateProjectV2ItemPosition)
- [ ] Handle errors gracefully (permission denied, etc.)

### Phase 3: CRUD Operations

- [ ] Create new issues (with repository selection)
- [ ] Edit issue title and body
- [ ] External editor integration (fetch → edit → push)
- [ ] Add/remove labels
- [ ] Close/reopen issues

### Phase 4: Polish

- [ ] Column auto-detection from project
- [ ] Priority label mapping
- [ ] Type label mapping
- [ ] Caching for faster startup
- [ ] Rate limit handling

### Out of Scope for MVP

- Pull request reviews/merging
- Draft issues
- Milestones
- Iterations/Sprints
- Custom fields beyond Status
- Sub-issues
- Project creation/configuration
- Multiple projects

---

## Implementation Comparison: GitHub vs Jira

### Easier in GitHub

| Aspect | Why Easier |
|--------|-----------|
| **Status changes** | Direct field update, no workflow transitions to discover |
| **Body format** | Already markdown, no conversion needed |
| **Ordering** | Native `updateProjectV2ItemPosition` mutation |
| **Authentication** | Can leverage existing `gh` CLI auth |
| **Local editing** | Issues are markdown, familiar format |

### Harder in GitHub

| Aspect | Why Harder |
|--------|-----------|
| **API type** | GraphQL is more complex than REST |
| **Node IDs** | Must track opaque IDs, not human-readable |
| **Priority/Type** | No native fields, must use label conventions |
| **Multi-repo** | Projects span repos, need to track source |
| **Rate limits** | Cost-based, harder to predict |

### Net Assessment

**GitHub Projects is easier overall** for sltasks integration because:

1. No workflow complexity - any status → any status
2. Markdown body - no format conversion
3. Native ordering API
4. Simpler authentication options
5. Issues are already a familiar concept to sltasks users

---

## Technical Considerations

### HTTP/GraphQL Client

Options:
1. **httpx** - HTTP client, send GraphQL as POST
2. **gql** - Python GraphQL client with query validation
3. **sgqlc** - Schema-based GraphQL client

**Recommendation:** Use `httpx` for simplicity, consider `gql` if query validation becomes valuable.

### Sample GraphQL Queries

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

### Error Handling

| Error | Handling |
|-------|----------|
| Auth failure (401) | Clear message, check GITHUB_TOKEN |
| Not found (404) | Project/issue deleted, refresh |
| Forbidden (403) | Missing permissions, inform user |
| Rate limited | Backoff, show remaining quota |
| Query too complex | Simplify query, paginate |

### Caching Strategy

- Cache project metadata (fields, options) on startup
- Cache items on `get_all()`, invalidate on reload
- Store node ID mappings persistently in `~/.sltasks/github-cache/`
- Optional: webhook integration for real-time updates (advanced)

---

## Configuration Validation

### On Startup

1. Validate `backend: github` with required config
2. Check for `GITHUB_TOKEN` or `gh auth token`
3. Parse project URL or owner/project_number
4. Test API connectivity
5. Fetch project, verify it exists
6. Discover Status field and cache options
7. Build column mapping (explicit or auto)

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
```

---

## Open Questions

1. **Project URL parsing**
   - Support both `github.com/orgs/X/projects/N` and `github.com/users/X/projects/N`?
   - Handle private vs public project URLs?

2. **Multi-repository display**
   - Show repository name in task title? e.g., `[myrepo] Fix bug`
   - Or just show issue number and let user inspect?

3. **PR handling**
   - Include PRs by default or require opt-in?
   - Show PR-specific info (merge status, checks)?

4. **Draft issues**
   - Include? They're GitHub-specific and can't be closed.
   - If included, how to handle "convert to issue"?

5. **Label conventions**
   - Prescribe specific labels (`priority:high`) or configurable patterns?
   - Should sltasks create labels if missing?

6. **Closed issues column**
   - When `include_closed: true`, which column?
   - Always "done" or preserve last status?

---

## Implementation Order Recommendation

1. **GraphQL client setup** - httpx + auth + basic query execution
2. **Project discovery** - Fetch project by URL/ID, get Status field
3. **Item fetching** - Query items, map to Task model
4. **Read-only view** - Display in TUI, navigation works
5. **Status updates** - Move between columns
6. **Ordering** - Reorder within column
7. **Issue editing** - Title, body, labels
8. **Issue creation** - New issue → add to project
9. **Polish** - Caching, error handling, config validation

---

## Dependencies to Add

```toml
# pyproject.toml
[project.dependencies]
httpx = "^0.27"  # HTTP client for GitHub GraphQL API
```

Same dependency as Jira - could share the HTTP client abstraction.

---

## Comparison Summary

| Dimension | GitHub Projects | Jira | Winner |
|-----------|-----------------|------|--------|
| API complexity | GraphQL (moderate) | REST (simple) | Jira |
| Status changes | Simple field update | Workflow transitions | GitHub |
| Body format | Markdown native | ADF conversion needed | GitHub |
| Ordering | Native API | Rank field | GitHub |
| Authentication | Token or CLI | Token only | GitHub |
| Rate limits | 5K points/hour | ~100 req/min | Similar |
| Priority/Type | Label conventions | Native fields | Jira |
| Multi-source | Multi-repo projects | Single project | Jira |

**Overall: GitHub Projects is recommended as the first external integration** due to lower complexity and better alignment with sltasks' markdown-centric design.

---

## References

- [Using the API to manage Projects - GitHub Docs](https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects)
- [GitHub GraphQL API Documentation](https://docs.github.com/en/graphql)
- [GraphQL Objects Reference](https://docs.github.com/en/graphql/reference/objects)
- [Rate limits for GraphQL API](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)
- [GraphQL Pagination](https://docs.github.com/en/graphql/guides/using-pagination-in-the-graphql-api)
- [REST API for GitHub Projects (2025)](https://github.blog/changelog/2025-09-11-a-rest-api-for-github-projects-sub-issues-improvements-and-more/)
- [GitHub Projects CLI Examples](https://gist.github.com/ruvnet/ac1ec98a770d57571afe077b21676a1d)
