# Jira Integration Requirements Document

## Overview

This document outlines the requirements and design considerations for adding Jira as an alternative backend repository for sltasks. The goal is to allow users to visualize and manage Jira issues through the sltasks TUI while maintaining the existing filesystem-based workflow as the default.

## Goals

1. **Read Jira boards** - Display issues from a Jira Kanban/Scrum board in the sltasks TUI
2. **Manage issue state** - Move issues between columns/statuses via the TUI
3. **Basic CRUD** - Create, edit, and view issues from the terminal
4. **Minimal friction** - Simple configuration, works with existing sltasks patterns

## Non-Goals (MVP)

- Full Jira feature parity (sprints, epics, custom fields beyond basics)
- Offline mode / local caching with sync
- Two-way sync between filesystem and Jira
- Support for Jira Server (focus on Jira Cloud initially)
- Bulk operations
- Issue linking / parent-child relationships

---

## Architecture Overview

### Current Architecture

```
CLI → App → Services → FilesystemRepository → Filesystem
                ↓
         UI (Textual)
```

### Proposed Architecture

```
CLI → App → Services → RepositoryProtocol ←─┬─ FilesystemRepository → Filesystem
                ↓                           │
         UI (Textual)                       └─ JiraRepository → Jira REST API
```

### Key Insight

The service layer (TaskService, BoardService) should remain unchanged. They interact with a repository interface that can be backed by either filesystem or Jira.

---

## Configuration Design

### sltasks.yml Extensions

```yaml
version: 1

# Backend selection (default: filesystem)
backend: jira  # or "filesystem"

# Existing filesystem config (used when backend: filesystem)
task_root: .tasks
board:
  columns:
    - id: todo
      title: To Do
    - id: in_progress
      title: In Progress
    - id: done
      title: Done

# New Jira configuration (used when backend: jira)
jira:
  # Required
  instance: https://yourcompany.atlassian.net
  project: PROJ  # Project key

  # Board selection (one of these required)
  board_id: 123          # Specific board ID
  # OR
  board_name: "My Board" # Find board by name

  # Optional filters
  jql_filter: "assignee = currentUser()"  # Additional JQL to filter issues

  # Column mapping: Map Jira statuses to sltasks columns
  # If not specified, uses Jira board columns directly
  column_mapping:
    todo:
      - "To Do"
      - "Open"
      - "Backlog"
    in_progress:
      - "In Progress"
      - "In Review"
    done:
      - "Done"
      - "Closed"
      - "Resolved"
```

### Environment Variables

```bash
# Required for Jira backend
JIRA_EMAIL=user@company.com
JIRA_API_TOKEN=your-api-token

# Alternative: Combined credentials
JIRA_AUTH=user@company.com:api-token
```

### Why This Approach?

1. **Token in env var, not config** - Follows security best practices, avoids accidental commits
2. **Column mapping is optional** - Can use Jira's native board columns directly
3. **Backend is explicit** - Clear which mode you're in
4. **JQL filter** - Power users can scope to specific issues

---

## Data Model Mapping

### Task ↔ Jira Issue

| Task Field | Jira Field | Notes |
|------------|------------|-------|
| `filename` | `issue.key` | e.g., "PROJ-123" becomes identifier |
| `title` | `summary` | Direct mapping |
| `state` | `status.name` | Mapped through column_mapping |
| `priority` | `priority.name` | May need mapping (Jira has 5 levels) |
| `tags` | `labels` | Direct mapping |
| `type` | `issuetype.name` | Bug, Story, Task, etc. |
| `created` | `created` | ISO datetime |
| `updated` | `updated` | ISO datetime |
| `body` | `description` | Markdown ↔ Jira markup conversion |
| `filepath` | N/A | Not applicable for Jira |

### Priority Mapping

| sltasks | Jira |
|---------|------|
| `critical` | Highest |
| `high` | High |
| `medium` | Medium |
| `low` | Low, Lowest |

### BoardOrder Handling

For Jira, ordering within columns can be handled by:

1. **Jira's rank field** (preferred) - Most Jira boards use issue ranking
2. **Fallback to issue key** - PROJ-1, PROJ-2, etc.
3. **Local cache** - Store ordering in `~/.sltasks/jira-order-{board_id}.yaml`

**Recommendation:** Use Jira's native ranking for MVP. The rank is maintained by Jira when issues are drag-dropped in their UI.

---

## Repository Interface

### Proposed Protocol

```python
from typing import Protocol

class RepositoryProtocol(Protocol):
    """Interface for task storage backends."""

    def get_all(self) -> list[Task]:
        """Load all tasks from the backend."""
        ...

    def get_by_id(self, task_id: str) -> Task | None:
        """Get a single task by ID (filename or issue key)."""
        ...

    def save(self, task: Task) -> Task:
        """Create or update a task."""
        ...

    def delete(self, task_id: str) -> None:
        """Delete a task."""
        ...

    def get_board_order(self) -> BoardOrder:
        """Get task ordering within columns."""
        ...

    def save_board_order(self, order: BoardOrder) -> None:
        """Save task ordering (may be no-op for some backends)."""
        ...

    def reload(self) -> None:
        """Clear caches and reload from source."""
        ...
```

### FilesystemRepository Changes

- Implement the protocol (already does implicitly)
- Add `ensure_directory()` to protocol or keep as filesystem-specific

### JiraRepository Implementation

```python
class JiraRepository:
    """Repository backed by Jira REST API."""

    def __init__(self, config: JiraConfig, board_config: BoardConfig):
        self.config = config
        self.board_config = board_config
        self._client: JiraClient  # HTTP client wrapper
        self._cache: dict[str, Task] = {}

    def get_all(self) -> list[Task]:
        # Fetch issues from Jira board
        # Map to Task objects
        # Apply column_mapping for state
        ...

    def save(self, task: Task) -> Task:
        if task.filename.startswith("NEW-"):
            # Create new issue
            return self._create_issue(task)
        else:
            # Update existing issue
            return self._update_issue(task)
```

---

## Jira API Integration

### Required API Calls

| Operation | Jira API Endpoint | Notes |
|-----------|-------------------|-------|
| List issues | `GET /rest/agile/1.0/board/{boardId}/issue` | With JQL filter |
| Get issue | `GET /rest/api/3/issue/{issueKey}` | Single issue details |
| Create issue | `POST /rest/api/3/issue` | Returns new key |
| Update issue | `PUT /rest/api/3/issue/{issueKey}` | Field updates |
| Transition issue | `POST /rest/api/3/issue/{issueKey}/transitions` | State changes |
| Delete issue | `DELETE /rest/api/3/issue/{issueKey}` | Requires permission |
| Get transitions | `GET /rest/api/3/issue/{issueKey}/transitions` | Available states |
| Get board | `GET /rest/agile/1.0/board/{boardId}` | Board metadata |
| Get board config | `GET /rest/agile/1.0/board/{boardId}/configuration` | Column config |
| Rank issue | `PUT /rest/agile/1.0/issue/rank` | Reorder within column |

### Authentication

Jira Cloud uses Basic Auth with API tokens:
```
Authorization: Basic base64(email:api_token)
```

### Rate Limiting Considerations

- Jira Cloud: ~100 requests/minute (varies by plan)
- Batch fetches where possible
- Consider pagination for large boards
- Cache aggressively for read operations

---

## Feature Mapping

### What Works Naturally

| sltasks Feature | Jira Equivalent | Notes |
|-----------------|-----------------|-------|
| View board | Board API | Direct mapping |
| Move between columns | Transition API | Requires transition lookup |
| Edit task | Update API | Field updates |
| Create task | Create API | Requires project/type selection |
| Archive | Transition to "Done" or custom | No direct archive in Jira |
| Filter by tag | JQL `labels = X` | Works well |
| Filter by priority | JQL `priority = X` | Works well |
| Filter by type | JQL `issuetype = X` | Works well |

### Challenges / Differences

| Feature | Challenge | Proposed Solution |
|---------|-----------|-------------------|
| **State transitions** | Jira has workflows; can't always go state→state | Fetch available transitions, show only valid moves |
| **Reorder within column** | Jira ranking is complex | Use Jira's rank API, or skip for MVP |
| **External editor** | Can't edit Jira issue as markdown file | Open Jira URL in browser, or temp file → API update |
| **Delete** | Often restricted in Jira | Hide behind confirmation, respect permissions |
| **New task filename** | Auto-generated in filesystem | For Jira: use temp ID until created, then use issue key |
| **Body format** | Jira uses ADF (Atlassian Document Format) | Convert markdown ↔ ADF, or use plain text |

### Archive Behavior

Options for "archive" in Jira context:
1. **Transition to "Done"** - Most common
2. **Custom status** - "Archived" if workflow supports it
3. **Move to different project** - Complex, skip for MVP
4. **Hide from board via JQL** - Filter out resolved issues

**Recommendation:** Map archive to transitioning to final column (Done/Resolved).

---

## MVP Scope

### Phase 1: Read-Only Board View

- [ ] Connect to Jira with credentials from env
- [ ] Fetch board and issues via API
- [ ] Display in TUI with mapped columns
- [ ] Navigation and filtering work
- [ ] View issue details

### Phase 2: State Management

- [ ] Move issues between columns (transitions)
- [ ] Fetch available transitions before move
- [ ] Handle transition failures gracefully
- [ ] Reorder within column (using Jira rank)

### Phase 3: CRUD Operations

- [ ] Create new issues (with type selection)
- [ ] Edit issue summary/description
- [ ] Delete issues (with confirmation)
- [ ] Add/remove labels

### Out of Scope for MVP

- Sprint management
- Epic linking
- Custom fields beyond basics
- Attachments
- Comments
- Watchers/assignees
- Time tracking
- Offline mode

---

## Technical Considerations

### HTTP Client

Options:
1. **httpx** - Modern async-capable client (recommended)
2. **requests** - Simpler, synchronous
3. **jira-python** - Official library, but heavy

**Recommendation:** Use `httpx` for flexibility and async capability if needed later.

### Error Handling

| Error Type | Handling |
|------------|----------|
| Auth failure (401) | Clear error, prompt to check credentials |
| Not found (404) | Issue deleted externally, refresh board |
| Permission denied (403) | Inform user, skip operation |
| Rate limited (429) | Backoff and retry |
| Network error | Show error, allow retry |
| Transition not allowed | Show available transitions |

### Caching Strategy

- Cache board configuration on startup
- Cache issues on `get_all()`, invalidate on reload
- Don't cache transitions (may change)
- Optional: persist cache to disk for faster startup

### Async Considerations

Current sltasks is synchronous. Options:
1. **Keep sync** - Use `httpx` sync client, simpler
2. **Add async** - Better UX for slow API calls, but more complex

**Recommendation:** Start synchronous, add loading indicators. Consider async later if needed.

---

## Configuration Validation

### On Startup

1. Check `backend` value is valid ("filesystem" or "jira")
2. If jira:
   - Validate required env vars present
   - Validate instance URL format
   - Test connection with simple API call
   - Fetch and validate board exists
   - Build column mapping

### Error Messages

```
Error: JIRA_API_TOKEN not set
  Set the JIRA_API_TOKEN environment variable with your Jira API token.
  Generate one at: https://id.atlassian.com/manage-profile/security/api-tokens

Error: Cannot connect to Jira
  Could not reach https://yourcompany.atlassian.net
  Check your instance URL and network connection.

Error: Board not found
  No board found with ID 123 in project PROJ
  Available boards: [list boards]
```

---

## Open Questions

1. **Column mapping required?**
   - Should we require explicit mapping, or auto-detect from Jira board config?
   - Auto-detect is easier for users but less flexible

2. **How to handle Jira workflows?**
   - Simple boards: any status → any status
   - Complex workflows: specific transitions only
   - Should we enforce workflow or allow any move attempt?

3. **Issue creation type selection**
   - Filesystem: type is optional metadata
   - Jira: issue type is required
   - Pop up selector? Default type in config?

4. **Description format**
   - Jira Cloud uses ADF (Atlassian Document Format)
   - Convert markdown ↔ ADF, or plain text only?
   - ADF conversion is complex but provides better rendering

5. **What about Jira Server/Data Center?**
   - Different API endpoints, different auth
   - Should we support it in MVP or focus on Cloud?

6. **Subtasks?**
   - Jira has parent/child relationships
   - Flatten to single list? Show hierarchy? Skip subtasks?

---

## Implementation Order Recommendation

1. **Repository abstraction** - Create protocol, ensure FilesystemRepository implements it
2. **Config extensions** - Add jira section to SltasksConfig model
3. **Jira client** - HTTP wrapper with auth, error handling
4. **JiraRepository (read)** - Implement get_all(), get_by_id()
5. **Backend selection** - Wire up in App based on config
6. **JiraRepository (write)** - Implement save(), transitions
7. **Polish** - Error messages, loading states, documentation

---

## Dependencies to Add

```toml
# pyproject.toml
[project.dependencies]
httpx = "^0.27"  # HTTP client for Jira API
```

No other new dependencies required for MVP.

---

## References

- [Jira Cloud REST API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
- [Jira Agile REST API](https://developer.atlassian.com/cloud/jira/software/rest/intro/)
- [API Token Generation](https://id.atlassian.com/manage-profile/security/api-tokens)
- [Atlassian Document Format](https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/)
