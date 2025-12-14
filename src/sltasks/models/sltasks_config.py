"""Configuration models for sltasks.yml."""

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator


def _validate_identifier(value: str, name: str = "ID") -> str:
    """Validate an identifier is lowercase alphanumeric with underscores."""
    if not value:
        raise ValueError(f"{name} cannot be empty")
    if not value[0].isalpha():
        raise ValueError(f"{name} must start with a letter")
    if not all(c.isalnum() or c == "_" for c in value):
        raise ValueError(f"{name} must be alphanumeric with underscores only")
    if value != value.lower():
        raise ValueError(f"{name} must be lowercase")
    return value


def _validate_alias_list(aliases: list[str], alias_type: str = "Alias") -> list[str]:
    """Validate a list of aliases follow identifier format rules."""
    for alias in aliases:
        if not alias:
            raise ValueError(f"{alias_type} cannot be empty")
        if not alias[0].isalpha():
            raise ValueError(f"{alias_type} '{alias}' must start with a letter")
        if not alias.islower():
            raise ValueError(f"{alias_type} '{alias}' must be lowercase")
        if not all(c.isalnum() or c == "_" for c in alias):
            raise ValueError(
                f"{alias_type} '{alias}' can only contain lowercase letters, "
                "numbers, and underscores"
            )
    return aliases


class ColumnConfig(BaseModel):
    """Configuration for a single board column."""

    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    status_alias: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate column ID is lowercase with underscores only."""
        return _validate_identifier(v, "Column ID")

    @field_validator("status_alias")
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        """Validate that aliases follow column ID format rules."""
        return _validate_alias_list(v, "Alias")


class TypeConfig(BaseModel):
    """Configuration for a single task type."""

    id: str = Field(..., min_length=1)
    template: str | None = Field(default=None, description="Template filename")
    color: str = Field(default="white", description="Named color or hex code")
    type_alias: list[str] = Field(default_factory=list)
    canonical_alias: str | None = Field(
        default=None,
        description="Label to use when writing to external systems (defaults to id)",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate type ID is lowercase with underscores only."""
        return _validate_identifier(v, "Type ID")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Validate color is a valid named color or hex code."""
        if v.startswith("#"):
            hex_part = v[1:]
            if len(hex_part) not in (3, 6):
                raise ValueError("Hex color must be 3 or 6 characters (e.g., #fff or #ffffff)")
            if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
                raise ValueError("Invalid hex color code")
        return v

    @field_validator("type_alias")
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        """Validate that type aliases follow identifier format rules."""
        return _validate_alias_list(v, "Type alias")

    @property
    def template_filename(self) -> str:
        """Get the template filename (defaults to {id}.md)."""
        return self.template or f"{self.id}.md"

    @property
    def write_alias(self) -> str:
        """Get the alias to use when writing to external systems.

        Returns canonical_alias if set, otherwise the id.
        """
        return self.canonical_alias or self.id


def _validate_color(v: str) -> str:
    """Validate color is a valid named color or hex code."""
    if v.startswith("#"):
        hex_part = v[1:]
        if len(hex_part) not in (3, 6):
            raise ValueError("Hex color must be 3 or 6 characters (e.g., #fff or #ffffff)")
        if not all(c in "0123456789abcdefABCDEF" for c in hex_part):
            raise ValueError("Invalid hex color code")
    return v


class PriorityConfig(BaseModel):
    """Configuration for a single priority level.

    Priorities are ordered by position in the config list (first = lowest).
    """

    id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1, description="Display label")
    color: str = Field(default="white", description="Named color or hex code")
    symbol: str = Field(default="●", description="Display symbol")
    priority_alias: list[str] = Field(default_factory=list)
    canonical_alias: str | None = Field(
        default=None,
        description="Label to use when writing to external systems (defaults to id)",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate priority ID is lowercase with underscores only."""
        return _validate_identifier(v, "Priority ID")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: str) -> str:
        """Validate color is a valid named color or hex code."""
        return _validate_color(v)

    @field_validator("priority_alias")
    @classmethod
    def validate_aliases(cls, v: list[str]) -> list[str]:
        """Validate that priority aliases follow identifier format rules."""
        return _validate_alias_list(v, "Priority alias")

    @property
    def write_alias(self) -> str:
        """Get the alias to use when writing to external systems.

        Returns canonical_alias if set, otherwise the id.
        """
        return self.canonical_alias or self.id


class BoardConfig(BaseModel):
    """Configuration for board columns, task types, and priorities."""

    columns: list[ColumnConfig] = Field(..., min_length=2, max_length=6)
    types: list[TypeConfig] = Field(default_factory=list)
    priorities: list[PriorityConfig] = Field(default_factory=list)

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

    @field_validator("types")
    @classmethod
    def validate_types(cls, v: list[TypeConfig]) -> list[TypeConfig]:
        """Validate type constraints."""
        ids = [t.id for t in v]

        # Check unique IDs
        if len(ids) != len(set(ids)):
            raise ValueError("Type IDs must be unique")

        # Collect all type aliases
        all_aliases: list[str] = []
        for t in v:
            all_aliases.extend(t.type_alias)

        # Check no alias duplicates a type ID
        for alias in all_aliases:
            if alias in ids:
                raise ValueError(f"Type alias '{alias}' conflicts with type ID")

        # Check no alias duplicates another alias
        if len(all_aliases) != len(set(all_aliases)):
            raise ValueError("Duplicate type alias found")

        return v

    @field_validator("priorities")
    @classmethod
    def validate_priorities(cls, v: list[PriorityConfig]) -> list[PriorityConfig]:
        """Validate priority constraints."""
        ids = [p.id for p in v]

        # Check unique IDs
        if len(ids) != len(set(ids)):
            raise ValueError("Priority IDs must be unique")

        # Collect all priority aliases
        all_aliases: list[str] = []
        for p in v:
            all_aliases.extend(p.priority_alias)

        # Check no alias duplicates a priority ID
        for alias in all_aliases:
            if alias in ids:
                raise ValueError(f"Priority alias '{alias}' conflicts with priority ID")

        # Check no alias duplicates another alias
        if len(all_aliases) != len(set(all_aliases)):
            raise ValueError("Duplicate priority alias found")

        return v

    @property
    def column_ids(self) -> list[str]:
        """List of column IDs in display order."""
        return [col.id for col in self.columns]

    @property
    def type_ids(self) -> list[str]:
        """List of type IDs in display order."""
        return [t.id for t in self.types]

    @property
    def priority_ids(self) -> list[str]:
        """List of priority IDs in order (first = lowest priority)."""
        return [p.id for p in self.priorities]

    def get_title(self, column_id: str) -> str:
        """Get display title for a column ID."""
        for col in self.columns:
            if col.id == column_id:
                return col.title
        return column_id.replace("_", " ").title()

    def get_type(self, type_id: str) -> TypeConfig | None:
        """Get type config by ID."""
        for t in self.types:
            if t.id == type_id:
                return t
        return None

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

    def resolve_type(self, type_value: str) -> str:
        """
        Resolve a type value to its canonical type ID.

        If type_value matches a type ID, returns it unchanged.
        If type_value matches an alias, returns the type's primary ID.
        If type_value is unknown, returns it unchanged.
        """
        # Check if it's already a type ID
        if type_value in self.type_ids:
            return type_value

        # Check if it's an alias
        for t in self.types:
            if type_value in t.type_alias:
                return t.id

        # Unknown type - return unchanged (let caller handle)
        return type_value

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

    def is_valid_type(self, type_value: str) -> bool:
        """Check if type_value is a valid type ID or alias."""
        if type_value in self.type_ids:
            return True
        return any(type_value in t.type_alias for t in self.types)

    def get_priority(self, priority_id: str) -> PriorityConfig | None:
        """Get priority config by ID."""
        for p in self.priorities:
            if p.id == priority_id:
                return p
        return None

    def resolve_priority(self, priority_value: str) -> str:
        """
        Resolve a priority value to its canonical priority ID.

        If priority_value matches a priority ID, returns it unchanged.
        If priority_value matches an alias, returns the priority's primary ID.
        If priority_value is unknown, returns it unchanged.
        """
        # Check if it's already a priority ID
        if priority_value in self.priority_ids:
            return priority_value

        # Check if it's an alias
        for p in self.priorities:
            if priority_value in p.priority_alias:
                return p.id

        # Unknown priority - return unchanged (let caller handle)
        return priority_value

    def get_priority_rank(self, priority_id: str) -> int:
        """
        Get the rank/order of a priority (position in list).

        Lower values = lower priority. Returns -1 if not found.
        """
        resolved = self.resolve_priority(priority_id)
        try:
            return self.priority_ids.index(resolved)
        except ValueError:
            return -1

    def is_valid_priority(self, priority_value: str) -> bool:
        """Check if priority_value is a valid priority ID or alias."""
        if priority_value in self.priority_ids:
            return True
        return any(priority_value in p.priority_alias for p in self.priorities)

    @classmethod
    def default(cls) -> "BoardConfig":
        """Return default 3-column configuration with default types and priorities."""
        return cls(
            columns=[
                ColumnConfig(id="todo", title="To Do", status_alias=["new"]),
                ColumnConfig(id="in_progress", title="In Progress"),
                ColumnConfig(
                    id="done",
                    title="Done",
                    status_alias=["completed", "finished", "complete"],
                ),
            ],
            types=[
                TypeConfig(id="feature", color="blue"),
                TypeConfig(id="bug", color="red", type_alias=["defect", "issue"]),
                TypeConfig(id="task", color="white", type_alias=["chore"]),
            ],
            priorities=[
                PriorityConfig(
                    id="low",
                    label="Low",
                    color="green",
                    priority_alias=["trivial", "minor"],
                ),
                PriorityConfig(id="medium", label="Medium", color="yellow"),
                PriorityConfig(
                    id="high",
                    label="High",
                    color="orange1",
                    priority_alias=["important"],
                ),
                PriorityConfig(
                    id="critical",
                    label="Critical",
                    color="red",
                    priority_alias=["blocker", "urgent"],
                ),
            ],
        )


class SltasksConfig(BaseModel):
    """Root configuration from sltasks.yml."""

    version: int = 1
    provider: str = Field(
        default="file",
        description="Storage provider: file, github, github-prs, jira",
    )
    task_root: str = Field(default=".tasks", description="Relative path to tasks directory")
    board: BoardConfig = Field(default_factory=BoardConfig.default)

    # Valid provider values
    VALID_PROVIDERS: ClassVar[tuple[str, ...]] = ("file", "github", "github-prs", "jira")

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate provider is a supported value."""
        if v not in cls.VALID_PROVIDERS:
            raise ValueError(
                f"Invalid provider '{v}'. Must be one of: {', '.join(cls.VALID_PROVIDERS)}"
            )
        return v

    @field_validator("task_root")
    @classmethod
    def validate_task_root(cls, v: str) -> str:
        """Validate task_root is a relative path."""
        path = Path(v)
        if path.is_absolute():
            raise ValueError("task_root must be a relative path")
        # Check for path traversal attempts (e.g., "../other")
        try:
            resolved = Path().resolve() / path
            resolved.resolve().relative_to(Path().resolve())
        except ValueError as err:
            raise ValueError("task_root must be within the project directory") from err
        return v

    @classmethod
    def default(cls) -> "SltasksConfig":
        """Return default configuration."""
        return cls(provider="file", board=BoardConfig.default())
