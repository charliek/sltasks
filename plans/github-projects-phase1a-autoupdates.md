# GitHub Projects Phase 1A - Auto-Detection Updates

## Overview

This plan implements the requirements from `docs/design/github-phase1-updates.md`. The main goals are:

1. Auto-detect columns from GitHub Status field (remove manual `column_mapping`)
2. Support priority via project fields or label fallback
3. Add explicit `github_label` for type/priority write-back
4. Create `--github-setup` CLI command for interactive config generation

## References

- Requirements: [docs/design/github-phase1-updates.md](../docs/design/github-phase1-updates.md)
- Original Phase 1: [plans/github-projects-phase1-implementation.md](./github-projects-phase1-implementation.md)
- Integration Requirements: [docs/design/github-projects-integration-requirements.md](../docs/design/github-projects-integration-requirements.md)

---

## Resolved Design Decisions

| Question | Decision |
|----------|----------|
| Should `board.columns` be required for GitHub provider? | **Optional**. If omitted, auto-generate from Status options at runtime. If present, validate against Status options. |
| What if GitHub Status options change after setup? | Fail validation with clear error pointing to `--github-setup` |
| Support partial column overrides? | **No**. Require full list if any columns specified. |
| Priority option ordering | **By position**. First GitHub field option → first priority. Simple and predictable. |
| Label write-back field | **Reuse existing `canonical_alias`** on TypeConfig/PriorityConfig. No new `github_label` field needed. |
| `status_alias` on ColumnConfig | **Keep**. Still needed for file-based provider. |
| File provider impact | **None**. All changes isolated to GitHub provider. |

---

## Phase 1: Model Changes

### 1.1 TypeConfig and PriorityConfig - NO CHANGES

**Decision**: Reuse existing `canonical_alias` field for GitHub label write-back.

Both `TypeConfig` and `PriorityConfig` already have:
- `canonical_alias: str | None` - for external system write-back
- `write_alias` property - returns `canonical_alias` or `id`

No new fields needed. The existing `canonical_alias` serves the same purpose as the proposed `github_label`.

### 1.2 Update `GitHubConfig` Model

**File**: `src/sltasks/models/sltasks_config.py`

- [ ] Remove `column_mapping` field
- [ ] Add `default_status: str | None` field
- [ ] Add `priority_field: str | None` field
- [ ] Add `featured_labels: list[str]` field

### 1.3 Tests for Model Changes

**File**: `tests/test_sltasks_config.py`

- [ ] Test new `GitHubConfig` fields (`default_status`, `priority_field`, `featured_labels`)
- [ ] Test that `column_mapping` is no longer present in model

---

## Phase 2: Slugification Utility

### 2.1 Add Column ID Slugification

**File**: `src/sltasks/utils/slug.py`

- [ ] Add `slugify_column_id()` function

**Function specification**:
```python
def slugify_column_id(name: str) -> str:
    """
    Convert a GitHub Status option name to a valid sltasks column ID.
    
    Rules:
    - Lowercase
    - Spaces/hyphens become underscores
    - Remove non-alphanumeric characters (except underscores)
    - Must start with a letter (prefix with 'col_' if not)
    
    Examples:
        "In progress" -> "in_progress"
        "Ready" -> "ready"
        "In Review" -> "in_review"
        "Done ✓" -> "done"
        "123 Numbers" -> "col_123_numbers"
    """
```

### 2.2 Tests for Slugification

**File**: `tests/test_slug.py`

- [ ] Test basic conversion: "In progress" → "in_progress"
- [ ] Test simple word: "Ready" → "ready"
- [ ] Test multiple words: "In Review" → "in_review"
- [ ] Test unicode removal: "Done ✓" → "done"
- [ ] Test numeric prefix: "123 Numbers First" → "col_123_numbers_first"
- [ ] Test empty/edge cases

---

## Phase 3: Repository Updates

### 3.1 Add Field Extraction Method

**File**: `src/sltasks/repositories/github_projects.py`

- [ ] Add `_extract_all_fields()` method to extract all single-select fields
- [ ] Store fields in `self._single_select_fields: dict[str, dict]`
- [ ] Update `_extract_status_field()` to use new method or integrate

### 3.2 Update Validation Logic

**File**: `src/sltasks/repositories/github_projects.py`

- [ ] Update `validate()` to check `board.columns` against GitHub Status options
- [ ] Add validation for `github.priority_field` if set
- [ ] Cache priority field info (`_priority_field_id`, `_priority_options`)
- [ ] Return actionable error messages pointing to `--github-setup`

**Error message templates**:
```
Column '{col.id}' not found in GitHub project.
Available columns: {available}
Run 'sltasks --github-setup' to regenerate configuration.

Priority field '{field_name}' not found in GitHub project.
Available single-select fields: {available}
Run 'sltasks --github-setup' to reconfigure.
```

### 3.3 Replace Fuzzy Mapping with Direct Lookup

**File**: `src/sltasks/repositories/github_projects.py`

- [ ] Rewrite `_map_status_to_state()` to use `slugify_column_id()` directly
- [ ] Rewrite `_map_state_to_status()` to find Status option by matching slugified name
- [ ] Remove fuzzy matching logic (title matching, alias checking for columns)

### 3.4 Add Priority Field Read Support

**File**: `src/sltasks/repositories/github_projects.py`

- [ ] Add `_extract_priority_from_item()` method
- [ ] Check `github.priority_field` config first
- [ ] Fall back to `_extract_priority_from_labels()` if no field configured
- [ ] Match field options to `board.priorities` by label or alias

### 3.5 Add Priority Field Write Support

**File**: `src/sltasks/repositories/github_projects.py`

- [ ] Add `_update_priority_field()` method
- [ ] Call from `_update_issue()` when priority changes
- [ ] Use `UPDATE_ITEM_FIELD` mutation (same as status updates)

### 3.6 Add Project Metadata Method

**File**: `src/sltasks/repositories/github_projects.py`

- [ ] Add `get_project_metadata()` method for `--github-setup`
- [ ] Return dict with: project_title, status_options, single_select_fields

### 3.7 Handle Optional `board.columns`

**File**: `src/sltasks/repositories/github_projects.py`

- [ ] If `board.columns` is empty/default, auto-generate from Status options
- [ ] Store generated columns for use by services

### 3.8 Tests for Repository Changes

**File**: `tests/test_github_repository.py`

- [ ] Update existing tests to remove `column_mapping` usage
- [ ] Add test for column validation error (unknown column ID)
- [ ] Add test for `priority_field` validation error
- [ ] Add test for direct status mapping (no fuzzy)
- [ ] Add test for priority field read
- [ ] Add test for priority field write
- [ ] Add test for auto-generated columns when `board.columns` empty

---

## Phase 4: CLI `--github-setup` Command

### 4.1 Add CLI Argument

**File**: `src/sltasks/__main__.py`

- [ ] Add `--github-setup` argument (optional PROJECT_URL)
- [ ] Route to `run_github_setup()` in main()

### 4.2 Create GitHub Setup Module

**New File**: `src/sltasks/cli/github_setup.py`

- [ ] Create `run_github_setup()` main function
- [ ] Implement `prompt_project_url()` - prompt for URL if not provided
- [ ] Implement `parse_project_url()` - extract owner, type, number
- [ ] Implement `fetch_project_metadata()` - call GitHub API
- [ ] Implement `find_priority_fields()` - detect Priority/Severity/Urgency
- [ ] Implement `generate_priorities_config()` - create board.priorities from options
- [ ] Implement `generate_config()` - assemble full config dict
- [ ] Implement `generate_yaml()` - serialize to YAML string
- [ ] Implement `prompt_choice()` - numeric selection prompt
- [ ] Implement `prompt_write_action()` - y/N/print prompt
- [ ] Implement `prompt_default_repo()` - ask for default repo
- [ ] Implement `detect_default_repo()` - auto-detect from project items

### 4.3 Interactive Flow

The command should follow this flow:

1. Get project URL (argument or prompt)
2. Parse URL and authenticate
3. Fetch project metadata via GraphQL
4. Display detected Status columns
5. Prompt for priority field selection (if any detected)
6. Prompt for default status (for new issues)
7. Detect or prompt for default repository
8. Generate config YAML
9. Preview and prompt to write/print/cancel
10. Write file (with backup if exists) or print only

### 4.4 Tests for GitHub Setup

**New File**: `tests/test_github_setup.py`

- [ ] Test `parse_project_url()` with valid URLs
- [ ] Test `parse_project_url()` with invalid URLs
- [ ] Test `find_priority_fields()` detection
- [ ] Test `generate_priorities_config()` output
- [ ] Test `generate_config()` structure
- [ ] Test `slugify_column_id()` integration

---

## Phase 5: Documentation Updates

### 5.1 Update CLAUDE.md

**File**: `CLAUDE.md`

- [ ] Document `--github-setup` command
- [ ] Note removal of `column_mapping`
- [ ] Document use of `canonical_alias` for GitHub label write-back

### 5.2 Update User Documentation

**File**: `docs/user-guide/configuration.md` (if exists)

- [ ] Document GitHub provider configuration
- [ ] Document `--github-setup` workflow
- [ ] Provide example configurations

---

## Phase 6: Migration Path

### 6.1 Deprecation Warning for `column_mapping`

**File**: `src/sltasks/services/config_service.py`

- [ ] Check for `column_mapping` in loaded YAML
- [ ] Log warning if present (will be ignored)
- [ ] Point user to `--github-setup`

---

## Implementation Order

Execute phases in this order to minimize risk:

1. **Phase 2: Slugification** - Isolated utility, no dependencies
2. **Phase 1: Model Changes** - Schema updates, run existing tests
3. **Phase 3: Repository Updates** - Core logic changes
4. **Phase 4: CLI Command** - Additive feature
5. **Phase 5: Documentation** - Update as needed
6. **Phase 6: Migration** - Polish

---

## Execution Notes

### Implementation Progress

**ALL PHASES COMPLETED:**

- [x] Phase 2 (Slugification): Added `slugify_column_id()` to `src/sltasks/utils/slug.py` with tests
- [x] Phase 1 (Model Changes): Updated `GitHubConfig` - removed `column_mapping`, added `default_status`, `priority_field`, `featured_labels`
- [x] Phase 3 (Repository Updates):
  - Updated `_extract_project_fields()` to extract all single-select fields
  - Added `_validate_columns_against_status()` for column validation
  - Added `_validate_priority_field()` for priority field validation
  - Replaced fuzzy matching with direct `slugify_column_id()` in `_map_status_to_state()` and `_map_state_to_status()`
  - Added `_extract_priority_from_item()` and `_extract_priority_from_field()` for priority field support
  - Added `get_project_metadata()` method for --github-setup
  - Added `get_status_column_ids()` method
  - Updated tests to use new column IDs (e.g., "to_do" instead of "todo")
- [x] Phase 4 (CLI Command): Created `src/sltasks/cli/github_setup.py` with:
  - Interactive project URL input/parsing
  - GitHub API authentication via env var or `gh` CLI
  - Project metadata fetching via GraphQL
  - Priority field detection and selection
  - Default status selection
  - Repository detection from project items
  - YAML config generation with preview
  - File write with backup support
  - Tests in `tests/test_github_setup.py` (23 tests)
- [x] Phase 5 (Documentation): Updated `CLAUDE.md` with:
  - New `--github-setup` command
  - GitHub provider section
  - GitHubProjectsRepository in architecture
- [x] Phase 6: SKIPPED per user request (no migration warnings needed)

### Key Changes Summary

1. **Column IDs now match slugified GitHub Status options**: e.g., "To Do" → "to_do", "In Progress" → "in_progress"
2. **Removed `column_mapping`** - direct 1:1 mapping via slugification
3. **Priority can come from project fields** - via `github.priority_field` config
4. **Validation now checks columns** - fails if board.columns don't match Status options

---

## Verification Checklist

After implementation, verify:

- [ ] `uv run pytest` - All tests pass
- [ ] `./scripts/lint.sh` - No lint errors
- [ ] Manual test: `--github-setup` with real project
- [ ] Manual test: TUI with auto-detected columns
- [ ] Manual test: Priority field read/write
- [ ] Manual test: Error messages for misconfigured columns
- [ ] Existing `provider: file` functionality unchanged
