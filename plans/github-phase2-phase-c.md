# Phase 2C: TUI Integration & Polish

**Epic:** [github-phase2-epic.md](./github-phase2-epic.md)
**Previous:** [Phase 2B](./github-phase2-phase-b.md)
**Status:** In Progress
**Prerequisites:** Phase 2B complete

## Overview

Phase 2C completes the sync feature with full TUI integration, documentation, and polish. Users can manage sync entirely from the terminal UI, see sync status on task cards, and have a dedicated sync screen for reviewing changes.

**Key deliverables:**
- Sync status indicators on task cards
- Sync management screen (`S` key)
- Push keybinding (`p` key) for local/modified tasks
- Updated `--github-setup` wizard
- User documentation

---

## Tasks

### 1. Sync Status Indicators

#### 1.1 Create Sync Status Widget
- [x] Create sync status indicator component in `src/sltasks/ui/widgets/`
- [x] Implement status display logic:
  ```python
  STATUS_DISPLAY = {
      SyncStatus.SYNCED: ("●", "green"),
      SyncStatus.LOCAL_MODIFIED: ("●", "yellow"),
      SyncStatus.REMOTE_MODIFIED: ("●", "blue"),
      SyncStatus.CONFLICT: ("⚠", "red"),
      SyncStatus.LOCAL_ONLY: ("○", "dim"),
  }
  ```
- [x] Widget should be small and unobtrusive
- [ ] Tooltip/hover text explaining status (deferred)
- [ ] Unit tests for rendering (deferred)

**Files:**
- `src/sltasks/ui/widgets/sync_indicator.py` (new, or inline in task_card.py)
- `tests/test_ui_sync_indicator.py` (new)

#### 1.2 Integrate into TaskCard
- [x] Modify `TaskCard` widget to display sync indicator
- [x] Position: right side of card header or badge area
- [x] Only show when sync is enabled (`config.github.sync.enabled`)
- [x] Pass sync status to card from parent
- [x] Update styles in `ui/styles.tcss`
- [ ] TUI tests (deferred)

**Files:**
- `src/sltasks/ui/widgets/task_card.py`
- `src/sltasks/ui/styles.tcss`
- `tests/test_ui_task_card.py`

#### 1.3 Add Sync Status to Board
- [x] In `app.py` or board service, compute sync statuses for all tasks
- [x] If sync enabled, initialize `GitHubSyncEngine` on app startup
- [x] Pass statuses to task cards during rendering
- [x] Update statuses after refresh (`r` key)
- [ ] TUI tests (deferred)

**Files:**
- `src/sltasks/app.py`
- `tests/test_app.py`

---

### 2. Sync Management Screen

#### 2.1 Create SyncScreen Widget
- [x] Create `src/sltasks/ui/screens/sync_screen.py`
- [x] Screen layout (implemented with sections for Pull, Push, Conflicts)
- [x] Use Static widgets with Rich markup for displaying items
- [x] Section headers with counts
- [x] Conflict details with timestamps

**Files:**
- `src/sltasks/ui/screens/sync_screen.py` (new)
- `tests/test_ui_sync_screen.py` (new - deferred)

#### 2.2 Implement Screen Actions
- [x] Keybindings for sync screen:
  | Key | Action |
  |-----|--------|
  | `P` | Pull all |
  | `U` | Push selected/all |
  | `r` | Refresh status |
  | `ESC` | Close screen |
- [x] Pull action: calls `sync_from_github()`
- [x] Push action: calls `push_new_issues()` and `push_updates()` with selected files
- [x] Refresh: re-compute `detect_changes()`
- [x] Show progress/results after operations via notifications
- [ ] TUI tests for actions (deferred)

**Files:**
- `src/sltasks/ui/screens/sync_screen.py`
- `tests/test_ui_sync_screen.py`

#### 2.3 Wire Up Screen to App
- [x] Add `S` keybinding to open sync screen
- [x] Only enabled when `sync.enabled: true`
- [x] If sync disabled, show notification "Sync not enabled"
- [x] Pass sync engine instance to screen
- [x] Refresh board after screen closes

**Files:**
- `src/sltasks/app.py`
- `tests/test_app.py`

---

### 3. Push Keybinding

#### 3.1 Add `p` Keybinding for Push
- [x] Add `p` keybinding to push current task
- [x] Behavior depends on task state:
  | Task State | Action |
  |------------|--------|
  | `LOCAL_ONLY` | Push as new issue |
  | `LOCAL_MODIFIED` | Push updates (if sync enabled) |
  | `SYNCED` | No-op, show "Already synced" |
  | `CONFLICT` | Warn to use sync screen |
  | `REMOTE_MODIFIED` | Warn to refresh first |
- [x] After push:
  - For new issues: prompt delete/archive (via PushConfirmModal)
  - For updates: show success notification
- [x] If sync disabled: shows warning notification
- [ ] TUI tests (deferred)

**Files:**
- `src/sltasks/app.py`
- `tests/test_app.py`

#### 3.2 Push Confirmation Dialog
- [x] Show confirmation before push (PushConfirmModal)
- [x] Shows task title, target repository, and status
- [x] Post-push action options: Keep, Delete, Archive local file
- [x] Implemented as ModalScreen with RadioSet

**Files:**
- `src/sltasks/ui/widgets/push_confirm_modal.py` (new)
- `tests/test_ui_push_dialog.py` (new - deferred)

---

### 4. GitHub Setup Wizard Updates

#### 4.1 Add Sync Configuration to Setup
- [x] Extend `--github-setup` wizard to configure sync
- [x] Prompt for enabling sync after repository selection
- [x] Prompt for common filters (assignee:@me)
- [x] Support custom filter input
- [x] Save sync config to `sltasks.yml` under `github.sync`
- [ ] Update existing setup tests (deferred)

**Files:**
- `src/sltasks/cli/github_setup.py`
- `tests/test_cli_github_setup.py`

---

### 5. Error Handling & Edge Cases

#### 5.1 Network Error Handling
- [ ] Graceful handling of network errors during sync
- [ ] Retry logic with exponential backoff
- [ ] Clear error messages:
  ```
  Error: Network error during sync
    Could not connect to GitHub. Check your internet connection.
    Partial sync completed: 3 of 10 issues synced.
  ```
- [ ] Resume capability after partial failure
- [ ] Tests for error scenarios

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

#### 5.2 Edge Cases
- [ ] Handle deleted GitHub issues:
  - If issue deleted on GitHub, mark local file with warning
  - Option to delete local file or keep as orphan
- [ ] Handle renamed repositories:
  - Detect repository rename
  - Update file names and metadata
- [ ] Handle file permission errors:
  - Skip unwritable files
  - Report in results
- [ ] Handle large issue bodies:
  - No truncation, preserve full content
- [ ] Tests for each edge case

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

#### 5.3 Improve Error Messages
- [ ] Review all error messages in sync module
- [ ] Ensure actionable guidance:
  ```
  Error: Sync filter invalid
    Filter "assignee:" is missing a value.
    Example: assignee:@me or assignee:octocat

  Error: Cannot sync - default_repo not configured
    Add 'default_repo: owner/repo' to github section of sltasks.yml
    Run 'sltasks --github-setup' to reconfigure.
  ```
- [ ] Consistent error formatting with `cli/output.py`

**Files:**
- `src/sltasks/sync/engine.py`
- `src/sltasks/sync/filter_parser.py`
- `src/sltasks/cli/sync.py`
- `src/sltasks/cli/push.py`

---

### 6. Performance Optimization

#### 6.1 Optimize for Large Projects
- [ ] Implement caching for sync status computation
- [ ] Lazy loading of sync statuses (don't block UI)
- [ ] Batch file operations where possible
- [ ] Progress indicator for large syncs
- [ ] Profile and optimize hot paths
- [ ] Load tests with 100+ issues

**Files:**
- `src/sltasks/sync/engine.py`
- `src/sltasks/app.py`

#### 6.2 Incremental Sync
- [ ] Track last sync timestamp globally
- [ ] Use GitHub's `updatedAt` filtering where possible
- [ ] Only fetch issues updated since last sync
- [ ] Integration tests for incremental sync

**Files:**
- `src/sltasks/sync/engine.py`
- `tests/test_sync_engine.py`

---

### 7. Documentation

#### 7.1 Update User Documentation
- [ ] Add sync documentation to user guide (deferred - future phase)
  - Configuration options
  - Filter syntax reference
  - CLI command usage
  - TUI keybindings
  - Conflict resolution guide
  - Troubleshooting section

**Files:**
- `docs/` (documentation files)

#### 7.2 Update CLAUDE.md
- [x] Add sync feature to project overview (GitHub Sync section)
- [x] Document new files and patterns (key files listed)
- [x] Update keybinding reference (S, p added)
- [x] Document synced file format

**Files:**
- `CLAUDE.md`

#### 7.3 Update Help Text
- [ ] Update `--help` output for CLI commands (deferred)
- [x] Update TUI help screen (`?` key) with sync keybindings
- [x] Added "GitHub Sync" section with S and p keybindings

**Files:**
- `src/sltasks/__main__.py`
- `src/sltasks/ui/screens/help.py`

---

### 8. Testing

#### 8.1 TUI Tests
- [ ] `test_ui_sync_indicator.py` - indicator rendering
- [ ] `test_ui_sync_screen.py` - screen layout and actions
- [ ] `test_ui_push_dialog.py` - push confirmation dialog
- [ ] `test_app.py` - keybindings integration

#### 8.2 Integration Tests
- [ ] Full workflow: configure → sync → edit → push
- [ ] Error recovery scenarios
- [ ] Performance with large datasets

#### 8.3 Manual Testing Checklist
- [ ] Enable sync in config
- [ ] Launch TUI - see sync indicators on cards
- [ ] Press `S` - open sync screen
- [ ] Review changes in sync screen
- [ ] Pull changes from GitHub via screen
- [ ] Push local changes via screen
- [ ] Press `p` on local-only task - push single task
- [ ] Press `p` on modified task - push updates
- [ ] Test with network disconnected
- [ ] Test with large project (50+ issues)

---

## Acceptance Criteria

- [x] Sync status indicators visible on task cards
- [x] `S` keybinding opens sync management screen
- [x] Sync screen shows pull/push/conflict sections
- [x] Can pull and push from sync screen
- [x] `p` keybinding pushes current task
- [x] Push confirmation dialog works correctly
- [x] `--github-setup` wizard configures sync
- [ ] Error messages are clear and actionable (basic implementation done)
- [ ] Performance acceptable with 100+ issues (not tested yet)
- [ ] User documentation complete (CLAUDE.md done, docs/ deferred)
- [x] All tests pass (490 tests passing)

---

## Files Created/Modified

### New Files
| File | Purpose |
|------|---------|
| `src/sltasks/ui/screens/sync_screen.py` | Sync management screen |
| `src/sltasks/ui/widgets/sync_indicator.py` | Status indicator widget (or inline) |
| `tests/test_ui_sync_screen.py` | Sync screen tests |
| `tests/test_ui_sync_indicator.py` | Indicator tests |
| `tests/test_ui_push_dialog.py` | Push dialog tests |

### Modified Files
| File | Changes |
|------|---------|
| `src/sltasks/app.py` | Add `S`, `p` keybindings, sync engine init |
| `src/sltasks/ui/widgets/task_card.py` | Add sync indicator |
| `src/sltasks/ui/styles.tcss` | Sync indicator styles |
| `src/sltasks/cli/github_setup.py` | Add sync configuration |
| `src/sltasks/sync/engine.py` | Error handling, performance |
| `CLAUDE.md` | Document sync feature |
| `docs/` | User documentation |

---

## Dependencies

- Phase 2B must be complete
- No external dependencies to add

---

## Deviations & Insights

_Updated during implementation_

### Deviations from Plan
- Sync indicator implemented inline in task_card.py rather than separate widget
- SyncScreen uses Static widgets with Rich markup instead of DataTable
- Checkbox toggle selection not implemented in SyncScreen (push all approach)
- TUI tests deferred to keep implementation focused

### Key Implementation Insights
- Rich markup `[{color}]{symbol}[/]` pattern works well for sync indicators
- ModalScreen pattern with callbacks is clean for push confirmation
- Lazy sync status computation works well on app mount and refresh
- Using `call_after_refresh()` for board refresh after sync screen closes

### Blockers Encountered
- None

### Open Questions
- Performance with large projects (100+ issues) - needs manual testing
- Whether Space toggle selection is needed in SyncScreen

---

## Phase Completion Checklist

Before marking Phase 2C complete:

- [ ] All acceptance criteria met
- [ ] All tests passing
- [ ] Code reviewed
- [ ] Documentation updated
- [ ] Manual testing completed
- [ ] Performance verified
- [ ] Deviations documented above

---

## Post-Implementation Review

_Fill out after phase completion_

### What Went Well
- [ ] TBD

### What Could Be Improved
- [ ] TBD

### Technical Debt Created
- [ ] TBD

### Recommendations for Future Work
- [ ] TBD
