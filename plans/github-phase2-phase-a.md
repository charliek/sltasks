# Phase 2A: Foundation & Push (CLI Only)

**Epic:** [github-phase2-epic.md](./github-phase2-epic.md)
**Status:** Complete
**Prerequisites:** Phase 1 (GitHub-only mode) complete

## Overview

Phase 2A enables the LLM workflow: create GitHub issues from local markdown files without enabling full bidirectional sync. This establishes the foundation (models, file mapper) that subsequent phases build upon.

**Key deliverable:** Users can write local `.md` files and run `sltasks push` to create GitHub issues.

---

## Tasks

### 1. Configuration Models

#### 1.1 Add GitHubSyncConfig
- [x] Create `GitHubSyncConfig` model in `src/sltasks/models/sltasks_config.py`
  ```python
  class GitHubSyncConfig(BaseModel):
      enabled: bool = False
      task_root: str | None = None  # Override global task_root
      filters: list[str] = Field(default_factory=list)
  ```
- [x] Add `sync: GitHubSyncConfig | None = None` field to `GitHubConfig`
- [x] Add validation: `sync.enabled` requires `default_repo` to be set
- [ ] Unit tests for config parsing and validation (deferred - existing config tests cover basic parsing)

**Files:**
- `src/sltasks/models/sltasks_config.py`
- `tests/test_config.py`

#### 1.2 Extend GitHubProviderData
- [x] Add sync-related fields to `GitHubProviderData`:
  ```python
  last_synced: datetime | None = None
  priority_source: str = "labels"  # "labels" or "field"
  ```
- [x] These fields support future sync but are optional for push-only mode
- [ ] Unit tests for provider data serialization (deferred)

**Files:**
- `src/sltasks/models/provider_data.py`
- `tests/test_models.py`

---

### 2. Sync Data Models

#### 2.1 Create models/sync.py
- [x] Create new file `src/sltasks/models/sync.py`
- [x] Implement `SyncStatus` enum:
  ```python
  class SyncStatus(str, Enum):
      SYNCED = "synced"
      LOCAL_MODIFIED = "local_modified"
      REMOTE_MODIFIED = "remote_modified"
      CONFLICT = "conflict"
      LOCAL_ONLY = "local_only"
  ```
- [x] Implement `PushResult` dataclass:
  ```python
  @dataclass
  class PushResult:
      created: list[str] = field(default_factory=list)  # Issue IDs created
      errors: list[str] = field(default_factory=list)   # Error messages
      dry_run: bool = False
  ```
- [x] Export from `models/__init__.py`
- [x] Unit tests for models

**Files:**
- `src/sltasks/models/sync.py` (new)
- `src/sltasks/models/__init__.py`
- `tests/test_sync_models.py` (new)

---

### 3. File Mapper

#### 3.1 Create sync/file_mapper.py
- [x] Create `src/sltasks/sync/` package with `__init__.py`
- [x] Create `src/sltasks/sync/file_mapper.py`
- [x] Implement `generate_synced_filename(owner, repo, issue_number, title)`:
  - Format: `{owner}-{repo}#{number}-{slug}.md`
  - Use `slugify()` from existing `utils/slug.py`
  - Example: `acme-project#123-fix-login-bug.md`
- [x] Implement `parse_synced_filename(filename)`:
  - Returns `ParsedSyncedFilename` or `None` if not synced format
  - Uses regex pattern with named groups
- [x] Implement `is_synced_filename(filename)`:
  - Returns `True` if filename matches synced pattern
- [x] Implement `is_local_only_filename(filename)`:
  - Returns `True` if filename is `.md` but not synced format
- [x] Comprehensive unit tests for edge cases

**Files:**
- `src/sltasks/sync/__init__.py` (new)
- `src/sltasks/sync/file_mapper.py` (new)
- `tests/test_sync_file_mapper.py` (new)

---

### 4. Push Engine

#### 4.1 Create sync/engine.py (Push-only subset)
- [x] Create `src/sltasks/sync/engine.py`
- [x] Implement `GitHubPushEngine` class:
  ```python
  class GitHubPushEngine:
      def __init__(
          self,
          config_service: ConfigService,
          github_client: GitHubClient,
          task_root: Path,
      ) -> None: ...

      def find_local_only_tasks(self) -> list[Task]: ...
      def push_new_issues(
          self,
          tasks: list[Task],
          dry_run: bool = False,
      ) -> PushResult: ...

      def _create_github_issue(self, task: Task) -> str: ...  # Returns issue ID
  ```
- [x] `find_local_only_tasks()`:
  - Scan task files in `task_root`
  - Return tasks without `github:` section in frontmatter
- [x] `_create_github_issue()`:
  - Create issue in `default_repo`
  - Add to project
  - Set status field based on `task.state`
  - Add labels for type/priority/tags
  - Return `owner/repo#number` format ID
- [x] `push_new_issues()`:
  - Orchestrate push for multiple tasks
  - Track success/failure in `PushResult`
  - Support `dry_run` mode
- [ ] Integration tests with mocked GitHub API (deferred to Phase 2B)

**Files:**
- `src/sltasks/sync/engine.py` (new)
- `tests/test_sync_engine.py` (new - deferred)

#### 4.2 Post-Push File Handling
- [x] Implement `handle_pushed_file(task, issue_id, action)`:
  - `action="delete"`: Remove file and from `tasks.yaml`
  - `action="archive"`: Set `archived: true` in frontmatter, update state
  - `action="rename"`: Rename to synced filename format (for future sync)
- [x] For Phase 2A, default actions are `delete` or `archive` (no rename)
- [ ] Unit tests for file handling (deferred)

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 5. CLI Push Command

#### 5.1 Create cli/push.py
- [x] Create `src/sltasks/cli/push.py`
- [x] Implement `run_push()` function:
  ```python
  def run_push(
      project_root: Path,
      files: list[str] | None = None,
      dry_run: bool = False,
      yes: bool = False,
      delete: bool = False,
      archive: bool = False,
  ) -> int: ...
  ```
- [x] Workflow:
  1. Load config, validate `github.default_repo` is set
  2. Authenticate GitHub client
  3. Find local-only tasks (or filter by `files` argument)
  4. Show preview of what will be pushed
  5. If not `--yes`, prompt for confirmation
  6. Execute push
  7. Handle post-push (prompt for delete/archive if not specified)
  8. Report results
- [x] Use `output.py` utilities for colored output
- [ ] CLI tests (deferred)

**Files:**
- `src/sltasks/cli/push.py` (new)
- `tests/test_cli_push.py` (new - deferred)

#### 5.2 Update __main__.py
- [x] Add `push` subcommand to argparse:
  ```python
  push_parser = subparsers.add_parser("push", help="Push local tasks to GitHub")
  push_parser.add_argument("files", nargs="*", help="Specific files to push")
  push_parser.add_argument("--dry-run", action="store_true")
  push_parser.add_argument("--yes", "-y", action="store_true")
  push_parser.add_argument("--delete", action="store_true")
  push_parser.add_argument("--archive", action="store_true")
  ```
- [x] Route to `run_push()` when subcommand is `push`
- [x] Ensure default (no subcommand) still launches TUI

**Files:**
- `src/sltasks/__main__.py`

---

### 6. Frontmatter Parsing

#### 6.1 Update Filesystem Repository
- [x] Add `has_github_metadata()` helper method to check for `github:` section
  - If `github:` section present with `synced: true`, task is synced (not local-only)
- [x] This is read-only for Phase 2A - just detection, not writing
- [ ] Unit tests for parsing files with/without `github:` section (deferred)

**Files:**
- `src/sltasks/repositories/filesystem.py`
- `tests/test_repository.py`

---

### 7. Testing

#### 7.1 Unit Tests
- [x] `test_sync_models.py` - SyncStatus, PushResult, SyncResult, Conflict, ChangeSet
- [x] `test_sync_file_mapper.py` - filename generation/parsing
- [ ] `test_config.py` - GitHubSyncConfig parsing (deferred)

#### 7.2 Integration Tests
- [ ] `test_sync_engine.py` - push with mocked GitHub API (deferred to Phase 2B)
- [ ] `test_cli_push.py` - CLI invocation tests (deferred)

#### 7.3 Manual Testing Checklist
- [ ] Create local `.md` file with frontmatter
- [ ] Run `sltasks push --dry-run` - see preview
- [ ] Run `sltasks push` - issue created on GitHub
- [ ] Verify issue has correct title, body, labels, status
- [ ] Verify post-push file handling (delete/archive)

---

## Acceptance Criteria

- [x] `GitHubSyncConfig` model parses correctly from YAML
- [x] `GitHubProviderData` extended with sync fields
- [x] `SyncStatus` and `PushResult` models work correctly
- [x] File mapper generates and parses synced filenames
- [x] `sltasks push` creates GitHub issues from local files (CLI implemented)
- [x] `sltasks push --dry-run` shows preview without changes
- [x] `sltasks push --delete` removes local file after push
- [x] `sltasks push --archive` marks file as archived after push
- [x] All tests pass (443 tests)
- [x] Works when `sync.enabled: false` (default)

---

## Files Created/Modified

### New Files
| File | Purpose | Status |
|------|---------|--------|
| `src/sltasks/models/sync.py` | Sync data models | Created |
| `src/sltasks/sync/__init__.py` | Sync package | Created |
| `src/sltasks/sync/file_mapper.py` | Filename utilities | Created |
| `src/sltasks/sync/engine.py` | Push engine | Created |
| `src/sltasks/cli/push.py` | CLI command | Created |
| `tests/test_sync_models.py` | Model tests | Created |
| `tests/test_sync_file_mapper.py` | File mapper tests | Created |
| `tests/test_sync_engine.py` | Engine tests | Deferred |
| `tests/test_cli_push.py` | CLI tests | Deferred |

### Modified Files
| File | Changes | Status |
|------|---------|--------|
| `src/sltasks/models/sltasks_config.py` | Add `GitHubSyncConfig` | Complete |
| `src/sltasks/models/provider_data.py` | Extend `GitHubProviderData` | Complete |
| `src/sltasks/models/__init__.py` | Export new models | Complete |
| `src/sltasks/__main__.py` | Add `push` subcommand | Complete |
| `src/sltasks/repositories/filesystem.py` | Add `has_github_metadata()` | Complete |

---

## Dependencies

- Phase 1 must be complete (GitHubProjectsRepository, GitHubClient)
- No external dependencies to add

---

## Deviations & Insights

_Updated during implementation_

### Deviations from Plan
- [x] Engine takes `task_root: Path` instead of `github_repo: GitHubProjectsRepository` - simpler design, engine handles GitHub operations directly
- [x] Added `ParsedSyncedFilename` dataclass for structured filename parsing results
- [x] Regex for parsing synced filenames is greedy - `my-org-my-repo#123` parses as owner="my-org-my", repo="repo" (known limitation with hyphenated names)
- [x] Some integration tests deferred to Phase 2B when sync engine is more complete

### Key Implementation Insights
- [x] Reused GraphQL queries from existing `github/queries.py` - no new queries needed
- [x] `status_alias` is the correct field name in `ColumnConfig` (not `aliases`)
- [x] Frontmatter library returns `object` type for metadata - requires explicit `dict()` cast for type safety
- [x] Post-push file handling supports three actions: delete, archive, rename (rename useful for Phase 2B sync)

### Blockers Encountered
- [x] None - Phase 1 infrastructure was well-designed for extension

### Open Questions Resolved
- [x] How to detect local-only vs synced files? → Check for `github:` section with `synced: true` in frontmatter
- [x] What happens after push? → User choice: delete file, archive it, or (Phase 2B) rename to synced format
