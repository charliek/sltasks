"""Unit tests for sync filter parser."""

import pytest

from sltasks.sync.filter_parser import (
    FilterParseError,
    ParsedFilter,
    SyncFilterParser,
)


class TestParsedFilter:
    """Tests for ParsedFilter dataclass."""

    def test_default_values(self):
        """ParsedFilter has correct defaults."""
        f = ParsedFilter()
        assert f.assignee is None
        assert f.labels == ()
        assert f.milestone is None
        assert f.state == "open"
        assert f.repo is None
        assert f.is_wildcard is False

    def test_frozen(self):
        """ParsedFilter is immutable."""
        f = ParsedFilter(assignee="test")
        with pytest.raises(AttributeError):  # FrozenInstanceError is subclass of AttributeError
            f.assignee = "other"  # type: ignore


class TestSyncFilterParser:
    """Tests for SyncFilterParser.parse()."""

    @pytest.fixture
    def parser(self) -> SyncFilterParser:
        return SyncFilterParser()

    # --- Wildcard ---

    def test_parse_wildcard(self, parser: SyncFilterParser):
        """Wildcard '*' matches all."""
        f = parser.parse("*")
        assert f.is_wildcard is True
        assert f.state == "all"

    # --- Assignee ---

    def test_parse_assignee_me(self, parser: SyncFilterParser):
        """Parse assignee:@me."""
        f = parser.parse("assignee:@me")
        assert f.assignee == "@me"

    def test_parse_assignee_user(self, parser: SyncFilterParser):
        """Parse assignee:username."""
        f = parser.parse("assignee:octocat")
        assert f.assignee == "octocat"

    # --- Labels ---

    def test_parse_single_label(self, parser: SyncFilterParser):
        """Parse single label."""
        f = parser.parse("label:bug")
        assert f.labels == ("bug",)

    def test_parse_multiple_labels(self, parser: SyncFilterParser):
        """Parse multiple labels (AND'd)."""
        f = parser.parse("label:bug label:urgent")
        assert f.labels == ("bug", "urgent")

    def test_parse_label_with_colon(self, parser: SyncFilterParser):
        """Parse label with quoted value containing special chars."""
        f = parser.parse('label:"type:bug"')
        assert f.labels == ("type:bug",)

    # --- State ---

    def test_parse_is_open(self, parser: SyncFilterParser):
        """Parse is:open."""
        f = parser.parse("is:open")
        assert f.state == "open"

    def test_parse_is_closed(self, parser: SyncFilterParser):
        """Parse is:closed."""
        f = parser.parse("is:closed")
        assert f.state == "closed"

    def test_parse_is_invalid(self, parser: SyncFilterParser):
        """Invalid is: value raises error."""
        with pytest.raises(FilterParseError, match="Invalid is: value"):
            parser.parse("is:invalid")

    # --- Milestone ---

    def test_parse_milestone(self, parser: SyncFilterParser):
        """Parse milestone."""
        f = parser.parse("milestone:v2.0")
        assert f.milestone == "v2.0"

    def test_parse_milestone_quoted(self, parser: SyncFilterParser):
        """Parse milestone with spaces."""
        f = parser.parse('milestone:"Q1 2025"')
        assert f.milestone == "Q1 2025"

    # --- Repository ---

    def test_parse_repo(self, parser: SyncFilterParser):
        """Parse repo filter."""
        f = parser.parse("repo:owner/name")
        assert f.repo == "owner/name"

    def test_parse_repo_invalid(self, parser: SyncFilterParser):
        """Invalid repo format raises error."""
        with pytest.raises(FilterParseError, match="Invalid repo format"):
            parser.parse("repo:invalid")

    # --- Combined ---

    def test_parse_combined_filter(self, parser: SyncFilterParser):
        """Parse multiple criteria together."""
        f = parser.parse("assignee:@me label:bug is:open")
        assert f.assignee == "@me"
        assert f.labels == ("bug",)
        assert f.state == "open"

    def test_parse_complex_filter(self, parser: SyncFilterParser):
        """Parse complex filter with all fields."""
        f = parser.parse(
            'assignee:octocat label:bug label:urgent milestone:"v2.0" is:closed repo:org/repo'
        )
        assert f.assignee == "octocat"
        assert f.labels == ("bug", "urgent")
        assert f.milestone == "v2.0"
        assert f.state == "closed"
        assert f.repo == "org/repo"

    # --- Empty/Whitespace ---

    def test_parse_empty(self, parser: SyncFilterParser):
        """Empty string returns default filter."""
        f = parser.parse("")
        assert f.assignee is None
        assert f.labels == ()
        assert f.state == "open"

    def test_parse_whitespace(self, parser: SyncFilterParser):
        """Whitespace-only string returns default filter."""
        f = parser.parse("   ")
        assert f.assignee is None

    # --- Unknown keys (forward compatibility) ---

    def test_parse_unknown_key_ignored(self, parser: SyncFilterParser):
        """Unknown keys are ignored for forward compatibility."""
        f = parser.parse("assignee:test unknown:value")
        assert f.assignee == "test"


class TestSyncFilterParserMatching:
    """Tests for SyncFilterParser.matches_issue()."""

    @pytest.fixture
    def parser(self) -> SyncFilterParser:
        return SyncFilterParser()

    @pytest.fixture
    def sample_issue(self) -> dict:
        """Sample issue matching common criteria."""
        return {
            "assignees": [{"login": "testuser"}],
            "labels": [{"name": "bug"}, {"name": "urgent"}],
            "milestone": {"title": "v2.0"},
            "state": "OPEN",
            "repository": {"nameWithOwner": "owner/repo"},
        }

    # --- Wildcard ---

    def test_wildcard_matches_everything(self, parser: SyncFilterParser, sample_issue: dict):
        """Wildcard filter matches any issue."""
        f = ParsedFilter(is_wildcard=True)
        assert parser.matches_issue(f, sample_issue, "anyone") is True

    # --- Assignee ---

    def test_assignee_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Direct assignee match."""
        f = ParsedFilter(assignee="testuser")
        assert parser.matches_issue(f, sample_issue, "other") is True

    def test_assignee_me_match(self, parser: SyncFilterParser, sample_issue: dict):
        """@me expands to current user."""
        f = ParsedFilter(assignee="@me")
        assert parser.matches_issue(f, sample_issue, "testuser") is True

    def test_assignee_me_no_match(self, parser: SyncFilterParser, sample_issue: dict):
        """@me doesn't match when current user not assigned."""
        f = ParsedFilter(assignee="@me")
        assert parser.matches_issue(f, sample_issue, "otheruser") is False

    def test_assignee_no_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Assignee filter doesn't match unassigned user."""
        f = ParsedFilter(assignee="nobody")
        assert parser.matches_issue(f, sample_issue, "test") is False

    def test_assignee_empty_list(self, parser: SyncFilterParser):
        """Assignee filter doesn't match issue with no assignees."""
        issue = {"assignees": [], "state": "OPEN"}
        f = ParsedFilter(assignee="anyone")
        assert parser.matches_issue(f, issue, "test") is False

    # --- Labels ---

    def test_label_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Label filter matches."""
        f = ParsedFilter(labels=("bug",))
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_multiple_labels_match(self, parser: SyncFilterParser, sample_issue: dict):
        """All labels must match."""
        f = ParsedFilter(labels=("bug", "urgent"))
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_label_no_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Label filter doesn't match missing label."""
        f = ParsedFilter(labels=("feature",))
        assert parser.matches_issue(f, sample_issue, "test") is False

    def test_multiple_labels_partial_match(self, parser: SyncFilterParser, sample_issue: dict):
        """All labels must match - partial match fails."""
        f = ParsedFilter(labels=("bug", "feature"))
        assert parser.matches_issue(f, sample_issue, "test") is False

    # --- Milestone ---

    def test_milestone_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Milestone filter matches."""
        f = ParsedFilter(milestone="v2.0")
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_milestone_no_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Milestone filter doesn't match different milestone."""
        f = ParsedFilter(milestone="v3.0")
        assert parser.matches_issue(f, sample_issue, "test") is False

    def test_milestone_none(self, parser: SyncFilterParser):
        """Milestone filter doesn't match issue without milestone."""
        issue = {"milestone": None, "state": "OPEN"}
        f = ParsedFilter(milestone="v2.0")
        assert parser.matches_issue(f, issue, "test") is False

    # --- State ---

    def test_state_open_match(self, parser: SyncFilterParser, sample_issue: dict):
        """State open matches open issue."""
        f = ParsedFilter(state="open")
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_state_closed_no_match(self, parser: SyncFilterParser, sample_issue: dict):
        """State closed doesn't match open issue."""
        f = ParsedFilter(state="closed")
        assert parser.matches_issue(f, sample_issue, "test") is False

    def test_state_all_matches(self, parser: SyncFilterParser, sample_issue: dict):
        """State all matches any state."""
        f = ParsedFilter(state="all")
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_state_closed_match(self, parser: SyncFilterParser):
        """State closed matches closed issue."""
        issue = {"state": "CLOSED"}
        f = ParsedFilter(state="closed")
        assert parser.matches_issue(f, issue, "test") is True

    # --- Repository ---

    def test_repo_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Repo filter matches."""
        f = ParsedFilter(repo="owner/repo")
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_repo_case_insensitive(self, parser: SyncFilterParser, sample_issue: dict):
        """Repo match is case insensitive."""
        f = ParsedFilter(repo="Owner/Repo")
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_repo_no_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Repo filter doesn't match different repo."""
        f = ParsedFilter(repo="other/repo")
        assert parser.matches_issue(f, sample_issue, "test") is False

    # --- Combined ---

    def test_combined_all_match(self, parser: SyncFilterParser, sample_issue: dict):
        """Combined filter with all criteria matching."""
        f = ParsedFilter(
            assignee="testuser",
            labels=("bug",),
            milestone="v2.0",
            state="open",
            repo="owner/repo",
        )
        assert parser.matches_issue(f, sample_issue, "test") is True

    def test_combined_one_fails(self, parser: SyncFilterParser, sample_issue: dict):
        """Combined filter fails if one criterion fails."""
        f = ParsedFilter(
            assignee="testuser",
            labels=("bug",),
            milestone="v3.0",  # Doesn't match
        )
        assert parser.matches_issue(f, sample_issue, "test") is False


class TestMatchesAnyFilter:
    """Tests for matches_any_filter (OR logic)."""

    @pytest.fixture
    def parser(self) -> SyncFilterParser:
        return SyncFilterParser()

    @pytest.fixture
    def issue(self) -> dict:
        return {
            "assignees": [{"login": "testuser"}],
            "labels": [{"name": "bug"}],
            "state": "OPEN",
            "repository": {"nameWithOwner": "owner/repo"},
        }

    def test_empty_filters_matches_nothing(self, parser: SyncFilterParser, issue: dict):
        """No filters configured matches nothing."""
        assert parser.matches_any_filter([], issue, "test") is False

    def test_first_filter_matches(self, parser: SyncFilterParser, issue: dict):
        """First filter matches."""
        filters = [
            ParsedFilter(assignee="testuser"),
            ParsedFilter(labels=("feature",)),
        ]
        assert parser.matches_any_filter(filters, issue, "test") is True

    def test_second_filter_matches(self, parser: SyncFilterParser, issue: dict):
        """Second filter matches."""
        filters = [
            ParsedFilter(assignee="nobody"),
            ParsedFilter(labels=("bug",)),
        ]
        assert parser.matches_any_filter(filters, issue, "test") is True

    def test_no_filter_matches(self, parser: SyncFilterParser, issue: dict):
        """No filter matches."""
        filters = [
            ParsedFilter(assignee="nobody"),
            ParsedFilter(labels=("feature",)),
        ]
        assert parser.matches_any_filter(filters, issue, "test") is False

    def test_wildcard_matches_all(self, parser: SyncFilterParser, issue: dict):
        """Wildcard in filter list matches."""
        filters = [
            ParsedFilter(is_wildcard=True),
        ]
        assert parser.matches_any_filter(filters, issue, "test") is True
