"""Tests for slug generation utilities."""

from sltasks.utils.slug import generate_filename, slugify, slugify_column_id


class TestSlugify:
    """Tests for the slugify function."""

    def test_basic_text(self):
        """Simple text is lowercased and spaces become hyphens."""
        assert slugify("Hello World") == "hello-world"

    def test_special_characters_removed(self):
        """Special characters are removed."""
        assert slugify("Fix Login Bug!") == "fix-login-bug"
        assert slugify("What's up?") == "whats-up"
        assert slugify("Test @#$% chars") == "test-chars"

    def test_underscores_become_hyphens(self):
        """Underscores are converted to hyphens."""
        assert slugify("hello_world") == "hello-world"

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces become a single hyphen."""
        assert slugify("hello   world") == "hello-world"

    def test_multiple_hyphens_collapsed(self):
        """Multiple hyphens are collapsed to one."""
        assert slugify("hello---world") == "hello-world"
        assert slugify("hello - - world") == "hello-world"

    def test_leading_trailing_hyphens_removed(self):
        """Leading and trailing hyphens are stripped."""
        assert slugify("  hello world  ") == "hello-world"
        assert slugify("---hello---") == "hello"

    def test_unicode_normalized(self):
        """Unicode characters are normalized to ASCII."""
        assert slugify("café") == "cafe"
        assert slugify("naïve") == "naive"
        assert slugify("résumé") == "resume"

    def test_numbers_preserved(self):
        """Numbers are preserved in the slug."""
        assert slugify("version 2.0") == "version-20"
        assert slugify("task123") == "task123"

    def test_empty_result(self):
        """All-special-character input produces empty string."""
        assert slugify("@#$%") == ""
        assert slugify("   ") == ""

    def test_already_slug(self):
        """Already-valid slugs are unchanged."""
        assert slugify("hello-world") == "hello-world"
        assert slugify("fix-login-bug") == "fix-login-bug"


class TestGenerateFilename:
    """Tests for the generate_filename function."""

    def test_basic_title(self):
        """Basic title generates expected filename."""
        assert generate_filename("Fix Login Bug") == "fix-login-bug.md"

    def test_adds_md_extension(self):
        """Filename always ends with .md."""
        assert generate_filename("My Task").endswith(".md")

    def test_empty_title(self):
        """Empty or all-special-char title becomes 'untitled.md'."""
        assert generate_filename("") == "untitled.md"
        assert generate_filename("@#$%") == "untitled.md"

    def test_special_characters(self):
        """Special characters are handled correctly."""
        assert generate_filename("What's the plan?") == "whats-the-plan.md"


class TestSlugifyColumnId:
    """Tests for the slugify_column_id function."""

    def test_basic_conversion(self):
        """Basic text with spaces converts to underscores."""
        assert slugify_column_id("In progress") == "in_progress"
        assert slugify_column_id("In Progress") == "in_progress"

    def test_simple_word(self):
        """Single word is just lowercased."""
        assert slugify_column_id("Ready") == "ready"
        assert slugify_column_id("DONE") == "done"
        assert slugify_column_id("Backlog") == "backlog"

    def test_multiple_words(self):
        """Multiple words get underscores."""
        assert slugify_column_id("In Review") == "in_review"
        assert slugify_column_id("To Do") == "to_do"
        assert slugify_column_id("On Hold") == "on_hold"

    def test_unicode_removed(self):
        """Unicode characters are stripped."""
        assert slugify_column_id("Done ✓") == "done"
        assert slugify_column_id("Ready ⭐") == "ready"
        assert slugify_column_id("🚀 Launch") == "launch"

    def test_numeric_prefix(self):
        """IDs starting with numbers get 'col_' prefix."""
        assert slugify_column_id("123 Numbers") == "col_123_numbers"
        assert slugify_column_id("1st Priority") == "col_1st_priority"
        assert slugify_column_id("42") == "col_42"

    def test_hyphens_become_underscores(self):
        """Hyphens are converted to underscores."""
        assert slugify_column_id("in-progress") == "in_progress"
        assert slugify_column_id("to-do") == "to_do"

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces become single underscore."""
        assert slugify_column_id("In   Progress") == "in_progress"

    def test_special_characters_removed(self):
        """Special characters are removed."""
        assert slugify_column_id("In Progress!") == "in_progress"
        assert slugify_column_id("Ready?") == "ready"
        assert slugify_column_id("Test@#$%") == "test"

    def test_empty_or_special_only(self):
        """Empty or all-special input returns 'unknown'."""
        assert slugify_column_id("") == "unknown"
        assert slugify_column_id("@#$%") == "unknown"
        assert slugify_column_id("✓✓✓") == "unknown"

    def test_already_valid_id(self):
        """Already valid IDs are unchanged."""
        assert slugify_column_id("todo") == "todo"
        assert slugify_column_id("in_progress") == "in_progress"
        assert slugify_column_id("done") == "done"

    def test_leading_trailing_underscores_stripped(self):
        """Leading and trailing underscores are removed."""
        assert slugify_column_id("  Ready  ") == "ready"
        assert slugify_column_id("_todo_") == "todo"

    def test_accented_characters(self):
        """Accented characters are normalized."""
        assert slugify_column_id("Prêt") == "pret"
        assert slugify_column_id("À faire") == "a_faire"
