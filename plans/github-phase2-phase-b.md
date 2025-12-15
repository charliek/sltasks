# Phase 2B: Bidirectional Sync

**Epic:** [github-phase2-epic.md](./github-phase2-epic.md)
**Previous:** [Phase 2A](./github-phase2-phase-a.md)
**Status:** Not Started
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
- [ ] Create `src/sltasks/sync/filter_parser.py`
- [ ] Implement `SyncFilterParser` class:
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
- [ ] Supported filter syntax:
  | Filter | Description |
  |--------|-------------|
  | `assignee:@me` | Authenticated user |
  | `assignee:USER` | Specific username |
  | `label:NAME` | Issue has label |
  | `is:open` / `is:closed` | Issue state |
  | `milestone:NAME` | Issue in milestone |
  | `repo:owner/name` | Specific repository |
  | `*` | Match all |
- [ ] Multiple terms in one filter are AND'd
- [ ] Helpful error messages for invalid syntax
- [ ] Comprehensive unit tests

**Files:**
- `src/sltasks/sync/filter_parser.py` (new)
- `tests/test_sync_filter_parser.py` (new)

---

### 2. Sync Engine - Pull

#### 2.1 Extend GitHubSyncEngine for Pull
- [ ] Extend engine from Phase 2A or create unified `GitHubSyncEngine`
- [ ] Implement `_fetch_all_project_issues()`:
  - Query GitHub project items via existing `GitHubProjectsRepository`
  - Return raw issue data for filtering
- [ ] Implement `_apply_filters(issues, filters)`:
  - Apply configured filters (OR logic - any filter match syncs)
  - Handle `@me` expansion to current username
  - Return filtered list
- [ ] Implement `_write_issue_to_file(issue)`:
  - Generate synced filename via `file_mapper`
  - Create/update markdown file with full frontmatter:
    - Standard fields: title, state, priority, type, tags, created, updated
    - `github:` section with sync metadata
    - `push_changes: false` (default)
    - `close_on_github: false` (default)
  - Use `frontmatter` library (same as filesystem repo)
- [ ] Integration tests with mocked API

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

#### 2.2 Implement sync_from_github()
- [ ] Implement main sync orchestration:
  ```python
  def sync_from_github(
      self,
      dry_run: bool = False,
      force: bool = False,
  ) -> SyncResult: ...
  ```
- [ ] Workflow:
  1. Fetch all project issues from GitHub
  2. Apply configured filters
  3. For each matching issue:
     a. Check if local file exists (by issue number lookup)
     b. If not exists: create new file
     c. If exists: compare timestamps for conflict detection
     d. Handle based on conflict resolution rules
  4. Update `tasks.yaml` ordering
  5. Return `SyncResult` with counts
- [ ] `dry_run` mode: report changes without writing
- [ ] `force` mode: overwrite local changes without prompting
- [ ] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 3. Sync Data Models (Extended)

#### 3.1 Add Additional Models to sync.py
- [ ] Implement `SyncResult`:
  ```python
  @dataclass
  class SyncResult:
      pulled: int = 0           # Files created/updated from GitHub
      skipped: int = 0          # Files skipped (no changes)
      conflicts: int = 0        # Conflicts detected
      errors: list[str] = field(default_factory=list)
      dry_run: bool = False
  ```
- [ ] Implement `ChangeSet`:
  ```python
  @dataclass
  class ChangeSet:
      to_pull: list[SyncChange] = field(default_factory=list)
      to_push: list[SyncChange] = field(default_factory=list)
      conflicts: list[Conflict] = field(default_factory=list)
  ```
- [ ] Implement `Conflict`:
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
- [ ] Unit tests for new models

**Files:**
- `src/sltasks/models/sync.py`
- `tests/test_sync_models.py`

---

### 4. Sync Engine - Push Updates

#### 4.1 Implement Push for Modified Files
- [ ] Extend `detect_changes()` to find modified synced files:
  - File has `github:` section (is synced)
  - File `updated` > `github.last_synced`
  - File has `push_changes: true`
- [ ] Implement `_update_github_issue(task)`:
  - Update issue title/body via GraphQL
  - Update status field if `state` changed
  - Update labels for type/priority changes
  - Update tags (add/remove labels)
  - Reference `GitHubProjectsRepository._update_issue()` for patterns
- [ ] Implement `push_changes()`:
  ```python
  def push_changes(
      self,
      dry_run: bool = False,
  ) -> PushResult: ...
  ```
- [ ] After successful push:
  - Update `github.last_synced` in frontmatter
  - Reset `push_changes: false`
- [ ] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

#### 4.2 Handle close_on_github Flag
- [ ] Detect files with `close_on_github: true` that are deleted/archived
- [ ] Close the corresponding GitHub issue
- [ ] Remove from local sync tracking
- [ ] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 5. Conflict Detection and Resolution

#### 5.1 Implement Conflict Detection
- [ ] In `detect_changes()`, detect conflicts:
  - Local file `updated` > `github.last_synced` (local changed)
  - GitHub `updatedAt` > `github.last_synced` (remote changed)
  - If both: CONFLICT
- [ ] Store conflict details in `ChangeSet.conflicts`
- [ ] Unit tests for conflict scenarios

#### 5.2 Implement Conflict Resolution
- [ ] Resolution based on `push_changes` flag:
  | `push_changes` | Resolution |
  |----------------|------------|
  | `false` (default) | GitHub wins - overwrite local |
  | `true` | Local wins - push to GitHub |
- [ ] In `sync_from_github()`:
  - If conflict and `push_changes: false`: overwrite local
  - If conflict and `push_changes: true`: skip (will be pushed)
- [ ] Report conflicts in `SyncResult`
- [ ] Tests for both resolution paths

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 6. CLI Sync Command

#### 6.1 Create cli/sync.py
- [ ] Create `src/sltasks/cli/sync.py`
- [ ] Implement `run_sync()`:
  ```python
  def run_sync(
      project_root: Path,
      dry_run: bool = False,
      force: bool = False,
  ) -> int: ...
  ```
- [ ] Workflow:
  1. Load config, validate `github.sync.enabled: true`
  2. Authenticate GitHub client
  3. Initialize sync engine
  4. Call `detect_changes()` and display summary
  5. If `dry_run`: show preview and exit
  6. If conflicts and not `force`: warn user
  7. Execute `sync_from_github()`
  8. Report results
- [ ] Progress output for large syncs
- [ ] CLI tests

**Files:**
- `src/sltasks/cli/sync.py` (new)
- `tests/test_cli_sync.py` (new)

#### 6.2 Update __main__.py
- [ ] Add `sync` subcommand:
  ```python
  sync_parser = subparsers.add_parser("sync", help="Sync with GitHub")
  sync_parser.add_argument("--dry-run", action="store_true")
  sync_parser.add_argument("--force", action="store_true")
  ```
- [ ] Route to `run_sync()` when subcommand is `sync`

**Files:**
- `src/sltasks/__main__.py`

---

### 7. Extend Push Command

#### 7.1 Update cli/push.py for Sync Mode
- [ ] When `sync.enabled: true`, push command should:
  - Also detect and offer to push modified synced files
  - Show separate sections: "New issues" vs "Updated issues"
- [ ] When `sync.enabled: false`, behavior unchanged from Phase 2A
- [ ] Update CLI help text
- [ ] CLI tests for both modes

**Files:**
- `src/sltasks/cli/push.py`
- `tests/test_cli_push.py`

---

### 8. Frontmatter Writing

#### 8.1 Implement Sync Frontmatter Writing
- [ ] Create utility function `write_synced_task_file(task, path)`:
  - Write standard frontmatter fields
  - Write `github:` section with all sync metadata
  - Write `push_changes: false` and `close_on_github: false`
  - Preserve body content
- [ ] Use `frontmatter` library with `sort_keys=False`
- [ ] Ensure atomic writes (temp file + rename)
- [ ] Unit tests for frontmatter formatting

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 9. Tasks.yaml Integration

#### 9.1 Update Ordering for Synced Files
- [ ] When sync creates new files, add to `tasks.yaml`
- [ ] Respect existing `BoardOrder` patterns from filesystem repo
- [ ] When sync removes files, update `tasks.yaml`
- [ ] Integration tests

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 10. Testing

#### 10.1 Unit Tests
- [ ] `test_sync_filter_parser.py` - all filter syntax variations
- [ ] `test_sync_models.py` - SyncResult, ChangeSet, Conflict
- [ ] `test_sync_engine.py` - individual method tests

#### 10.2 Integration Tests
- [ ] Sync pull - create new files from GitHub
- [ ] Sync pull - update existing files
- [ ] Sync pull - handle conflicts
- [ ] Push updates - modify existing issues
- [ ] Push updates - close issues
- [ ] Full round-trip: create local → push → modify on GitHub → sync

#### 10.3 Manual Testing Checklist
- [ ] Configure `sync.enabled: true` with filters
- [ ] Run `sltasks sync --dry-run` - see preview
- [ ] Run `sltasks sync` - files created locally
- [ ] Verify files have correct frontmatter and body
- [ ] Edit local file, set `push_changes: true`
- [ ] Run `sltasks push` - issue updated on GitHub
- [ ] Modify issue on GitHub
- [ ] Run `sltasks sync` - local file updated
- [ ] Create conflict scenario - verify resolution

---

## Acceptance Criteria

- [ ] Filter parser handles all documented syntax
- [ ] `sltasks sync` pulls issues matching configured filters
- [ ] Synced files have complete `github:` metadata section
- [ ] `sltasks sync --dry-run` shows preview without changes
- [ ] `sltasks sync --force` overwrites local changes
- [ ] Modified files with `push_changes: true` are pushed
- [ ] Conflicts detected and resolved per `push_changes` flag
- [ ] `close_on_github: true` closes issues when file deleted
- [ ] All tests pass
- [ ] Round-trip sync works correctly

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
- [ ] None yet

### Key Implementation Insights
- [ ] None yet

### Blockers Encountered
- [ ] None yet

### Open Questions
- [ ] None yet
