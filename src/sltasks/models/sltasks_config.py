"""Configuration models for sltasks.yml."""

from pydantic import BaseModel, Field, field_validator


class ColumnConfig(BaseModel):
    """Configuration for a single board column."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)

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
        return cls(
            columns=[
                ColumnConfig(id="todo", title="To Do"),
                ColumnConfig(id="in_progress", title="In Progress"),
                ColumnConfig(id="done", title="Done"),
            ]
        )


class SltasksConfig(BaseModel):
    """Root configuration from sltasks.yml."""

    version: int = 1
    board: BoardConfig = Field(default_factory=BoardConfig.default)

    @classmethod
    def default(cls) -> "SltasksConfig":
        """Return default configuration."""
        return cls(board=BoardConfig.default())
