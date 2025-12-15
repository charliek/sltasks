# GitHub Projects Phase 2: Filesystem Sync Design

## Overview

Phase 2 adds **bidirectional filesystem sync** to the GitHub Projects integration. This enables:

1. **Offline viewing** - GitHub issues cached as local markdown files
2. **LLM workflow** - Create issues by writing markdown files, push to GitHub
3. **Local editing** - Edit issue content locally, sync changes back
4. **Conflict resolution** - Handle divergent changes between local and GitHub

**Prerequisite**: Phase 1 (GitHub-only mode) must be complete.

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sync direction | GitHub → local on startup; local → GitHub explicit | GitHub is source of truth |
| File naming | `{owner}-{repo}#{number}-{slug}.md` | Clear GitHub-managed indicator |
| Column in frontmatter | Slugified status (e.g., `in_progress`) | Matches Phase 1 pattern |
| Priority in frontmatter | Priority ID from board.priorities | Consistent with file provider |
| Conflict detection | Compare `updated` timestamp vs `last_synced` | Simple, reliable |
| Conflict resolution | GitHub wins by default; `push_changes: true` to override | Explicit user intent |
| Delete handling | Resync by default; `close_on_github: true` to close | Safe default |
| Ordering | Separate `tasks.yaml` file | Same as file provider |
| Filter syntax | GitHub search syntax subset | Familiar to GitHub users |

---

## Configuration

### Sync Configuration in sltasks.yml

```yaml
github:
  # ... existing Phase 1 config ...

  sync:
    enabled: true              # Enable filesystem sync
    task_root: .tasks          # Where to write synced files

    # Filters use GitHub search syntax (OR'd together)
    # If any filter matches, the issue is synced
    filters:
      - "assignee:@me"         # All my issues
      - "label:urgent"         # Anything labeled urgent
      - "is:open"              # All open issues

    # Special values:
    # - Omit filters or use "*" to sync all issues on board
    # - "assignee:@me" uses the authenticated user
```

### Supported Filter Syntax

| Filter | Description | Example |
|--------|-------------|---------|
| `assignee:@me` | Issues assigned to authenticated user | `assignee:@me` |
| `assignee:USER` | Issues assigned to specific user | `assignee:octocat` |
| `label:NAME` | Issues with specific label | `label:bug` |
| `is:open` | Open issues only | `is:open` |
| `is:closed` | Closed issues only | `is:closed` |
| `*` | All issues on board | `*` |

Filters are OR'd together - an issue syncs if it matches ANY filter.

---

## File Format

### Synced Issue File

```markdown
---
title: Fix login validation bug
state: in_progress              # Slugified GitHub Status
priority: high                  # Priority ID from board.priorities
type: bug                       # Type ID from board.types
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
  project_item_id: PVTI_lADOBrU...
  issue_node_id: I_kwDOBrU...
  last_synced: '2025-01-15T14:00:00Z'
  priority_source: field        # "field" or "label"
  priority_label: null          # Original label if from labels

# User-controlled flags
push_changes: false             # Set true to push local edits to GitHub
close_on_github: false          # Set true to close issue when file deleted
---

## Description

The login form accepts invalid email formats...

## Steps to Reproduce

1. Navigate to /login
2. Enter "notanemail" in email field
3. Click submit

## Expected Behavior

Show validation error for invalid email format.
```

### New Local-Only File (Not Yet on GitHub)

```markdown
---
title: Add dark mode support
state: backlog
priority: medium
type: feature
tags:
  - ui
  - accessibility
---

Implement dark mode theme option in settings.

## Requirements

- Toggle in settings screen
- Persist preference
- Support system preference detection
```

Note: No `github:` section indicates this is a local-only file.

### File Naming Convention

| File State | Name Pattern | Example |
|------------|--------------|---------|
| Synced from GitHub | `{owner}-{repo}#{number}-{slug}.md` | `owner-repo#123-fix-login-bug.md` |
| New local file | `{slug}.md` | `add-dark-mode.md` |
| After push | Renamed to synced format | `owner-repo#456-add-dark-mode.md` |

---

## Sync Engine Architecture

### Component Structure

```
GitHubSyncEngine
├── sync_from_github()       # Pull: GitHub → local files
│   ├── fetch_filtered_issues()
│   ├── write_issue_to_file()
│   └── update_tasks_yaml()
│
├── push_to_github()         # Push: local → GitHub
│   ├── detect_local_changes()
│   ├── create_new_issues()
│   ├── update_existing_issues()
│   └── rename_pushed_files()
│
├── detect_changes()         # Find modified/new/deleted files
│   ├── find_new_local_files()
│   ├── find_modified_files()
│   └── find_deleted_files()
│
├── resolve_conflicts()      # Compare timestamps
│   └── determine_winner()   # GitHub wins unless push_changes=true
│
└── get_sync_status()        # For TUI display
    └── categorize_files()   # local, modified, synced, conflict
```

### GitHubSyncEngine Class

```python
class GitHubSyncEngine:
    """Handles bidirectional sync between GitHub and filesystem."""

    def __init__(
        self,
        repository: GitHubProjectsRepository,
        config: GitHubConfig,
        task_root: Path,
    ):
        self.repository = repository
        self.config = config
        self.task_root = task_root

    def sync_from_github(self, dry_run: bool = False) -> SyncResult:
        """Pull issues from GitHub and write to local files."""
        ...

    def push_to_github(
        self,
        files: list[Path] | None = None,
        dry_run: bool = False,
    ) -> PushResult:
        """Push local changes to GitHub."""
        ...

    def detect_changes(self) -> ChangeSet:
        """Scan local files and detect changes since last sync."""
        ...

    def get_sync_status(self) -> SyncStatus:
        """Get current sync status for TUI display."""
        ...
```

### Data Classes

```python
@dataclass
class SyncResult:
    """Result of sync_from_github operation."""
    synced: list[str]           # Task IDs that were synced
    created: list[str]          # New files created
    updated: list[str]          # Existing files updated
    conflicts: list[Conflict]   # Files with conflicts
    errors: list[SyncError]     # Errors encountered

@dataclass
class PushResult:
    """Result of push_to_github operation."""
    created: list[str]          # New issues created
    updated: list[str]          # Existing issues updated
    renamed: dict[str, str]     # Old filename -> new filename
    errors: list[PushError]     # Errors encountered

@dataclass
class ChangeSet:
    """Detected changes in local files."""
    new_files: list[Path]       # Files without github: section
    modified_files: list[Path]  # Files with push_changes: true
    deleted_files: list[Path]   # Previously synced files now missing
    conflicts: list[Conflict]   # Local changes + GitHub changes

@dataclass
class Conflict:
    """Conflict between local and GitHub versions."""
    file_path: Path
    task_id: str
    local_updated: datetime
    github_updated: datetime
    resolution: str             # "github_wins" or "local_wins"

@dataclass
class SyncStatus:
    """Current sync status for display."""
    local_only: list[Path]      # New files not on GitHub
    modified: list[Path]        # Modified files pending push
    synced: list[Path]          # Fully synced files
    conflicts: list[Conflict]   # Files with conflicts
    last_sync: datetime | None  # Last successful sync time
```

---

## Sync Operations

### 1. Pull from GitHub (`sltasks sync`)

**Flow:**

1. Authenticate and validate configuration
2. Fetch all project items from GitHub (using existing repository)
3. Apply filters to determine which issues to sync
4. For each matching issue:
   a. Check if local file exists (by issue_number lookup)
   b. If exists: compare timestamps, update if GitHub is newer
   c. If not exists: create new file with proper naming
5. Update `tasks.yaml` with ordering
6. Report results

**Conflict Handling:**

- If local file has changes AND GitHub has changes since `last_synced`:
  - Check `push_changes` flag in frontmatter
  - If `push_changes: true`: mark for push, don't overwrite
  - If `push_changes: false`: GitHub wins, overwrite local

### 2. Push to GitHub (`sltasks push`)

**Flow:**

1. Scan task_root for markdown files
2. Categorize files:
   - **New**: No `github:` section → will create issue
   - **Modified**: `push_changes: true` → will update issue
   - **Delete**: `close_on_github: true` + file missing → will close issue
3. For new files:
   a. Create issue via repository
   b. Add to project
   c. Set Status field
   d. Rename file to include issue number
4. For modified files:
   a. Update issue via repository
   b. Update `last_synced` timestamp
   c. Reset `push_changes` to false
5. Report results

### 3. Dry Run Mode

Both sync and push support `--dry-run`:

```bash
sltasks sync --dry-run     # Show what would be synced
sltasks push --dry-run     # Show what would be pushed
```

Output:
```
Dry run - no changes will be made

Would sync 5 issues from GitHub:
  [new]     owner/repo#123 - Fix login bug
  [update]  owner/repo#124 - Update README
  [skip]    owner/repo#125 - Already synced

Would create 2 local files:
  .tasks/owner-repo#123-fix-login-bug.md
  .tasks/owner-repo#124-update-readme.md
```

---

## TUI Integration

### Sync Status Indicators

Task cards show sync status in the TUI:

| Indicator | Meaning | Color |
|-----------|---------|-------|
| `[local]` | Local-only file, not on GitHub | Blue |
| `[modified]` | Local edits pending push | Yellow |
| `[synced]` | Fully synced with GitHub | Green |
| `[conflict]` | Both local and GitHub changed | Red |
| (none) | GitHub-only mode (sync disabled) | - |

### Keybindings

| Key | Action | When |
|-----|--------|------|
| `r` | Refresh from GitHub | Always |
| `S` | Open sync status screen | Sync enabled |
| `p` | Push current task | Task is local/modified |

### Sync Status Screen

Accessed via `S` keybinding:

```
┌─────────────────────────────────────────────────────────────┐
│ Sync Status                                          [ESC] │
├─────────────────────────────────────────────────────────────┤
│ New Local Files (will create issues):                       │
│   [x] add-dark-mode.md → owner/repo                        │
│   [ ] fix-typo.md → owner/repo                             │
│                                                             │
│ Modified Files (will update issues):                        │
│   [x] owner-repo#123-fix-login-bug.md                      │
│                                                             │
│ Conflicts (both local and GitHub changed):                  │
│   [ ] owner-repo#124-update-readme.md                      │
│       Local: 2025-01-15 10:30  GitHub: 2025-01-15 11:00    │
│       [GitHub will win - set push_changes: true to push]   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│ [Space] Toggle  [Enter] Push Selected  [r] Refresh  [ESC]  │
└─────────────────────────────────────────────────────────────┘
```

**Screen Actions:**

- `Space` - Toggle selection for push
- `Enter` - Push all selected items
- `r` - Refresh status (re-scan files and GitHub)
- `ESC` - Close screen

---

## CLI Commands

### `sltasks sync`

Pull issues from GitHub to local filesystem.

```bash
# Interactive sync
sltasks sync

# Preview only
sltasks sync --dry-run

# Force overwrite local changes
sltasks sync --force
```

**Options:**

| Flag | Description |
|------|-------------|
| `--dry-run` | Show what would sync without making changes |
| `--force` | Overwrite local changes even if modified |

### `sltasks push`

Push local changes to GitHub.

```bash
# Interactive push (shows preview, prompts for confirmation)
sltasks push

# Preview only
sltasks push --dry-run

# Push specific files
sltasks push add-dark-mode.md fix-typo.md

# Push all without confirmation
sltasks push --yes
```

**Options:**

| Flag | Description |
|------|-------------|
| `--dry-run` | Show what would push without making changes |
| `--yes` | Skip confirmation prompt |

---

## Delete Handling

### Default Behavior: Resync

When a synced file is deleted locally:

1. On next `sltasks sync`, the file is recreated from GitHub
2. The issue remains open on GitHub
3. This is the safe default for accidental deletions

### Explicit Close: `close_on_github: true`

To actually close a GitHub issue when deleting the local file:

1. Edit the file and set `close_on_github: true`
2. Delete the file
3. Run `sltasks push`
4. The issue will be closed on GitHub

```markdown
---
title: Old task to close
state: done
close_on_github: true   # ← Set this before deleting
---
```

This two-step process prevents accidental issue closure.

---

## Conflict Resolution

### Detection

A conflict occurs when:
- Local file has `updated` timestamp > `last_synced`
- AND GitHub issue has `updatedAt` > `last_synced`

### Resolution Strategy

| Scenario | Resolution |
|----------|------------|
| Local changed, GitHub unchanged | Local wins (can push) |
| Local unchanged, GitHub changed | GitHub wins (sync overwrites) |
| Both changed, `push_changes: false` | GitHub wins |
| Both changed, `push_changes: true` | Local wins (push to GitHub) |

### User Workflow for Conflicts

1. Run `sltasks sync`
2. Conflicts are reported in output
3. Open sync screen (`S`) to review
4. For each conflict:
   - Review diff between local and GitHub
   - Either: accept GitHub version (do nothing)
   - Or: set `push_changes: true` and push

---

## Implementation Tasks

### Phase 2.1: Core Sync Engine

- [ ] Create `GitHubSyncEngine` class
- [ ] Implement `sync_from_github()` with filtering
- [ ] Implement `detect_changes()` for local file scanning
- [ ] Implement `push_to_github()` with file renaming
- [ ] Add sync metadata to frontmatter parsing
- [ ] Update `tasks.yaml` handling for synced files

### Phase 2.2: CLI Commands

- [ ] Add `sync` subcommand to CLI
- [ ] Add `push` subcommand to CLI
- [ ] Implement `--dry-run` for both commands
- [ ] Add progress output for sync operations

### Phase 2.3: TUI Integration

- [ ] Add sync status indicators to task cards
- [ ] Create `SyncScreen` widget
- [ ] Add `S` keybinding for sync screen
- [ ] Add `p` keybinding for push current task

### Phase 2.4: Conflict Resolution

- [ ] Implement conflict detection
- [ ] Add conflict display in sync screen
- [ ] Implement resolution based on `push_changes` flag

### Phase 2.5: Testing

- [ ] Unit tests for GitHubSyncEngine
- [ ] Integration tests with mocked GitHub API
- [ ] CLI command tests
- [ ] TUI tests for sync indicators

---

## Migration from Phase 1

Phase 2 is **fully additive**:

- Existing Phase 1 configs work unchanged
- `sync.enabled: false` (or omitted) = Phase 1 behavior
- `sync.enabled: true` = Enable filesystem sync
- No migration steps required

---

## Error Handling

| Error | Handling |
|-------|----------|
| Network error during sync | Retry with backoff, show error if persistent |
| File write permission error | Skip file, report in results |
| Invalid frontmatter | Skip file, report in results |
| Conflict with no resolution | Keep local, don't sync |
| Push fails for one file | Continue with others, report failures |

### Error Messages

```
Error: Cannot sync - no network connection
  Check your internet connection and try again.

Warning: Skipped 2 files with invalid frontmatter:
  .tasks/broken-file.md - Missing title field
  .tasks/another.md - Invalid YAML syntax

Conflict: owner/repo#123 has changes on both local and GitHub
  Local modified: 2025-01-15 10:30
  GitHub modified: 2025-01-15 11:00
  Action: GitHub version preserved (set push_changes: true to push local)
```

---

## Performance Considerations

### Caching

- Cache GitHub issue metadata in memory during session
- Only fetch full issue content when needed for sync
- Use `If-Modified-Since` headers where possible

### Pagination

- GitHub limits items to 100 per query
- Implement cursor-based pagination
- Show progress for large projects

### File I/O

- Batch file writes where possible
- Use atomic writes (write to temp, rename)
- Minimize file system scans

---

## References

- [Phase 1 Implementation](../../plans/github-projects-phase1-implementation.md)
- [Integration Requirements](./github-projects-integration-requirements.md)
- [GitHub GraphQL API](https://docs.github.com/en/graphql)
