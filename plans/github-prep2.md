# GitHub Integration Preparatory Refactors - Phase 2

## Overview

This document outlines the preparatory refactors needed before implementing GitHub Projects integration (Phases 1-2 from `docs/design/github-projects-integration-requirements.md`). These changes establish a provider-agnostic architecture that supports multiple backends: filesystem (default), GitHub Projects, GitHub PRs, and Jira.

## Goals

1. **Provider abstraction** - Enable swapping between filesystem, GitHub, and Jira backends
2. **Type-safe provider data** - Store provider-specific metadata without polluting the Task model
3. **Canonical aliases** - Support roundtrip of labels/priorities when writing back to external systems
4. **Provider validation** - Allow providers to validate connectivity before operations

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Terminology | "provider" not "backend" | Clearer for users (file, github, jira providers) |
| Provider data | Discriminated union (Option A) | Type-safe, IDE support, Pydantic validation |
| Column mapping | Auto-detect + generate support | Reduces friction; `--generate` writes editable config |
| Workflow restrictions | Optimistic with graceful failure | Responsive UI; clear error messages |
| Issue type selection | Present list like feature/bug/task | Consistent UX; maps external types via `type_alias` |

## Implementation

### Phase 1: Config & Service Layer

#### 1.1 Add `provider` field to SltasksConfig

**File:** `src/sltasks/models/sltasks_config.py`

```python
class SltasksConfig(BaseModel):
    version: int = 1
    provider: str = "file"  # "file", "github", "github-prs", "jira"
    task_root: str = Field(default=".tasks", ...)
    board: BoardConfig = Field(default_factory=BoardConfig.default)
```

#### 1.2 Fix TaskService repository type hint

**File:** `src/sltasks/services/task_service.py`

Change from:
```python
from ..repositories import FilesystemRepository
def __init__(self, repository: FilesystemRepository, ...):
```

To:
```python
from ..repositories import RepositoryProtocol
def __init__(self, repository: RepositoryProtocol, ...):
```

---

### Phase 2: Provider Data Model

#### 2.1 Create provider_data.py with discriminated union

**New file:** `src/sltasks/models/provider_data.py`

```python
from pydantic import BaseModel
from typing import Literal

class FileProviderData(BaseModel):
    """Provider data for filesystem tasks."""
    provider: Literal["file"] = "file"
    # No additional fields - filepath derived from task.id + task_root

class GitHubProviderData(BaseModel):
    """Provider data for GitHub Projects tasks."""
    provider: Literal["github"] = "github"
    project_item_id: str          # "PVTI_..." - needed for mutations
    issue_node_id: str            # "I_kw..." - needed for GraphQL
    repository: str               # "owner/repo"
    issue_number: int             # 123
    type_label: str | None = None
    priority_label: str | None = None

class GitHubPRProviderData(BaseModel):
    """Provider data for GitHub PR tasks."""
    provider: Literal["github-prs"] = "github-prs"
    owner: str
    repo: str
    pr_number: int
    head_branch: str
    base_branch: str
    author: str
    review_summary: str | None = None
    ci_status: str | None = None
    is_draft: bool = False

class JiraProviderData(BaseModel):
    """Provider data for Jira tasks."""
    provider: Literal["jira"] = "jira"
    issue_key: str                # "PROJ-123"
    project_key: str              # "PROJ"

ProviderData = FileProviderData | GitHubProviderData | GitHubPRProviderData | JiraProviderData | None
```

#### 2.2 Update Task model

**File:** `src/sltasks/models/task.py`

Replace `filepath` with `provider_data`:
```python
from .provider_data import ProviderData

class Task(BaseModel):
    id: str
    # filepath: Path | None = None  # REMOVE
    provider_data: ProviderData = None
```

#### 2.3 Update FilesystemRepository

**File:** `src/sltasks/repositories/filesystem.py`

- Use `FileProviderData()` when creating tasks
- Derive filepath from `task_root / task.id`
- Skip `provider_data` in frontmatter serialization (nothing to write for file provider)

#### 2.4 Update tests

- `tests/test_models.py` - Add provider_data tests
- `tests/test_filesystem.py` - Update for provider_data changes

---

### Phase 3: Canonical Aliases & Validation

#### 3.1 Add canonical_alias to config models

**File:** `src/sltasks/models/sltasks_config.py`

```python
class TypeConfig(BaseModel):
    id: str
    template: str | None = None
    color: str = "white"
    type_alias: list[str] = Field(default_factory=list)
    canonical_alias: str | None = None  # Label to use when writing to external systems

class PriorityConfig(BaseModel):
    id: str
    label: str
    color: str = "white"
    symbol: str | None = None
    priority_alias: list[str] = Field(default_factory=list)
    canonical_alias: str | None = None  # Label to use when writing to external systems
```

If `canonical_alias` is not set, defaults to `id`.

#### 3.2 Add validate() to RepositoryProtocol

**File:** `src/sltasks/repositories/protocol.py`

```python
class RepositoryProtocol(Protocol):
    # ... existing methods ...

    def validate(self) -> tuple[bool, str | None]:
        """Validate provider connectivity and configuration.

        Returns: (is_valid, error_message_if_invalid)
        """
        ...
```

- Filesystem: Returns `(True, None)`
- GitHub: Validates token, project access
- Jira: Validates credentials, board access

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `src/sltasks/models/provider_data.py` | Create | Discriminated union of provider data models |
| `src/sltasks/models/sltasks_config.py` | Modify | Add `provider` field, `canonical_alias` to TypeConfig/PriorityConfig |
| `src/sltasks/models/task.py` | Modify | Replace `filepath` with `provider_data` |
| `src/sltasks/models/__init__.py` | Modify | Export new provider_data types |
| `src/sltasks/services/task_service.py` | Modify | Change type hint to `RepositoryProtocol` |
| `src/sltasks/repositories/filesystem.py` | Modify | Use `FileProviderData`, derive filepath from id |
| `src/sltasks/repositories/protocol.py` | Modify | Add `validate()` method |
| `tests/test_models.py` | Modify | Add provider_data tests |
| `tests/test_filesystem.py` | Modify | Update for provider_data |

---

## Documentation Updates

After implementation:

1. **Design docs** (`docs/design/`)
   - Update `github-projects-integration-requirements.md` - Mark prep work complete
   - Update `jira-integration-requirements.md` - Mark prep work complete
   - Update `repository-protocol.md` - Document `validate()` method

2. **User docs** (`docs/`)
   - Add provider configuration section
   - Document `provider` field in config

3. **Project docs**
   - `README.md` - Update config example with `provider` field
   - `CLAUDE.md` - Update architecture with provider_data model

---

## Testing Strategy

1. **Unit tests**
   - Provider data model serialization/deserialization
   - Discriminated union type narrowing
   - Canonical alias defaulting

2. **Integration tests**
   - FilesystemRepository with FileProviderData
   - Task serialization excludes provider_data for file provider
   - Provider validation

3. **Coverage**
   - Maintain existing coverage levels
   - All new code paths covered

---

## Alignment with Future Providers

This architecture supports:

| Provider | Status | Notes |
|----------|--------|-------|
| File (filesystem) | Current | Default provider |
| GitHub Projects | Planned | Uses `GitHubProviderData` |
| GitHub PRs | Planned | Uses `GitHubPRProviderData`, read-only |
| Jira | Planned | Uses `JiraProviderData` |

All providers implement `RepositoryProtocol` and store provider-specific data in typed `ProviderData` models.
