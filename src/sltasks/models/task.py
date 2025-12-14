"""Task domain model."""

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

# State constants for common states
STATE_TODO = "todo"
STATE_IN_PROGRESS = "in_progress"
STATE_DONE = "done"
STATE_ARCHIVED = "archived"


class Task(BaseModel):
    """Represents a single task from a markdown file."""

    # Task identification
    id: str  # e.g., "fix-login-bug.md" (filesystem), "PROJ-123" (Jira), "#456" (GitHub)
    filepath: Path | None = None  # Full path, set by repository (filesystem only)

    # Front matter fields (all optional with defaults)
    title: str | None = None  # Defaults to filename without .md
    state: str = STATE_TODO  # String to support custom states
    priority: str = "medium"  # String to support configurable priorities
    tags: list[str] = Field(default_factory=list)
    type: str | None = None  # Task type (feature, bug, task, etc.)
    created: datetime | None = None
    updated: datetime | None = None

    # Content
    body: str = ""  # Markdown content after front matter

    @property
    def display_title(self) -> str:
        """Title for display - uses ID if title not set."""
        if self.title:
            return self.title
        # For filesystem IDs (ending in .md), transform to readable title
        display = self.id
        if display.endswith(".md"):
            display = display[:-3]
        return display.replace("-", " ").title()

    def to_frontmatter(self) -> dict:
        """Convert to dict suitable for YAML front matter."""
        data: dict = {}
        if self.title:
            data["title"] = self.title
        data["state"] = self.state
        data["priority"] = self.priority
        if self.tags:
            data["tags"] = self.tags
        if self.type:
            data["type"] = self.type
        if self.created:
            data["created"] = self.created.isoformat()
        if self.updated:
            data["updated"] = self.updated.isoformat()
        return data

    @classmethod
    def from_frontmatter(
        cls,
        task_id: str,
        metadata: dict,
        body: str,
        filepath: Path | None = None,
    ) -> "Task":
        """Create Task from parsed front matter."""
        return cls(
            id=task_id,
            filepath=filepath,
            title=metadata.get("title"),
            state=metadata.get("state", STATE_TODO),
            priority=metadata.get("priority", "medium"),
            tags=metadata.get("tags", []),
            type=metadata.get("type"),
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
