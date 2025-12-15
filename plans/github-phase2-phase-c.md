# Phase 2C: TUI Integration & Polish

**Epic:** [github-phase2-epic.md](./github-phase2-epic.md)
**Previous:** [Phase 2B](./github-phase2-phase-b.md)
**Status:** Not Started
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
- [ ] Create sync status indicator component in `src/sltasks/ui/widgets/`
- [ ] Implement status display logic:
  ```python
  STATUS_DISPLAY = {
      SyncStatus.SYNCED: ("●", "green"),
      SyncStatus.LOCAL_MODIFIED: ("●", "yellow"),
      SyncStatus.REMOTE_MODIFIED: ("●", "blue"),
      SyncStatus.CONFLICT: ("⚠", "red"),
      SyncStatus.LOCAL_ONLY: ("○", "dim"),
  }
  ```
- [ ] Widget should be small and unobtrusive
- [ ] Tooltip/hover text explaining status
- [ ] Unit tests for rendering

**Files:**
- `src/sltasks/ui/widgets/sync_indicator.py` (new, or inline in task_card.py)
- `tests/test_ui_sync_indicator.py` (new)

#### 1.2 Integrate into TaskCard
- [ ] Modify `TaskCard` widget to display sync indicator
- [ ] Position: right side of card header or badge area
- [ ] Only show when sync is enabled (`config.github.sync.enabled`)
- [ ] Pass sync status to card from parent
- [ ] Update styles in `ui/styles.tcss`
- [ ] TUI tests

**Files:**
- `src/sltasks/ui/widgets/task_card.py`
- `src/sltasks/ui/styles.tcss`
- `tests/test_ui_task_card.py`

#### 1.3 Add Sync Status to Board
- [ ] In `app.py` or board service, compute sync statuses for all tasks
- [ ] If sync enabled, initialize `GitHubSyncEngine` on app startup
- [ ] Pass statuses to task cards during rendering
- [ ] Update statuses after refresh (`r` key)
- [ ] TUI tests

**Files:**
- `src/sltasks/app.py`
- `tests/test_app.py`

---

### 2. Sync Management Screen

#### 2.1 Create SyncScreen Widget
- [ ] Create `src/sltasks/ui/screens/sync_screen.py`
- [ ] Screen layout:
  ```
  ┌─────────────────────────────────────────────────────────────┐
  │ Sync Status                                          [ESC] │
  ├─────────────────────────────────────────────────────────────┤
  │ Pull from GitHub (3 changes):                               │
  │   [ ] owner/repo#123 - Fix login bug         [remote mod]  │
  │   [ ] owner/repo#124 - Update docs           [new]         │
  │   [ ] owner/repo#125 - Refactor auth         [new]         │
  │                                                             │
  │ Push to GitHub (2 changes):                                 │
  │   [x] add-feature.md - Add dark mode         [local only]  │
  │   [ ] owner-repo#100-fix-typo.md             [local mod]   │
  │                                                             │
  │ Conflicts (1):                                              │
  │   [ ] owner-repo#99-update-readme.md                       │
  │       Local: 2025-01-15 10:30  GitHub: 2025-01-15 11:00    │
  │       [GitHub will win - set push_changes: true to push]   │
  ├─────────────────────────────────────────────────────────────┤
  │ [Space] Toggle  [P] Pull  [U] Push  [r] Refresh  [ESC] Close│
  └─────────────────────────────────────────────────────────────┘
  ```
- [ ] Use Textual `DataTable` or custom list for change items
- [ ] Checkbox selection for push operations
- [ ] Section headers with counts
- [ ] Conflict details with timestamps

**Files:**
- `src/sltasks/ui/screens/sync_screen.py` (new)
- `tests/test_ui_sync_screen.py` (new)

#### 2.2 Implement Screen Actions
- [ ] Keybindings for sync screen:
  | Key | Action |
  |-----|--------|
  | `Space` | Toggle selection |
  | `P` | Pull all / Pull selected |
  | `U` | Push selected |
  | `r` | Refresh status |
  | `ESC` | Close screen |
- [ ] Pull action: calls `sync_from_github()`
- [ ] Push action: calls `push_to_github()` with selected files
- [ ] Refresh: re-compute `detect_changes()`
- [ ] Show progress/results after operations
- [ ] TUI tests for actions

**Files:**
- `src/sltasks/ui/screens/sync_screen.py`
- `tests/test_ui_sync_screen.py`

#### 2.3 Wire Up Screen to App
- [ ] Add `S` keybinding to open sync screen
- [ ] Only enabled when `sync.enabled: true`
- [ ] If sync disabled, show notification "Sync not enabled"
- [ ] Pass sync engine instance to screen
- [ ] Refresh board after screen closes

**Files:**
- `src/sltasks/app.py`
- `tests/test_app.py`

---

### 3. Push Keybinding

#### 3.1 Add `p` Keybinding for Push
- [ ] Add `p` keybinding to push current task
- [ ] Behavior depends on task state:
  | Task State | Action |
  |------------|--------|
  | `LOCAL_ONLY` | Push as new issue |
  | `LOCAL_MODIFIED` | Push updates (if sync enabled) |
  | `SYNCED` | No-op, show "Already synced" |
  | Other | No-op |
- [ ] After push:
  - For new issues: prompt delete/archive
  - For updates: show success notification
- [ ] If sync disabled: only works for `LOCAL_ONLY`
- [ ] TUI tests

**Files:**
- `src/sltasks/app.py`
- `tests/test_app.py`

#### 3.2 Push Confirmation Dialog
- [ ] Show confirmation before push:
  ```
  Push to GitHub?

  Title: Add dark mode support
  Repository: owner/repo
  Status: backlog

  [Enter] Confirm  [ESC] Cancel
  ```
- [ ] For new issues: show target repo
- [ ] For updates: show what changed
- [ ] Implement as modal dialog

**Files:**
- `src/sltasks/ui/screens/` or `src/sltasks/ui/modals/`
- `tests/test_ui_push_dialog.py` (new)

---

### 4. GitHub Setup Wizard Updates

#### 4.1 Add Sync Configuration to Setup
- [ ] Extend `--github-setup` wizard to configure sync:
  ```
  === Filesystem Sync Configuration ===

  Would you like to enable filesystem sync? [y/N]

  Sync allows you to:
  - Cache GitHub issues as local markdown files
  - Create issues from local files
  - Edit issues offline and push changes

  Enable sync? [y/N]: y

  Configure sync filters (issues matching ANY filter will sync):

  Sync issues assigned to you? [Y/n]: y
  > Added filter: assignee:@me

  Add custom filter? (e.g., "label:urgent") [empty to skip]:
  > label:urgent
  > Added filter: label:urgent

  Add another filter? [y/N]: n
  ```
- [ ] Save sync config to `sltasks.yml`
- [ ] Update existing setup tests

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
- [ ] Add sync documentation to user guide:
  - Configuration options
  - Filter syntax reference
  - CLI command usage
  - TUI keybindings
  - Conflict resolution guide
  - Troubleshooting section
- [ ] Include examples and screenshots

**Files:**
- `docs/` (documentation files)

#### 7.2 Update CLAUDE.md
- [ ] Add sync feature to project overview
- [ ] Document new files and patterns
- [ ] Update keybinding reference
- [ ] Add sync testing guidance

**Files:**
- `CLAUDE.md`

#### 7.3 Update Help Text
- [ ] Update `--help` output for CLI commands
- [ ] Update TUI help screen (`?` key) with sync keybindings
- [ ] Ensure help is accurate and complete

**Files:**
- `src/sltasks/__main__.py`
- `src/sltasks/ui/screens/help_screen.py` (if exists)

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

- [ ] Sync status indicators visible on task cards
- [ ] `S` keybinding opens sync management screen
- [ ] Sync screen shows pull/push/conflict sections
- [ ] Can pull and push from sync screen
- [ ] `p` keybinding pushes current task
- [ ] Push confirmation dialog works correctly
- [ ] `--github-setup` wizard configures sync
- [ ] Error messages are clear and actionable
- [ ] Performance acceptable with 100+ issues
- [ ] User documentation complete
- [ ] All tests pass

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
- [ ] None yet

### Key Implementation Insights
- [ ] None yet

### Blockers Encountered
- [ ] None yet

### Open Questions
- [ ] None yet

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
