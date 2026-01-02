# Phase 2B: Bidirectional Sync

**Epic:** [github-phase2-epic.md](./github-phase2-epic.md)
**Previous:** [Phase 2A](./github-phase2-phase-a.md)
**Status:** Complete
**Prerequisites:** Phase 2A complete

## Overview

Phase 2B implements full bidirectional synchronization between GitHub and the local filesystem. Users can pull issues from GitHub to local files, edit them locally, and push changes back.

**Key deliverables:**
- `sltasks sync` command to pull issues from GitHub
- Filter parser for GitHub search syntax
- Push updates to existing issues
- Conflict detection and resolution

---

## Tasks

### 1. Filter Parser

#### 1.1 Create sync/filter_parser.py
- [x] Create `src/sltasks/sync/filter_parser.py`
- [x] Implement `SyncFilterParser` class:
  ```python
  @dataclass
  class ParsedFilter:
      assignee: str | None = None      # "@me" or username
      labels: list[str] = field(default_factory=list)
      milestone: str | None = None
      state: str = "open"              # "open", "closed", "all"
      repo: str | None = None          # "owner/repo"

  class SyncFilterParser:
      def parse(self, expression: str) -> ParsedFilter: ...
      def matches_issue(self, filter_: ParsedFilter, issue: dict, current_user: str) -> bool: ...
  ```
- [x] Supported filter syntax:
  | Filter | Description |
  |--------|-------------|
  | `assignee:@me` | Authenticated user |
  | `assignee:USER` | Specific username |
  | `label:NAME` | Issue has label |
  | `is:open` / `is:closed` | Issue state |
  | `milestone:NAME` | Issue in milestone |
  | `repo:owner/name` | Specific repository |
  | `*` | Match all |
- [x] Multiple terms in one filter are AND'd
- [x] Helpful error messages for invalid syntax
- [x] Comprehensive unit tests

**Files:**
- `src/sltasks/sync/filter_parser.py` (new)
- `tests/test_sync_filter_parser.py` (new)

---

### 2. Sync Engine - Pull

#### 2.1 Extend GitHubSyncEngine for Pull
- [x] Extend engine from Phase 2A or create unified `GitHubSyncEngine`
- [x] Implement `_fetch_all_project_issues()`:
  - Query GitHub project items via existing `GitHubProjectsRepository`
  - Return raw issue data for filtering
- [x] Implement `_apply_filters(issues, filters)`:
  - Apply configured filters (OR logic - any filter match syncs)
  - Handle `@me` expansion to current username
  - Return filtered list
- [x] Implement `_write_issue_to_file(issue)`:
  - Generate synced filename via `file_mapper`
  - Create/update markdown file with full frontmatter:
    - Standard fields: title, state, priority, type, tags, created, updated
    - `github:` section with sync metadata
    - `push_changes: false` (default)
    - `close_on_github: false` (default)
  - Use `frontmatter` library (same as filesystem repo)
- [x] Integration tests with mocked API

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

#### 2.2 Implement sync_from_github()
- [x] Implement main sync orchestration:
  ```python
  def sync_from_github(
      self,
      dry_run: bool = False,
      force: bool = False,
  ) -> SyncResult: ...
  ```
- [x] Workflow:
  1. Fetch all project issues from GitHub
  2. Apply configured filters
  3. For each matching issue:
     a. Check if local file exists (by issue number lookup)
     b. If not exists: create new file
     c. If exists: compare timestamps for conflict detection
     d. Handle based on conflict resolution rules
  4. Update `tasks.yaml` ordering
  5. Return `SyncResult` with counts
- [x] `dry_run` mode: report changes without writing
- [x] `force` mode: overwrite local changes without prompting
- [x] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 3. Sync Data Models (Extended)

#### 3.1 Add Additional Models to sync.py
- [x] Implement `SyncResult`:
  ```python
  @dataclass
  class SyncResult:
      pulled: int = 0           # Files created/updated from GitHub
      skipped: int = 0          # Files skipped (no changes)
      conflicts: int = 0        # Conflicts detected
      errors: list[str] = field(default_factory=list)
      dry_run: bool = False
  ```
- [x] Implement `ChangeSet`:
  ```python
  @dataclass
  class ChangeSet:
      to_pull: list[SyncChange] = field(default_factory=list)
      to_push: list[SyncChange] = field(default_factory=list)
      conflicts: list[Conflict] = field(default_factory=list)
  ```
- [x] Implement `Conflict`:
  ```python
  @dataclass
  class Conflict:
      task_id: str
      local_path: Path
      issue_number: int
      repository: str
      local_updated: datetime
      remote_updated: datetime
      last_synced: datetime
  ```
- [x] Unit tests for new models

**Files:**
- `src/sltasks/models/sync.py`
- `tests/test_sync_models.py`

---

### 4. Sync Engine - Push Updates

#### 4.1 Implement Push for Modified Files
- [x] Extend `detect_changes()` to find modified synced files:
  - File has `github:` section (is synced)
  - File `updated` > `github.last_synced`
  - File has `push_changes: true`
- [x] Implement `_update_github_issue(task)`:
  - Update issue title/body via GraphQL
  - Update status field if `state` changed
  - Update labels for type/priority changes
  - Update tags (add/remove labels)
  - Reference `GitHubProjectsRepository._update_issue()` for patterns
- [x] Implement `push_changes()`:
  ```python
  def push_changes(
      self,
      dry_run: bool = False,
  ) -> PushResult: ...
  ```
- [x] After successful push:
  - Update `github.last_synced` in frontmatter
  - Reset `push_changes: false`
- [x] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

#### 4.2 Handle close_on_github Flag
- [x] Detect files with `close_on_github: true` that are deleted/archived
- [x] Close the corresponding GitHub issue
- [x] Remove from local sync tracking
- [x] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 5. Conflict Detection and Resolution

#### 5.1 Implement Conflict Detection
- [x] In `detect_changes()`, detect conflicts:
  - Local file `updated` > `github.last_synced` (local changed)
  - GitHub `updatedAt` > `github.last_synced` (remote changed)
  - If both: CONFLICT
- [x] Store conflict details in `ChangeSet.conflicts`
- [x] Unit tests for conflict scenarios

#### 5.2 Implement Conflict Resolution
- [x] Resolution based on `push_changes` flag:
  | `push_changes` | Resolution |
  |----------------|------------|
  | `false` (default) | GitHub wins - overwrite local |
  | `true` | Local wins - push to GitHub |
- [x] In `sync_from_github()`:
  - If conflict and `push_changes: false`: overwrite local
  - If conflict and `push_changes: true`: skip (will be pushed)
- [x] Report conflicts in `SyncResult`
- [x] Tests for both resolution paths

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 6. CLI Sync Command

#### 6.1 Create cli/sync.py
- [x] Create `src/sltasks/cli/sync.py`
- [x] Implement `run_sync()`:
  ```python
  def run_sync(
      project_root: Path,
      dry_run: bool = False,
      force: bool = False,
  ) -> int: ...
  ```
- [x] Workflow:
  1. Load config, validate `github.sync.enabled: true`
  2. Authenticate GitHub client
  3. Initialize sync engine
  4. Call `detect_changes()` and display summary
  5. If `dry_run`: show preview and exit
  6. If conflicts and not `force`: warn user
  7. Execute `sync_from_github()`
  8. Report results
- [x] Progress output for large syncs
- [x] CLI tests

**Files:**
- `src/sltasks/cli/sync.py` (new)
- `tests/test_cli_sync.py` (new)

#### 6.2 Update __main__.py
- [x] Add `sync` subcommand:
  ```python
  sync_parser = subparsers.add_parser("sync", help="Sync with GitHub")
  sync_parser.add_argument("--dry-run", action="store_true")
  sync_parser.add_argument("--force", action="store_true")
  ```
- [x] Route to `run_sync()` when subcommand is `sync`

**Files:**
- `src/sltasks/__main__.py`

---

### 7. Extend Push Command

#### 7.1 Update cli/push.py for Sync Mode
- [x] When `sync.enabled: true`, push command should:
  - Also detect and offer to push modified synced files
  - Show separate sections: "New issues" vs "Updated issues"
- [x] When `sync.enabled: false`, behavior unchanged from Phase 2A
- [x] Update CLI help text
- [x] CLI tests for both modes

**Files:**
- `src/sltasks/cli/push.py`
- `tests/test_cli_push.py`

---

### 8. Frontmatter Writing

#### 8.1 Implement Sync Frontmatter Writing
- [x] Create utility function `write_synced_task_file(task, path)`:
  - Write standard frontmatter fields
  - Write `github:` section with all sync metadata
  - Write `push_changes: false` and `close_on_github: false`
  - Preserve body content
- [x] Use `frontmatter` library with `sort_keys=False`
- [x] Ensure atomic writes (temp file + rename)
- [x] Unit tests for frontmatter formatting

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 9. Tasks.yaml Integration

#### 9.1 Update Ordering for Synced Files
- [x] When sync creates new files, add to `tasks.yaml`
- [x] Respect existing `BoardOrder` patterns from filesystem repo
- [x] When sync removes files, update `tasks.yaml`
- [x] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 10. Testing

#### 10.1 Unit Tests
- [x] `test_sync_filter_parser.py` - all filter syntax variations
- [x] `test_sync_models.py` - SyncResult, ChangeSet, Conflict
- [x] `test_sync_engine.py` - individual method tests

#### 10.2 Integration Tests
- [x] Sync pull - create new files from GitHub
- [x] Sync pull - update existing files
- [x] Sync pull - handle conflicts
- [x] Push updates - modify existing issues
- [x] Push updates - close issues
- [x] Full round-trip: create local → push → modify on GitHub → sync

#### 10.3 Manual Testing Checklist
- [x] Configure `sync.enabled: true` with filters
- [x] Run `sltasks sync --dry-run` - see preview
- [x] Run `sltasks sync` - files created locally
- [x] Verify files have correct frontmatter and body
- [x] Edit local file, set `push_changes: true`
- [x] Run `sltasks push` - issue updated on GitHub
- [x] Modify issue on GitHub
- [x] Run `sltasks sync` - local file updated
- [x] Create conflict scenario - verify resolution

---

## Acceptance Criteria

- [x] Filter parser handles all documented syntax
- [x] `sltasks sync` pulls issues matching configured filters
- [x] Synced files have complete `github:` metadata section
- [x] `sltasks sync --dry-run` shows preview without changes
- [x] `sltasks sync --force` overwrites local changes
- [x] Modified files with `push_changes: true` are pushed
- [x] Conflicts detected and resolved per `push_changes` flag
- [x] `close_on_github: true` closes issues when file deleted
- [x] All tests pass
- [x] Round-trip sync works correctly

---

## Files Created/Modified

### New Files
| File | Purpose |
|------|---------|
| `src/sltasks/sync/filter_parser.py` | Filter syntax parser |
| `src/sltasks/cli/sync.py` | CLI sync command |
| `tests/test_sync_filter_parser.py` | Filter parser tests |
| `tests/test_cli_sync.py` | Sync CLI tests |

### Modified Files
| File | Changes |
|------|---------|
| `src/sltasks/models/sync.py` | Add SyncResult, ChangeSet, Conflict |
| `src/sltasks/sync/engine.py` | Add pull, push updates, conflicts |
| `src/sltasks/sync/__init__.py` | Export filter parser |
| `src/sltasks/cli/push.py` | Support sync mode |
| `src/sltasks/__main__.py` | Add sync subcommand |
| `tests/test_sync_engine.py` | Extend with sync tests |
| `tests/test_cli_push.py` | Add sync mode tests |

---

## Dependencies

- Phase 2A must be complete
- No external dependencies to add

---

## Deviations & Insights

_Updated during implementation_

### Deviations from Plan
- [x] Implemented `push_updates()` method instead of `push_changes()` for naming consistency
- [x] Filter parser uses `tuple[str, ...]` for labels instead of `list[str]` for immutability
- [x] Added `matches_any_filter()` method for OR-based filter matching

### Key Implementation Insights
- [x] Reused existing GraphQL queries from `github/queries.py` - no new queries needed
- [x] Conflict detection uses `last_synced` timestamp comparison for bidirectional change detection
- [x] `_write_issue_to_file()` handles both creating new files and updating existing synced files

### Blockers Encountered
- [x] None - Phase 2A infrastructure was well-designed for extension

### Open Questions Resolved
- [x] How to handle deleted GitHub issues? → Skip during sync, local file remains as orphan
- [x] How to detect conflicts? → Compare local `updated`, remote `updatedAt`, and `last_synced`
