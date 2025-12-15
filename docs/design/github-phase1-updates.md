# GitHub Projects Integration - Phase 1 Updates

## Overview

This document outlines updated requirements for the GitHub Projects integration, building on the existing Phase 1 implementation. The focus is on improving the developer experience by auto-detecting project configuration from GitHub and reducing manual mapping requirements.

**Key Principle**: GitHub is the source of truth. The TUI mirrors what GitHub provides, with optional display customizations.

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Column source | GitHub Status field only | Eliminates sync drift; 1:1 mapping required |
| Column overrides | Display only (title, color) | Users can customize appearance without breaking mapping |
| Priority detection | Auto-detect project field | Check "Priority", "Severity", "Urgency" (case-insensitive); fall back to labels |
| Type mapping | Explicit label mapping | No native GitHub field; requires 1:1 config when used |
| Tags | Labels minus reserved | Automatic; optionally curate "featured" labels |
| Config generation | `--github-setup` command | Interactive setup writes sane defaults from project metadata |

---

## Requirements

### 1. Columns / State

**Current Behavior**: Users must manually define `board.columns` and optionally provide `github.column_mapping` to link sltasks columns to GitHub Status options.

**Updated Behavior**:
- On startup, fetch the project's Status field and its options via GraphQL.
- Auto-generate the internal column list from Status options (preserving GitHub's order).
- `board.columns` becomes optional and **display-only**:
  - If present, each entry must match a GitHub Status option ID (slugified).
  - Allowed overrides: `title`, `color`, `icon`.
  - Unknown column IDs trigger an error with guidance to run `--github-setup`.
- Remove `github.column_mapping` entirely; it's no longer needed.

**Validation**:
- If `board.columns` contains an ID not matching any GitHub Status option, fail on startup with:
  ```
  Error: Column 'review' not found in GitHub project.
  Available columns: backlog, ready, in_progress, in_review, done
  Run 'sltasks --github-setup' to regenerate configuration.
  ```

**Example Config (columns section)**:
```yaml
board:
  columns:
    # Only display overrides; IDs must match GitHub Status options
    - id: backlog
      title: "Backlog"
      color: gray
    - id: ready
      title: "Ready to Start"  # Custom display title
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
```

### 2. Priority

**Current Behavior**: Priority is extracted from issue labels using `board.priorities` with `priority_alias` for matching.

**Updated Behavior**:
- Priority source is determined during `--github-setup` and written to config.
- `--github-setup` checks for single-select project fields named (case-insensitive):
  1. "Priority"
  2. "Severity"
  3. "Urgency"
- If a field is found, the user selects it and it's written to `github.priority_field`.
- If no field is found (or user declines), priority falls back to label-based mapping via `github_label`.

**Startup Behavior**:
- If `github.priority_field` is set:
  - Validate the field exists in the project.
  - If not found, error with guidance to run `--github-setup`:
    ```
    Error: Priority field 'Priority' not found in GitHub project.
    Available single-select fields: Status, Size
    Run 'sltasks --github-setup' to reconfigure.
    ```
  - Cache field ID and option IDs for read/write operations.
- If `github.priority_field` is not set:
  - Use label-based priority via `board.priorities` with `github_label`.

**New Field**: `github_label` on `PriorityConfig` (for label fallback)
```yaml
board:
  priorities:
    - id: low
      label: "Low"
      color: green
      github_label: "priority:low"  # Used when no project field configured
    - id: medium
      label: "Medium"
      color: yellow
      github_label: "priority:medium"
    - id: high
      label: "High"
      color: orange
      github_label: "priority:high"
    - id: critical
      label: "Critical"
      color: red
      github_label: "priority:critical"
```

**Behavior Notes**:
- When `github.priority_field` is set, priorities are read/written via the project field; `github_label` is ignored.
- When `github.priority_field` is not set, `github_label` defines the exact label string to search for and apply.
- `--github-setup` maps detected field options to `board.priorities` entries (matching by name or alias).

### 3. Type

**Current Behavior**: Type is extracted from issue labels using `board.types` with `type_alias` for matching multiple labels to one type.

**Updated Behavior**:
- Type remains label-based (no native GitHub Projects field).
- Add `github_label` field to `TypeConfig` for explicit 1:1 mapping.
- If `github_label` is not specified for any type, type detection/syncing is skipped entirely.
- When creating/editing tasks, apply the `github_label` and remove other type labels.

**New Field**: `github_label` on `TypeConfig`
```yaml
board:
  types:
    - id: feature
      color: blue
      github_label: "type:feature"  # Exact label to match/apply
    - id: bug
      color: red
      github_label: "type:bug"
    - id: task
      color: white
      github_label: "type:task"
```

**Behavior Notes**:
- `type_alias` continues to work for reading (maps multiple labels to one type).
- `github_label` is the canonical label written back to GitHub.
- If no types have `github_label` defined, type editing is disabled in the TUI.

### 4. Tags

**Current Behavior**: All labels except those matching type/priority are treated as tags.

**Updated Behavior**:
- Same base behavior: labels minus reserved ones become tags.
- Add optional `featured_labels` list in config to highlight commonly used labels in the TUI for quick assignment.

**Example Config**:
```yaml
github:
  featured_labels:
    - "needs-design"
    - "good-first-issue"
    - "documentation"
```

### 5. Size / Supplementary Fields

**Current Behavior**: Not supported.

**Updated Behavior**:
- Auto-detect "Size" (or "Estimate", "Story Points") single-select field.
- Display read-only in task preview/detail view.
- No editing support in Phase 1 updates.

### 6. `--github-setup` Command

**Purpose**: Interactive command to generate or update `sltasks.yml` based on a GitHub project's actual configuration.

**Flow**:
1. Prompt for project URL (or accept as argument).
2. Authenticate using existing token discovery (`GITHUB_TOKEN` or `gh auth token`).
3. Fetch project metadata via GraphQL:
   - Project title, ID
   - Status field options
   - Priority/Severity/Urgency field (if exists)
   - Size/Estimate field (if exists)
   - Sample of existing labels from issues
4. Prompt for default Status option (for new issue creation).
5. Generate proposed `sltasks.yml`:
   - `provider: github`
   - `github` block with project URL, default repo, detected fields
   - `board.columns` with all Status options (IDs slugified, titles preserved)
   - `board.priorities` if Priority field detected (options mapped to priority definitions)
   - `board.types` with common type labels if detected (commented out as suggestions)
6. Display preview of generated config.
7. Prompt to write to file:
   - If file exists, show diff and require confirmation.
   - Offer "print only" option to skip file write.

**Example Output**:
```
Detected GitHub Project: sltasks
Project URL: https://github.com/users/charliek/projects/2

Status columns (5):
  - Backlog
  - Ready
  - In progress
  - In review
  - Done

Priority fields detected:
  1. Priority (P0, P1, P2)
  2. (none - use labels instead)
Select [1-2]: 1

Size field found: Size (XS, S, M, L, XL) [read-only]

Default status for new issues:
  1. Backlog
  2. Ready
  3. In progress
  4. In review
  5. Done
Select [1-5]: 1

Generated configuration:
---
version: 1
provider: github

github:
  project_url: "https://github.com/users/charliek/projects/2"
  default_repo: "charliek/sltasks"
  default_status: backlog
  priority_field: "Priority"

board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: ready
      title: "Ready"
    - id: in_progress
      title: "In progress"
    - id: in_review
      title: "In review"
    - id: done
      title: "Done"

  priorities:
    - id: p0
      label: "P0"
      color: red
    - id: p1
      label: "P1"
      color: orange
    - id: p2
      label: "P2"
      color: yellow

  # Uncomment and customize type labels if needed:
  # types:
  #   - id: bug
  #     github_label: "bug"
  #     color: red
  #   - id: feature
  #     github_label: "enhancement"
  #     color: blue
---

Write to sltasks.yml? [y/N/print]:
```

---

## Configuration Schema Changes

### New Fields

| Model | Field | Type | Description |
|-------|-------|------|-------------|
| `TypeConfig` | `github_label` | `str \| None` | Exact GitHub label for this type |
| `PriorityConfig` | `github_label` | `str \| None` | Exact GitHub label for this priority (used when no project field) |
| `GitHubConfig` | `default_status` | `str \| None` | Status option ID for new issues |
| `GitHubConfig` | `featured_labels` | `list[str]` | Labels to highlight in TUI |
| `GitHubConfig` | `priority_field` | `str \| None` | Name of project field to use for priority (e.g., "Priority", "Severity"); if unset, uses labels |

### Removed Fields

| Model | Field | Reason |
|-------|-------|--------|
| `GitHubConfig` | `column_mapping` | No longer needed; 1:1 mapping is automatic |

### Full Example Config

```yaml
version: 1
provider: github

github:
  project_url: "https://github.com/users/charliek/projects/2"
  default_repo: "charliek/sltasks"
  default_status: backlog
  priority_field: "Priority"  # Use project field; omit to use labels instead
  featured_labels:
    - "needs-design"
    - "blocked"

board:
  columns:
    # Display overrides only; IDs auto-detected from GitHub
    - id: backlog
      title: "Backlog"
      color: gray
    - id: ready
      title: "Ready"
      color: blue
    - id: in_progress
      title: "Working"  # Custom display name
      color: yellow
    - id: in_review
      title: "Review"
      color: orange
    - id: done
      title: "Complete"
      color: green

  types:
    - id: feature
      color: blue
      github_label: "type:feature"
    - id: bug
      color: red
      github_label: "type:bug"
    - id: task
      color: white
      github_label: "type:task"

  priorities:
    # When github.priority_field is set, these map to project field options
    # When github.priority_field is unset, github_label is used for label-based priority
    - id: p0
      label: "P0"
      color: red
      github_label: "priority:p0"  # Only used if priority_field is unset
    - id: p1
      label: "P1"
      color: orange
      github_label: "priority:p1"
    - id: p2
      label: "P2"
      color: yellow
      github_label: "priority:p2"
```

---

## Behavioral Changes Summary

| Area | Current | Updated |
|------|---------|---------|
| Column definition | Manual `board.columns` required | Auto-detected from GitHub; `board.columns` optional for display overrides |
| Column mapping | `github.column_mapping` required | Removed; 1:1 mapping is implicit |
| Priority source | Labels only | Project field (Priority/Severity/Urgency) preferred; labels as fallback |
| Type source | Labels with `type_alias` | Labels with explicit `github_label` for write-back |
| Config generation | Manual | `--github-setup` generates from project metadata |
| Validation | Lenient (fuzzy matching) | Strict (unknown column IDs error with guidance) |

---

## Technical Awareness

### GraphQL Queries

Existing queries in `src/sltasks/github/queries.py` already fetch Status field options. Updates needed:
- Extend `GET_USER_PROJECT` / `GET_ORG_PROJECT` to also return all single-select fields (for Size detection and `--github-setup`).
- `--github-setup` needs to query all single-select fields to offer Priority/Severity/Urgency selection.

### Repository Changes

`GitHubProjectsRepository` needs:
- New method to return detected columns (for validation and `--github-setup`).
- Priority field read/write via `updateProjectV2ItemFieldValue` when `github.priority_field` is configured.
- Removal of `_map_status_to_state` / `_map_state_to_status` fuzzy logic; replace with direct option ID lookup.
- Validation on startup: if `github.priority_field` is set but field doesn't exist in project, fail with error.

### Model Changes

- Add `github_label` to `TypeConfig` and `PriorityConfig`.
- Add `default_status`, `featured_labels`, `priority_field` to `GitHubConfig`.
- Remove `column_mapping` from `GitHubConfig`.

### CLI Changes

- New `--github-setup` flag in `__main__.py`.
- Interactive prompts using standard input (or a simple TUI flow).
- Config file generation and diff display.
- Prompts for: project URL, default status, priority field selection.

### Validation

- On startup, compare `board.columns` IDs against fetched Status options. Error if mismatch.
- On startup, if `github.priority_field` is set, verify field exists in project. Error if not found.
- Both errors should reference `--github-setup` as the fix.

---

## Open Items for Technical Plan

1. **Slugification rules**: How to convert "In progress" → `in_progress` consistently? Use existing `slug.py` utilities?
2. **Priority field editing**: Which mutations are needed? Same pattern as Status field updates.
3. **Label management**: When setting type, should we remove other type labels automatically?
4. **Offline handling**: What happens if GitHub is unreachable on startup?
5. **Migration path**: How do existing users with `column_mapping` transition? Deprecation warnings?
6. **Priority field option mapping**: How to match project field options (P0, P1, P2) to `board.priorities` entries? By name, by position, or explicit mapping?

---

## References

- [GitHub Projects Phase 1 Implementation](../../plans/github-projects-phase1-implementation.md)
- [GitHub Projects Integration Requirements](./github-projects-integration-requirements.md)
- [GitHub GraphQL API - Projects V2](https://docs.github.com/en/graphql/reference/objects#projectv2)
