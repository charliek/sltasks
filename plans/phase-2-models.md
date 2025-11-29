# Phase 2: Models & Data Layer

## Overview

This phase creates the core data models using Pydantic. These models define the structure of tasks, board state, and the enums used throughout the application. All fields use type hints and the models are designed to work seamlessly with YAML front matter parsing.

## Goals

1. Define enums for task state and priority
2. Create the Task model with all optional fields and sensible defaults
3. Create the BoardOrder model for tasks.yaml structure
4. Ensure models can serialize to/from YAML front matter format

## Task Checklist

- [x] Create `src/kosmos/models/enums.py`:
  - [x] `TaskState` enum (todo, in_progress, done, archived)
  - [x] `Priority` enum (low, medium, high, critical)
- [x] Create `src/kosmos/models/task.py`:
  - [x] `Task` Pydantic model with all fields
  - [x] Default values matching PRD spec
  - [x] `to_frontmatter()` method for serialization
  - [x] `from_frontmatter()` class method for parsing
- [x] Create `src/kosmos/models/board.py`:
  - [x] `BoardOrder` Pydantic model
  - [x] `Board` model for full board state with tasks grouped by column
  - [x] Column ordering structure
- [x] Update `src/kosmos/models/__init__.py` with exports
- [x] Create `src/kosmos/utils/slug.py`:
  - [x] `slugify()` function for filename generation
  - [x] `generate_filename()` function
- [x] Create `src/kosmos/utils/datetime.py`:
  - [x] `now_utc()` - get current UTC datetime
  - [x] `to_iso()` - convert to ISO string
  - [x] `from_iso()` - parse ISO string
- [x] Update `src/kosmos/utils/__init__.py` with exports
- [x] Write tests for complex logic (slug generation) - 14 tests passing

## Detailed Specifications

### Enums (models/enums.py)

```python
from enum import Enum


class TaskState(str, Enum):
    """Valid states for a task."""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    ARCHIVED = "archived"


class Priority(str, Enum):
    """Priority levels for tasks."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

Using `str, Enum` allows direct string comparison and YAML serialization.

### Task Model (models/task.py)

```python
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field
from .enums import TaskState, Priority


class Task(BaseModel):
    """Represents a single task from a markdown file."""

    # File identification
    filename: str  # e.g., "fix-login-bug.md"
    filepath: Path | None = None  # Full path, set by repository

    # Front matter fields (all optional with defaults)
    title: str | None = None  # Defaults to filename without .md
    state: TaskState = TaskState.TODO
    priority: Priority = Priority.MEDIUM
    tags: list[str] = Field(default_factory=list)
    created: datetime | None = None
    updated: datetime | None = None

    # Content
    body: str = ""  # Markdown content after front matter

    @property
    def display_title(self) -> str:
        """Title for display - uses filename if title not set."""
        if self.title:
            return self.title
        return self.filename.replace(".md", "").replace("-", " ").title()

    def to_frontmatter(self) -> dict:
        """Convert to dict suitable for YAML front matter."""
        data = {}
        if self.title:
            data["title"] = self.title
        data["state"] = self.state.value
        data["priority"] = self.priority.value
        if self.tags:
            data["tags"] = self.tags
        if self.created:
            data["created"] = self.created.isoformat()
        if self.updated:
            data["updated"] = self.updated.isoformat()
        return data

    @classmethod
    def from_frontmatter(
        cls,
        filename: str,
        metadata: dict,
        body: str,
        filepath: Path | None = None,
    ) -> "Task":
        """Create Task from parsed front matter."""
        return cls(
            filename=filename,
            filepath=filepath,
            title=metadata.get("title"),
            state=TaskState(metadata.get("state", "todo")),
            priority=Priority(metadata.get("priority", "medium")),
            tags=metadata.get("tags", []),
            created=_parse_datetime(metadata.get("created")),
            updated=_parse_datetime(metadata.get("updated")),
            body=body,
        )


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse datetime from string or pass through."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
```

### Board Order Model (models/board.py)

```python
from pydantic import BaseModel, Field


class BoardOrder(BaseModel):
    """Represents the ordering of tasks in tasks.yaml."""

    version: int = 1
    columns: dict[str, list[str]] = Field(default_factory=lambda: {
        "todo": [],
        "in_progress": [],
        "done": [],
        "archived": [],
    })

    def get_position(self, filename: str, state: str) -> int:
        """Get position of task in its column, or -1 if not found."""
        column = self.columns.get(state, [])
        try:
            return column.index(filename)
        except ValueError:
            return -1

    def add_task(self, filename: str, state: str, position: int = -1) -> None:
        """Add task to column at position (-1 = end)."""
        if state not in self.columns:
            self.columns[state] = []

        # Remove from any existing column first
        self.remove_task(filename)

        if position < 0:
            self.columns[state].append(filename)
        else:
            self.columns[state].insert(position, filename)

    def remove_task(self, filename: str) -> None:
        """Remove task from all columns."""
        for column in self.columns.values():
            if filename in column:
                column.remove(filename)

    def move_task(self, filename: str, from_state: str, to_state: str, position: int = -1) -> None:
        """Move task between columns."""
        self.remove_task(filename)
        self.add_task(filename, to_state, position)
```

### Slug Utility (utils/slug.py)

```python
import re
import unicodedata


def slugify(text: str) -> str:
    """
    Convert text to a filesystem-safe slug.

    Example: "Fix Login Bug!" -> "fix-login-bug"
    """
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)

    # Remove any character that isn't alphanumeric or hyphen
    text = re.sub(r"[^a-z0-9\-]", "", text)

    # Remove leading/trailing hyphens and collapse multiple hyphens
    text = re.sub(r"-+", "-", text).strip("-")

    return text


def generate_filename(title: str) -> str:
    """Generate a .md filename from a title."""
    slug = slugify(title)
    if not slug:
        slug = "untitled"
    return f"{slug}.md"
```

### DateTime Utility (utils/datetime.py)

```python
from datetime import datetime, timezone


def now_utc() -> datetime:
    """Get current UTC datetime."""
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Convert datetime to ISO format string."""
    return dt.isoformat()


def from_iso(value: str) -> datetime:
    """Parse ISO format string to datetime."""
    # Handle both 'Z' suffix and explicit timezone
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
```

## Model Relationships

```
Task
├── filename: str (identifier)
├── filepath: Path (full path)
├── title: str (display name)
├── state: TaskState (column)
├── priority: Priority (visual indicator)
├── tags: list[str] (filtering)
├── created/updated: datetime
└── body: str (markdown content)

BoardOrder
├── version: int
└── columns: dict[state -> list[filename]]
```

## Testing Notes

Tests should focus on:
- `slugify()` with various inputs (unicode, special chars, spaces)
- `Task.from_frontmatter()` with missing fields
- `Task.to_frontmatter()` round-trip
- `BoardOrder` add/remove/move operations

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|
| 2025-11-28 | Added `Board` model to board.py | Needed for Phase 5 TUI to group tasks by state for display |
| 2025-11-28 | Added explicit type annotation `dict` in `to_frontmatter()` | Clarity for return type |

## Completion Notes

**Phase 2 completed on 2025-11-28**

Files created:
- `src/kosmos/models/enums.py` - TaskState and Priority enums
- `src/kosmos/models/task.py` - Task Pydantic model
- `src/kosmos/models/board.py` - BoardOrder and Board models
- `src/kosmos/utils/slug.py` - slugify and generate_filename
- `src/kosmos/utils/datetime.py` - now_utc, to_iso, from_iso
- `tests/test_slug.py` - 14 tests for slug generation

Verification:
- All 14 slug tests passing
- Models import correctly and serialize/deserialize as expected
- Frontmatter round-trip works correctly

## Key Notes

- All Task fields are optional to support minimal markdown files
- The `filename` field is the stable identifier (not title)
- `filepath` is set by the repository layer, not during parsing
- Using `str, Enum` pattern for easy YAML/JSON serialization
- DateTime parsing handles both 'Z' suffix and explicit timezone offset
