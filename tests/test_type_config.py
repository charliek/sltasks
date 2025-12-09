"""Tests for TypeConfig and BoardConfig.types."""

import pytest
from pydantic import ValidationError

from sltasks.models.sltasks_config import BoardConfig, ColumnConfig, TypeConfig


class TestTypeConfig:
    """Tests for TypeConfig model."""

    def test_valid_type_config(self):
        """Valid type config with all fields."""
        config = TypeConfig(id="feature", template="feature.md", color="blue")
        assert config.id == "feature"
        assert config.template == "feature.md"
        assert config.color == "blue"

    def test_default_template_filename(self):
        """Template defaults to {id}.md."""
        config = TypeConfig(id="bug", color="red")
        assert config.template is None
        assert config.template_filename == "bug.md"

    def test_custom_template_filename(self):
        """Custom template is used when specified."""
        config = TypeConfig(id="bug", template="my-bug-template.md", color="red")
        assert config.template_filename == "my-bug-template.md"

    def test_default_color(self):
        """Color defaults to white."""
        config = TypeConfig(id="task")
        assert config.color == "white"

    def test_invalid_id_uppercase(self):
        """Uppercase ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TypeConfig(id="Feature", color="blue")
        assert "lowercase" in str(exc_info.value)

    def test_invalid_id_starts_with_number(self):
        """ID starting with number is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TypeConfig(id="1feature", color="blue")
        assert "start with a letter" in str(exc_info.value)

    def test_invalid_id_with_hyphen(self):
        """ID with hyphen is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TypeConfig(id="my-type", color="blue")
        assert "alphanumeric" in str(exc_info.value)

    def test_valid_hex_color_6_chars(self):
        """6-character hex colors are valid."""
        config = TypeConfig(id="custom", color="#ff0000")
        assert config.color == "#ff0000"

    def test_valid_hex_color_3_chars(self):
        """3-character hex colors are valid."""
        config = TypeConfig(id="custom", color="#f00")
        assert config.color == "#f00"

    def test_invalid_hex_color_wrong_chars(self):
        """Invalid hex characters are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TypeConfig(id="custom", color="#gggggg")
        assert "Invalid hex color" in str(exc_info.value)

    def test_invalid_hex_color_wrong_length(self):
        """Hex colors with wrong length are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TypeConfig(id="custom", color="#ff00")
        assert "3 or 6 characters" in str(exc_info.value)

    def test_valid_type_alias(self):
        """Valid type aliases are accepted."""
        config = TypeConfig(id="bug", color="red", type_alias=["defect", "issue"])
        assert config.type_alias == ["defect", "issue"]

    def test_invalid_type_alias_uppercase(self):
        """Uppercase type alias is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TypeConfig(id="bug", color="red", type_alias=["Defect"])
        assert "lowercase" in str(exc_info.value)

    def test_invalid_type_alias_empty(self):
        """Empty type alias is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            TypeConfig(id="bug", color="red", type_alias=[""])
        assert "cannot be empty" in str(exc_info.value)


class TestBoardConfigTypes:
    """Tests for types in BoardConfig."""

    def test_default_includes_types(self):
        """Default config includes default types."""
        config = BoardConfig.default()
        assert len(config.types) == 3
        assert "feature" in config.type_ids
        assert "bug" in config.type_ids
        assert "task" in config.type_ids

    def test_default_type_colors(self):
        """Default types have correct colors."""
        config = BoardConfig.default()
        feature = config.get_type("feature")
        bug = config.get_type("bug")
        task = config.get_type("task")
        assert feature.color == "blue"
        assert bug.color == "red"
        assert task.color == "white"

    def test_default_type_aliases(self):
        """Default types have correct aliases."""
        config = BoardConfig.default()
        bug = config.get_type("bug")
        task = config.get_type("task")
        assert "defect" in bug.type_alias
        assert "issue" in bug.type_alias
        assert "chore" in task.type_alias

    def test_get_type(self):
        """get_type returns correct TypeConfig."""
        config = BoardConfig.default()
        feature = config.get_type("feature")
        assert feature is not None
        assert feature.id == "feature"

    def test_get_type_missing(self):
        """get_type returns None for unknown type."""
        config = BoardConfig.default()
        assert config.get_type("unknown") is None

    def test_type_ids_property(self):
        """type_ids returns list of type IDs."""
        config = BoardConfig.default()
        assert config.type_ids == ["feature", "bug", "task"]

    def test_resolve_type_id(self):
        """resolve_type returns ID unchanged for valid type ID."""
        config = BoardConfig.default()
        assert config.resolve_type("feature") == "feature"

    def test_resolve_type_alias(self):
        """resolve_type resolves alias to canonical ID."""
        config = BoardConfig.default()
        assert config.resolve_type("defect") == "bug"
        assert config.resolve_type("issue") == "bug"
        assert config.resolve_type("chore") == "task"

    def test_resolve_type_unknown(self):
        """resolve_type returns unknown type unchanged."""
        config = BoardConfig.default()
        assert config.resolve_type("unknown") == "unknown"

    def test_is_valid_type_id(self):
        """is_valid_type returns True for valid type ID."""
        config = BoardConfig.default()
        assert config.is_valid_type("feature") is True

    def test_is_valid_type_alias(self):
        """is_valid_type returns True for valid alias."""
        config = BoardConfig.default()
        assert config.is_valid_type("defect") is True

    def test_is_valid_type_unknown(self):
        """is_valid_type returns False for unknown type."""
        config = BoardConfig.default()
        assert config.is_valid_type("unknown") is False

    def test_duplicate_type_ids_rejected(self):
        """Duplicate type IDs cause validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BoardConfig(
                columns=[
                    ColumnConfig(id="todo", title="To Do"),
                    ColumnConfig(id="done", title="Done"),
                ],
                types=[
                    TypeConfig(id="feature", color="blue"),
                    TypeConfig(id="feature", color="red"),
                ],
            )
        assert "unique" in str(exc_info.value)

    def test_type_alias_conflicts_with_type_id(self):
        """Type alias conflicting with type ID is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BoardConfig(
                columns=[
                    ColumnConfig(id="todo", title="To Do"),
                    ColumnConfig(id="done", title="Done"),
                ],
                types=[
                    TypeConfig(id="feature", color="blue"),
                    TypeConfig(id="bug", color="red", type_alias=["feature"]),
                ],
            )
        assert "conflicts with type ID" in str(exc_info.value)

    def test_duplicate_type_alias_rejected(self):
        """Duplicate type aliases are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BoardConfig(
                columns=[
                    ColumnConfig(id="todo", title="To Do"),
                    ColumnConfig(id="done", title="Done"),
                ],
                types=[
                    TypeConfig(id="feature", color="blue", type_alias=["dup"]),
                    TypeConfig(id="bug", color="red", type_alias=["dup"]),
                ],
            )
        assert "Duplicate type alias" in str(exc_info.value)

    def test_empty_types_allowed(self):
        """Board config with no types is valid."""
        config = BoardConfig(
            columns=[
                ColumnConfig(id="todo", title="To Do"),
                ColumnConfig(id="done", title="Done"),
            ],
            types=[],
        )
        assert config.types == []
        assert config.type_ids == []
