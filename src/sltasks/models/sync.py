"""Sync-related data models for GitHub filesystem sync."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SyncStatus(str, Enum):
    """Status of a task's sync state with GitHub."""

    SYNCED = "synced"  # In sync with remote
    LOCAL_MODIFIED = "local_modified"  # Local changes pending push
    REMOTE_MODIFIED = "remote_modified"  # Remote changes pending pull
    CONFLICT = "conflict"  # Both local and remote changed
    LOCAL_ONLY = "local_only"  # New local file, not on GitHub


@dataclass
class PushResult:
    """Result of a push operation."""

    created: list[str] = field(default_factory=list)  # Issue IDs created (owner/repo#N)
    errors: list[str] = field(default_factory=list)  # Error messages
    dry_run: bool = False

    @property
    def success_count(self) -> int:
        """Number of successfully created issues."""
        return len(self.created)

    @property
    def error_count(self) -> int:
        """Number of errors encountered."""
        return len(self.errors)

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred."""
        return len(self.errors) > 0


@dataclass
class SyncResult:
    """Result of a sync (pull) operation."""

    pulled: int = 0  # Files created/updated from GitHub
    skipped: int = 0  # Files skipped (no changes)
    conflicts: int = 0  # Conflicts detected
    errors: list[str] = field(default_factory=list)  # Error messages
    dry_run: bool = False

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred."""
        return len(self.errors) > 0


@dataclass
class Conflict:
    """Represents a sync conflict between local and remote."""

    task_id: str  # Local task ID (filename)
    local_path: str  # Full path to local file
    issue_number: int  # GitHub issue number
    repository: str  # "owner/repo"
    local_updated: datetime  # When local file was updated
    remote_updated: datetime  # When GitHub issue was updated
    last_synced: datetime  # When last successful sync occurred


@dataclass
class ChangeSet:
    """Set of changes detected during sync."""

    to_pull: list[str] = field(default_factory=list)  # Task IDs to pull from GitHub
    to_push: list[str] = field(default_factory=list)  # Task IDs to push to GitHub
    conflicts: list[Conflict] = field(default_factory=list)  # Conflicts to resolve
