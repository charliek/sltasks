"""Utilities for datetime handling."""

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
