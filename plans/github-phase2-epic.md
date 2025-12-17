# GitHub Phase 2: Filesystem Sync - Epic Plan

## Overview

Phase 2 adds **bidirectional filesystem sync** to the GitHub Projects integration, enabling:
- **Offline viewing** - GitHub issues cached as local markdown files
- **LLM workflow** - Create issues by writing markdown files, push to GitHub
- **Local editing** - Edit issue content locally, sync changes back
- **Conflict resolution** - Handle divergent changes between local and GitHub

**Key Architecture:** Sync is part of the GitHub provider (not a separate provider). Users configure `provider: github` and optionally enable sync to cache a filtered subset of issues to the filesystem. This extends the filesystem repository's file format with GitHub metadata.

**Prerequisite:** Phase 1 (GitHub-only mode) must be complete.

---

## New Features Summary

| Feature | Description | Phase |
|---------|-------------|-------|
| `sltasks push` (standalone) | Push new local files to GitHub **even without sync enabled** | A |
| `sltasks sync` | CLI command to pull issues from GitHub to local `.md` files | B |
| `sltasks push` (with sync) | Push local changes/new files to GitHub, update existing | B |
| Sync indicators | TUI badges showing sync status on task cards | C |
| Sync screen | TUI screen for reviewing and managing sync status (`S` key) | C |
| Conflict detection | Timestamp-based conflict detection with resolution options | B |
| Filter support | GitHub search syntax subset for selective sync | B |

---

## Push Without Sync (Standalone Feature)

Even with `sync.enabled: false`, users can:
1. Write local `.md` files (manually or via LLM)
2. Run `sltasks push` or use TUI to push new issues
3. After push, choose to delete or archive the local file

**Behavior:**
- Creates NEW GitHub issues only (one-time push)
- Once pushed, local file is marked `archived: true` or deleted (user choice)
- No update capability without sync - pushed issues are managed on GitHub
- Useful for LLM-generated issues workflow

---

## File Structure

### New Files
```
src/sltasks/
  models/
    sync.py                     # SyncStatus, ChangeSet, Conflict, SyncResult, etc.
  sync/
    __init__.py
    engine.py                   # GitHubSyncEngine - core sync logic
    filter_parser.py            # GitHub search syntax parser
    file_mapper.py              # Maps GitHub issues <-> local files
  cli/
    sync.py                     # sltasks sync command
    push.py                     # sltasks push command
  ui/
    screens/
      sync_screen.py            # TUI sync screen
tests/
  test_sync_engine.py
  test_sync_filter_parser.py
  test_sync_cli.py
```

### Files to Modify
```
src/sltasks/
  models/sltasks_config.py      # Add GitHubSyncConfig
  models/provider_data.py       # Extend GitHubProviderData with sync fields
  repositories/filesystem.py    # Parse sync metadata from frontmatter
  __main__.py                   # Add sync/push subcommands
  app.py                        # Add sync keybindings and service
  ui/widgets/task_card.py       # Add sync status indicator
```

---

## Configuration Design

### sltasks.yml Extension
```yaml
github:
  project_url: "https://github.com/users/owner/projects/1"
  default_repo: owner/repo

  sync:
    enabled: true               # Enable filesystem sync
    task_root: .tasks           # Where to write synced files (default from global)

    # Filters use GitHub search syntax (OR'd together - any match syncs)
    filters:
      - "assignee:@me"                    # All my issues
      - "label:urgent"                    # Anything marked urgent
      - "assignee:@me is:open"           # My open issues
      - "label:priority:high milestone:v2.0"  # High-pri in milestone
    # Omit filters or use ["*"] to sync all issues on board
```

### Filter Syntax (GitHub Search Subset)
| Filter | Description | Example |
|--------|-------------|---------|
| `assignee:@me` | Issues assigned to authenticated user | `assignee:@me` |
| `assignee:USER` | Issues assigned to specific user | `assignee:octocat` |
| `label:NAME` | Issues with specific label | `label:bug` |
| `is:open` / `is:closed` | Filter by state | `is:open` |
| `milestone:NAME` | Issues in milestone | `milestone:"v2.0"` |
| `repo:owner/name` | Filter by repository | `repo:acme/backend` |
| `*` | All issues on board | `*` |

Multiple terms in one filter are AND'd: `"assignee:@me label:bug is:open"` = my open bugs

### GitHubSyncConfig Model
```python
class GitHubSyncConfig(BaseModel):
    enabled: bool = False
    task_root: str | None = None  # Override global task_root if needed
    filters: list[str] = Field(default_factory=list)  # GitHub search syntax strings
```

---

## File Format

### Synced Issue (from GitHub)
```markdown
---
title: Fix login validation bug
state: in_progress
priority: high
type: bug
tags:
  - auth
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
  priority_source: field
  priority_label: null

# User-controlled flags
push_changes: false
close_on_github: false
---

Issue body here...
```

### File Naming
| File State | Pattern | Example |
|------------|---------|---------|
| Synced from GitHub | `{owner}-{repo}#{number}-{slug}.md` | `owner-repo#123-fix-login-bug.md` |
| New local file | `{slug}.md` | `add-dark-mode.md` |
| After push | Renamed to synced format | `owner-repo#456-add-dark-mode.md` |

---

## GitHubSyncEngine Design

### Core Methods
```python
class GitHubSyncEngine:
    def __init__(
        self,
        config_service: ConfigService,
        github_client: GitHubClient,
        task_root: Path,
    ) -> None: ...

    # Core sync operations
    def detect_changes(self) -> ChangeSet: ...
    def sync_from_github(self, dry_run: bool = False, force: bool = False) -> SyncResult: ...
    def push_to_github(self, dry_run: bool = False, files: list[Path] | None = None) -> PushResult: ...

    # Status queries
    def get_sync_status(self, task_id: str) -> SyncStatus: ...
    def get_all_sync_statuses(self) -> dict[str, SyncStatus]: ...

    # Internal operations
    def _fetch_filtered_issues(self) -> list[dict]: ...
    def _write_issue_to_file(self, issue: dict) -> Task: ...
    def _create_github_issue(self, task: Task) -> dict: ...
    def _update_github_issue(self, task: Task) -> dict: ...
```

### SyncStatus Enum
```python
class SyncStatus(str, Enum):
    SYNCED = "synced"              # In sync with remote
    LOCAL_MODIFIED = "local_modified"  # Local changes pending push
    REMOTE_MODIFIED = "remote_modified" # Remote changes pending pull
    CONFLICT = "conflict"          # Both modified
    LOCAL_ONLY = "local_only"      # New local file, not on GitHub
```

---

## CLI Commands

### `sltasks sync`
```bash
sltasks sync              # Pull from GitHub to local files
sltasks sync --dry-run    # Show what would sync
sltasks sync --force      # Overwrite local changes
```

### `sltasks push`
```bash
sltasks push              # Push local changes to GitHub (interactive)
sltasks push --dry-run    # Show what would push
sltasks push --yes        # Skip confirmation
sltasks push --delete     # Delete local files after push
sltasks push --archive    # Archive local files after push
sltasks push file1.md     # Push specific files
```

---

## TUI Integration

### Sync Status Indicators
| Indicator | Meaning | Color |
|-----------|---------|-------|
| `●` | Synced | Green |
| `●` | Local modified | Yellow |
| `●` | Remote modified | Blue |
| `⚠` | Conflict | Red |
| `○` | Local only | Dim |

### Keybindings
| Key | Action |
|-----|--------|
| `r` | Refresh from GitHub (existing) |
| `S` | Open sync status screen |
| `p` | Push current task (if local/modified) |

---

## Implementation Phases

### [Phase 2A: Foundation & Push](./github-phase2-phase-a.md) (CLI Only) - COMPLETE
**Goal:** Enable creating GitHub issues from local files without full sync.

- [x] Models: `GitHubSyncConfig`, `SyncStatus`, `PushResult`
- [x] File mapper for synced filenames
- [x] Push engine for creating new issues
- [x] `sltasks push` CLI command
- [x] Post-push: delete or archive local files

**Deliverable:** Users can write local `.md` files and run `sltasks push`.

### [Phase 2B: Bidirectional Sync](./github-phase2-phase-b.md) - COMPLETE
**Goal:** Full sync between GitHub and filesystem via CLI.

- [x] Filter parser for GitHub search syntax
- [x] Sync engine - pull from GitHub
- [x] Sync engine - push updates to existing issues
- [x] Conflict detection and resolution
- [x] `sltasks sync` CLI command

**Deliverable:** Full bidirectional sync via CLI commands.

### [Phase 2C: TUI Integration & Polish](./github-phase2-phase-c.md)
**Goal:** Complete TUI experience and production readiness.

- Sync status indicators on task cards
- Sync management screen (`S` key)
- Push keybinding (`p` key)
- Updated `--github-setup` wizard
- Error handling and edge cases
- Performance optimization
- User documentation

**Deliverable:** Users can manage sync entirely from the TUI.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Architecture | Sync is part of GitHub provider | User configures `provider: github`, sync is optional |
| Push without sync | Supported - creates new issues only | LLM workflow: write local → push → delete/archive |
| Post-push behavior | User choice: delete or archive | Safe default, user controls local file fate |
| Filter syntax | Simple strings (GitHub search) | Familiar syntax, copy-paste from GitHub |
| Sync metadata location | In frontmatter under `github:` | Keeps all task data together, git-friendly |
| Filename convention | `{owner}-{repo}#{number}-{slug}.md` | Unique ID, human-readable, detects synced |
| Conflict default | GitHub wins unless `push_changes: true` | Safe default, explicit user intent |
| Delete handling | Resync unless `close_on_github: true` | Safe default for accidental deletions |
| Implementation order | CLI → Indicators → Full TUI | Each phase independently testable |

---

## Critical Files

| File | Purpose |
|------|---------|
| `src/sltasks/models/sltasks_config.py` | Add `GitHubSyncConfig` model |
| `src/sltasks/models/provider_data.py` | Extend `GitHubProviderData` with sync fields |
| `src/sltasks/models/sync.py` | New: sync data models |
| `src/sltasks/sync/engine.py` | New: `GitHubSyncEngine` class |
| `src/sltasks/sync/filter_parser.py` | New: filter string parser |
| `src/sltasks/cli/sync.py` | New: `sltasks sync` command |
| `src/sltasks/cli/push.py` | New: `sltasks push` command |
| `src/sltasks/__main__.py` | Add subcommand routing |
| `src/sltasks/repositories/filesystem.py` | Parse sync metadata from frontmatter |
| `src/sltasks/ui/widgets/task_card.py` | Add sync indicator |
| `src/sltasks/ui/screens/sync_screen.py` | New: sync management screen |

---

## Testing Strategy

- **Unit tests**: Models, filter parser, file mapper (no I/O)
- **Integration tests**: Sync engine with mocked `httpx` responses
- **CLI tests**: Command invocation with `tmp_path` fixtures
- **TUI tests**: Widget rendering with sync status

---

## Backward Compatibility

- `sync.enabled: false` (default) = Phase 1 behavior unchanged
- All existing `provider: github` configs continue to work
- No migration required

---

## Deviations & Insights

_This section is updated during implementation to track any deviations from the plan or key insights discovered._

### Deviations from Original Design
- [x] **Phase 2A:** Engine takes `task_root: Path` instead of `github_repo: GitHubProjectsRepository` - simpler design
- [x] **Phase 2A:** Added `ParsedSyncedFilename` dataclass for structured filename parsing results
- [x] **Phase 2A:** Some integration tests deferred to Phase 2B when sync engine is more complete

### Key Implementation Insights
- [x] **Phase 2A:** Reused GraphQL queries from `github/queries.py` - no new queries needed for push
- [x] **Phase 2A:** Frontmatter library returns `object` type - requires explicit `dict()` cast for type safety
- [x] **Phase 2A:** Post-push file handling supports delete, archive, and rename actions

### Open Questions Resolved
- [x] How to detect local-only vs synced files? → Check for `github:` section with `synced: true`
- [x] What happens after push? → User choice: delete, archive, or rename to synced format
