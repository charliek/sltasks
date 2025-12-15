"""Unit tests for sync file mapper utilities."""

from sltasks.sync.file_mapper import (
    generate_synced_filename,
    is_local_only_filename,
    is_synced_filename,
    parse_synced_filename,
)


class TestGenerateSyncedFilename:
    """Tests for generate_synced_filename function."""

    def test_basic_generation(self):
        """Generate filename from basic inputs."""
        filename = generate_synced_filename("acme", "project", 123, "Fix login bug")
        assert filename == "acme-project#123-fix-login-bug.md"

    def test_with_special_characters_in_title(self):
        """Title with special characters is slugified."""
        filename = generate_synced_filename("owner", "repo", 456, "Fix Bug! (urgent)")
        assert filename == "owner-repo#456-fix-bug-urgent.md"

    def test_with_empty_title(self):
        """Empty title results in 'untitled' slug."""
        filename = generate_synced_filename("owner", "repo", 789, "")
        assert filename == "owner-repo#789-untitled.md"

    def test_with_whitespace_only_title(self):
        """Whitespace-only title results in 'untitled' slug."""
        filename = generate_synced_filename("owner", "repo", 1, "   ")
        assert filename == "owner-repo#1-untitled.md"

    def test_with_hyphenated_owner(self):
        """Owner with hyphens is preserved."""
        filename = generate_synced_filename("my-org", "my-repo", 42, "Test issue")
        assert filename == "my-org-my-repo#42-test-issue.md"

    def test_with_numbers_in_names(self):
        """Numbers in owner/repo are preserved."""
        filename = generate_synced_filename("user123", "project456", 1, "Test")
        assert filename == "user123-project456#1-test.md"


class TestParseSyncedFilename:
    """Tests for parse_synced_filename function."""

    def test_parse_basic_filename(self):
        """Parse a basic synced filename."""
        result = parse_synced_filename("acme-project#123-fix-login-bug.md")
        assert result is not None
        assert result.owner == "acme"
        assert result.repo == "project"
        assert result.issue_number == 123
        assert result.slug == "fix-login-bug"

    def test_parse_hyphenated_names(self):
        """Parse filename with hyphenated owner/repo."""
        result = parse_synced_filename("my-org-my-repo#456-test-issue.md")
        assert result is not None
        # Note: regex is greedy, matching up to the last hyphen before #
        # So "my-org-my-repo" becomes owner="my-org-my", repo="repo"
        # This is a known limitation with hyphenated names
        assert result.owner == "my-org-my"
        assert result.repo == "repo"
        assert result.issue_number == 456

    def test_parse_returns_none_for_non_synced(self):
        """Non-synced filenames return None."""
        result = parse_synced_filename("fix-login-bug.md")
        assert result is None

    def test_parse_returns_none_for_non_md(self):
        """Non-.md files return None."""
        result = parse_synced_filename("acme-project#123-test.txt")
        assert result is None

    def test_parse_returns_none_for_invalid_format(self):
        """Invalid format returns None."""
        assert parse_synced_filename("no-hash.md") is None
        assert parse_synced_filename("acme#123.md") is None  # Missing repo
        assert parse_synced_filename("") is None

    def test_parsed_filename_properties(self):
        """ParsedSyncedFilename has correct properties."""
        result = parse_synced_filename("owner-repo#42-slug.md")
        assert result is not None
        assert result.repository == "owner/repo"
        assert result.issue_id == "owner/repo#42"


class TestIsSyncedFilename:
    """Tests for is_synced_filename function."""

    def test_synced_filename(self):
        """Synced filenames are recognized."""
        assert is_synced_filename("owner-repo#123-slug.md") is True
        assert is_synced_filename("my-org-my-repo#1-test.md") is True

    def test_non_synced_filename(self):
        """Non-synced filenames are not recognized."""
        assert is_synced_filename("fix-bug.md") is False
        assert is_synced_filename("readme.md") is False
        assert is_synced_filename("UPPERCASE.md") is False

    def test_invalid_patterns(self):
        """Invalid patterns return False."""
        assert is_synced_filename("") is False
        assert is_synced_filename("owner#123.md") is False  # Missing repo
        assert is_synced_filename("owner-repo#abc-slug.md") is False  # Non-numeric issue


class TestIsLocalOnlyFilename:
    """Tests for is_local_only_filename function."""

    def test_local_only_filenames(self):
        """Local-only .md files are recognized."""
        assert is_local_only_filename("fix-bug.md") is True
        assert is_local_only_filename("add-feature.md") is True
        assert is_local_only_filename("readme.md") is True

    def test_synced_filenames_not_local_only(self):
        """Synced filenames are not local-only."""
        assert is_local_only_filename("owner-repo#123-slug.md") is False

    def test_non_md_files_not_local_only(self):
        """Non-.md files are not local-only."""
        assert is_local_only_filename("readme.txt") is False
        assert is_local_only_filename("task.yaml") is False
        assert is_local_only_filename("config.json") is False

    def test_empty_filename(self):
        """Empty filename is not local-only."""
        assert is_local_only_filename("") is False
