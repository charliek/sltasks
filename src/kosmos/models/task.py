"""Task domain model."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from .enums import Priority, TaskState


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
        data: dict = {}
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
