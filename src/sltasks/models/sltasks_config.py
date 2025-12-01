"""Configuration models for sltasks.yml."""

from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class ColumnConfig(BaseModel):
    """Configuration for a single board column."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    status_alias: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate column ID is lowercase with underscores only."""
        if not v[0].isalpha():
            raise ValueError("Column ID must start with a letter")
        if not all(c.isalnum() or c == "_" for c in v):
            raise ValueError("Column ID must be alphanumeric with underscores only")
        if v != v.lower():
            raise ValueError("Column ID must be lowercase")
        return v

    @field_validator("status_alias")
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        """Validate that aliases follow column ID format rules."""
        for alias in v:
            if not alias:
                raise ValueError("Alias cannot be empty")
            if not alias[0].isalpha():
                raise ValueError(f"Alias '{alias}' must start with a letter")
            if not alias.islower():
                raise ValueError(f"Alias '{alias}' must be lowercase")
            if not all(c.isalnum() or c == "_" for c in alias):
                raise ValueError(
                    f"Alias '{alias}' can only contain lowercase letters, numbers, and underscores"
                )
        return v


class BoardConfig(BaseModel):
    """Configuration for board columns."""

    columns: list[ColumnConfig] = Field(..., min_length=2, max_length=6)

    @field_validator("columns")
    @classmethod
    def validate_columns(cls, v: list[ColumnConfig]) -> list[ColumnConfig]:
        """Validate column constraints."""
        ids = [col.id for col in v]

        # Check unique IDs
        if len(ids) != len(set(ids)):
            raise ValueError("Column IDs must be unique")

        # Check reserved IDs
        if "archived" in ids:
            raise ValueError("'archived' is reserved and cannot be used as a column ID")

        # Collect all aliases
        all_aliases: list[str] = []
        for col in v:
            all_aliases.extend(col.status_alias)

        # Check no alias duplicates a column ID
        for alias in all_aliases:
            if alias in ids:
                raise ValueError(f"Alias '{alias}' conflicts with column ID")

        # Check no alias duplicates another alias
        if len(all_aliases) != len(set(all_aliases)):
            raise ValueError("Duplicate alias found across columns")

        # Check no alias is "archived"
        if "archived" in all_aliases:
            raise ValueError("'archived' is reserved and cannot be used as an alias")

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

    def resolve_status(self, status: str) -> str:
        """
        Resolve a status to its canonical column ID.

        If status matches a column ID, returns it unchanged.
        If status matches an alias, returns the column's primary ID.
        If status is unknown, returns it unchanged.
        """
        # Check if it's already a column ID
        if status in self.column_ids:
            return status

        # Check if it's an alias
        for col in self.columns:
            if status in col.status_alias:
                return col.id

        # Unknown status - return unchanged (let caller handle)
        return status

    def get_column_for_status(self, status: str) -> str | None:
        """
        Get the column ID for a status (including aliases).

        Returns None if status is not a valid column ID or alias.
        """
        # Check if it's a column ID
        if status in self.column_ids:
            return status

        # Check if it's "archived"
        if status == "archived":
            return "archived"

        # Check if it's an alias
        for col in self.columns:
            if status in col.status_alias:
                return col.id

        return None

    def is_valid_status(self, status: str) -> bool:
        """Check if status is valid (column ID, alias, or 'archived')."""
        return self.get_column_for_status(status) is not None

    @classmethod
    def default(cls) -> "BoardConfig":
        """Return default 3-column configuration."""
        return cls(
            columns=[
                ColumnConfig(id="todo", title="To Do", status_alias=["new"]),
                ColumnConfig(id="in_progress", title="In Progress"),
                ColumnConfig(
                    id="done",
                    title="Done",
                    status_alias=["completed", "finished", "complete"],
                ),
            ]
        )


class SltasksConfig(BaseModel):
    """Root configuration from sltasks.yml."""

    version: int = 1
    task_root: str = Field(default=".tasks", description="Relative path to tasks directory")
    board: BoardConfig = Field(default_factory=BoardConfig.default)

    @field_validator("task_root")
    @classmethod
    def validate_task_root(cls, v: str) -> str:
        """Validate task_root is a relative path."""
        path = Path(v)
        if path.is_absolute():
            raise ValueError("task_root must be a relative path")
        # Check for path traversal attempts (e.g., "../other")
        try:
            resolved = Path(".").resolve() / path
            resolved.resolve().relative_to(Path(".").resolve())
        except ValueError:
            raise ValueError("task_root must be within the project directory")
        return v

    @classmethod
    def default(cls) -> "SltasksConfig":
        """Return default configuration."""
        return cls(board=BoardConfig.default())
