---
state: done
priority: medium
updated: '2025-11-29T18:46:20.990324+00:00'
---

# Phase 1: Config Model & Service

## Overview

This phase establishes the configuration infrastructure for custom columns. We create the Pydantic models for parsing `sltasks.yml` and a service to load/cache the configuration. After this phase, the app can read custom column definitions but won't use them yet.

## Goals

1. Create `SltasksConfig`, `BoardConfig`, and `ColumnConfig` Pydantic models
2. Create `ConfigService` to load and cache configuration
3. Add validation for column constraints (2-6 columns, unique IDs, no "archived")
4. Wire ConfigService into app initialization (unused)
5. Add unit tests for config loading and validation

## Task Checklist

- [x] Create `src/kosmos/models/sltasks_config.py`:
  - [x] `ColumnConfig` model with `id` and `title` fields
  - [x] `BoardConfig` model with `columns` list (min=2, max=6)
  - [x] `SltasksConfig` root model with `version` and `board`
  - [x] Validator for unique column IDs
  - [x] Validator rejecting "archived" as column ID
  - [x] `default()` class method returning 3-column default
- [x] Create `src/kosmos/services/config_service.py`:
  - [x] `ConfigService` class with `task_root` parameter
  - [x] `get_config()` method returning cached `SltasksConfig`
  - [x] `_load_config()` private method for YAML parsing
  - [x] Fallback to `SltasksConfig.default()` on missing/invalid file
  - [x] `reload()` method to clear cache
- [x] Update `src/kosmos/models/__init__.py` with exports
- [x] Update `src/kosmos/services/__init__.py` with exports
- [x] Wire into `src/kosmos/app.py`:
  - [x] Add `config_service` property
  - [x] Initialize on app startup
- [x] Create `tests/test_sltasks_config.py`:
  - [x] Test default config has 3 columns
  - [x] Test min columns validation (< 2 fails)
  - [x] Test max columns validation (> 6 fails)
  - [x] Test unique IDs validation
  - [x] Test "archived" rejection
  - [x] Test valid custom config parsing
- [x] Create `tests/test_config_service.py`:
  - [x] Test loading from valid file
  - [x] Test fallback on missing file
  - [x] Test fallback on invalid YAML
  - [x] Test caching behavior
  - [x] Test reload clears cache

## Detailed Specifications

### ColumnConfig Model

```python
from pydantic import BaseModel, Field


class ColumnConfig(BaseModel):
    """Configuration for a single board column."""

    id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    title: str = Field(..., min_length=1)
```

**Validation rules:**
- `id`: Required, lowercase alphanumeric with underscores, must start with letter
- `title`: Required, non-empty string

### BoardConfig Model

```python
from pydantic import BaseModel, Field, field_validator


class BoardConfig(BaseModel):
    """Configuration for board columns."""

    columns: list[ColumnConfig] = Field(..., min_length=2, max_length=6)

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v: list[ColumnConfig]) -> list[ColumnConfig]:
        # Check unique IDs
        ids = [col.id for col in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Column IDs must be unique")

        # Check reserved IDs
        if "archived" in ids:
            raise ValueError("'archived' is reserved and cannot be used as a column ID")

        return v

    @property
    def column_ids(self) -> list[str]:
        """List of column IDs in display order."""
        return [col.id for col in self.columns]

    def get_title(self, column_id: str) -> str:
        """Get display title for a column ID."""
        for col in self.columns:
            if col.id == column_id:
                return col.title
        return column_id.replace("_", " ").title()

    def is_valid_status(self, status: str) -> bool:
        """Check if status is valid (in columns or 'archived')."""
        return status in self.column_ids or status == "archived"

    @classmethod
    def default(cls) -> "BoardConfig":
        """Return default 3-column configuration."""
        return cls(columns=[
            ColumnConfig(id="todo", title="To Do"),
            ColumnConfig(id="in_progress", title="In Progress"),
            ColumnConfig(id="done", title="Done"),
        ])
```

### SltasksConfig Model

```python
class SltasksConfig(BaseModel):
    """Root configuration from sltasks.yml."""

    version: int = 1
    board: BoardConfig = Field(default_factory=BoardConfig.default)

    @classmethod
    def default(cls) -> "SltasksConfig":
        """Return default configuration."""
        return cls(board=BoardConfig.default())
```

### ConfigService

```python
from pathlib import Path
import yaml
from kosmos.models import SltasksConfig


class ConfigService:
    """Service for loading and caching application configuration."""

    CONFIG_FILE = "sltasks.yml"

    def __init__(self, task_root: Path) -> None:
        self.task_root = task_root
        self._config: SltasksConfig | None = None

    def get_config(self) -> SltasksConfig:
        """Get configuration, loading from file if not cached."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def get_board_config(self) -> BoardConfig:
        """Convenience method to get board configuration."""
        return self.get_config().board

    def reload(self) -> None:
        """Clear cached configuration, forcing reload on next access."""
        self._config = None

    def _load_config(self) -> SltasksConfig:
        """Load configuration from file or return default."""
        config_path = self.task_root / self.CONFIG_FILE

        if not config_path.exists():
            return SltasksConfig.default()

        try:
            with open(config_path) as f:
                data = yaml.safe_load(f) or {}
            return SltasksConfig(**data)
        except Exception:
            # Invalid YAML or validation error - use defaults
            return SltasksConfig.default()
```

### App Integration

```python
# In src/kosmos/app.py

class KosmosApp(App):
    def __init__(self, task_root: Path | None = None) -> None:
        super().__init__()
        self._task_root = task_root or Path(".tasks")
        self._config_service: ConfigService | None = None
        # ... existing code ...

    @property
    def config_service(self) -> ConfigService:
        """Get the configuration service."""
        if self._config_service is None:
            self._config_service = ConfigService(self._task_root)
        return self._config_service
```

## Example sltasks.yml Files

### Minimal (2 columns)
```yaml
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: done
      title: "Done"
```

### Maximum (6 columns)
```yaml
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: todo
      title: "To Do"
    - id: in_progress
      title: "In Progress"
    - id: review
      title: "Code Review"
    - id: testing
      title: "Testing"
    - id: done
      title: "Done"
```

### Invalid Examples (should fail validation)

```yaml
# Too few columns
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
```

```yaml
# Duplicate IDs
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: todo
      title: "Also To Do"
    - id: done
      title: "Done"
```

```yaml
# Reserved "archived" ID
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: archived
      title: "Archive"
    - id: done
      title: "Done"
```

## Testing Strategy

### Unit Tests (test_sltasks_config.py)

```python
import pytest
from pydantic import ValidationError
from kosmos.models import SltasksConfig, BoardConfig, ColumnConfig


class TestColumnConfig:
    def test_valid_id(self):
        col = ColumnConfig(id="in_progress", title="In Progress")
        assert col.id == "in_progress"

    def test_invalid_id_uppercase(self):
        with pytest.raises(ValidationError):
            ColumnConfig(id="InProgress", title="In Progress")

    def test_invalid_id_starts_with_number(self):
        with pytest.raises(ValidationError):
            ColumnConfig(id="1st_column", title="First")


class TestBoardConfig:
    def test_default_has_three_columns(self):
        config = BoardConfig.default()
        assert len(config.columns) == 3
        assert config.column_ids == ["todo", "in_progress", "done"]

    def test_min_columns_validation(self):
        with pytest.raises(ValidationError):
            BoardConfig(columns=[ColumnConfig(id="only", title="Only")])

    def test_max_columns_validation(self):
        cols = [ColumnConfig(id=f"col{i}", title=f"Col {i}") for i in range(7)]
        with pytest.raises(ValidationError):
            BoardConfig(columns=cols)

    def test_unique_ids_validation(self):
        with pytest.raises(ValidationError):
            BoardConfig(columns=[
                ColumnConfig(id="same", title="First"),
                ColumnConfig(id="same", title="Second"),
            ])

    def test_archived_reserved(self):
        with pytest.raises(ValidationError):
            BoardConfig(columns=[
                ColumnConfig(id="todo", title="To Do"),
                ColumnConfig(id="archived", title="Archive"),
                ColumnConfig(id="done", title="Done"),
            ])

    def test_get_title(self):
        config = BoardConfig.default()
        assert config.get_title("in_progress") == "In Progress"
        assert config.get_title("unknown") == "Unknown"

    def test_is_valid_status(self):
        config = BoardConfig.default()
        assert config.is_valid_status("todo") is True
        assert config.is_valid_status("archived") is True  # Always valid
        assert config.is_valid_status("unknown") is False


class TestSltasksConfig:
    def test_default(self):
        config = SltasksConfig.default()
        assert config.version == 1
        assert len(config.board.columns) == 3
```

### Integration Tests (test_config_service.py)

```python
import pytest
from pathlib import Path
from kosmos.services import ConfigService


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    """Create a temporary task directory."""
    task_root = tmp_path / ".tasks"
    task_root.mkdir()
    return task_root


class TestConfigService:
    def test_default_on_missing_file(self, task_dir: Path):
        service = ConfigService(task_dir)
        config = service.get_config()
        assert len(config.board.columns) == 3

    def test_load_valid_config(self, task_dir: Path):
        config_file = task_dir / "sltasks.yml"
        config_file.write_text("""
version: 1
board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: done
      title: "Done"
""")
        service = ConfigService(task_dir)
        config = service.get_config()
        assert len(config.board.columns) == 2
        assert config.board.column_ids == ["backlog", "done"]

    def test_fallback_on_invalid_yaml(self, task_dir: Path):
        config_file = task_dir / "sltasks.yml"
        config_file.write_text("invalid: yaml: content:")
        service = ConfigService(task_dir)
        config = service.get_config()
        assert len(config.board.columns) == 3  # Default

    def test_caching(self, task_dir: Path):
        service = ConfigService(task_dir)
        config1 = service.get_config()
        config2 = service.get_config()
        assert config1 is config2  # Same instance

    def test_reload_clears_cache(self, task_dir: Path):
        service = ConfigService(task_dir)
        config1 = service.get_config()
        service.reload()
        config2 = service.get_config()
        assert config1 is not config2  # Different instances
```

## Verification Steps

1. Run `uv run pytest tests/test_sltasks_config.py -v` - all tests pass
2. Run `uv run pytest tests/test_config_service.py -v` - all tests pass
3. Verify app starts without `sltasks.yml` (uses defaults)
4. Create a valid `sltasks.yml` and verify it loads without errors

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|
| 2025-11-29 | Used simple string validation instead of regex pattern in ColumnConfig | Clearer error messages with explicit validators |

## Completion Notes

**Phase 1 status: Complete**

Completed on 2025-11-29.

Files created:
- `src/kosmos/models/sltasks_config.py` - ColumnConfig, BoardConfig, SltasksConfig models
- `src/kosmos/services/config_service.py` - ConfigService with caching and error handling
- `tests/test_sltasks_config.py` - 30 tests for config models
- `tests/test_config_service.py` - 16 tests for config service

Files modified:
- `src/kosmos/models/__init__.py` - Added exports
- `src/kosmos/services/__init__.py` - Added ConfigService export
- `src/kosmos/app.py` - Added ConfigService initialization

Verification:
- All 139 tests passing (46 new + 93 existing)
- App imports and runs correctly
- ConfigService falls back to defaults when no config file exists

## Key Notes

- ConfigService is initialized lazily via property
- Invalid config files silently fall back to defaults (no crash)
- The `archived` status is always valid even though it's not in columns
- Column ID validation uses regex to enforce snake_case format