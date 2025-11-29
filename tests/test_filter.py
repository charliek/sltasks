"""Tests for FilterService."""

import pytest

from kosmos.models import (
    Priority,
    Task,
    STATE_TODO,
    STATE_IN_PROGRESS,
    STATE_DONE,
    STATE_ARCHIVED,
)
from kosmos.services import Filter, FilterService


@pytest.fixture
def filter_service() -> FilterService:
    """Create a FilterService instance."""
    return FilterService()


class TestFilterParsing:
    """Tests for filter expression parsing."""

    def test_empty_expression(self, filter_service: FilterService):
        """Empty expression creates empty filter."""
        f = filter_service.parse("")
        assert f.text is None
        assert f.tags == []
        assert f.exclude_tags == []
        assert f.states == []
        assert f.priorities == []
        assert f.show_archived is False

    def test_free_text(self, filter_service: FilterService):
        """Plain text is captured as free text search."""
        f = filter_service.parse("login bug")
        assert f.text == "login bug"

    def test_single_tag(self, filter_service: FilterService):
        """tag:value is parsed correctly."""
        f = filter_service.parse("tag:bug")
        assert f.tags == ["bug"]
        assert f.text is None

    def test_multiple_tags(self, filter_service: FilterService):
        """Multiple tag: expressions are collected."""
        f = filter_service.parse("tag:bug tag:auth")
        assert f.tags == ["bug", "auth"]

    def test_exclude_tag(self, filter_service: FilterService):
        """-tag:value excludes the tag."""
        f = filter_service.parse("-tag:wontfix")
        assert f.exclude_tags == ["wontfix"]
        assert f.tags == []

    def test_mixed_include_exclude_tags(self, filter_service: FilterService):
        """Can mix include and exclude tags."""
        f = filter_service.parse("tag:bug -tag:wontfix tag:urgent")
        assert f.tags == ["bug", "urgent"]
        assert f.exclude_tags == ["wontfix"]

    def test_state_filter(self, filter_service: FilterService):
        """state:value is parsed correctly."""
        f = filter_service.parse("state:in_progress")
        assert f.states == ["in_progress"]

    def test_multiple_states(self, filter_service: FilterService):
        """Multiple state: expressions are collected."""
        f = filter_service.parse("state:todo state:in_progress")
        assert f.states == ["todo", "in_progress"]

    def test_custom_state_accepted(self, filter_service: FilterService):
        """Custom state values are accepted (for custom columns)."""
        f = filter_service.parse("state:review state:todo")
        assert f.states == ["review", "todo"]

    def test_priority_filter(self, filter_service: FilterService):
        """priority:value is parsed correctly."""
        f = filter_service.parse("priority:high")
        assert f.priorities == [Priority.HIGH]

    def test_multiple_priorities(self, filter_service: FilterService):
        """Multiple priority: expressions are collected."""
        f = filter_service.parse("priority:high priority:critical")
        assert f.priorities == [Priority.HIGH, Priority.CRITICAL]

    def test_invalid_priority_ignored(self, filter_service: FilterService):
        """Invalid priority values are ignored."""
        f = filter_service.parse("priority:invalid priority:low")
        assert f.priorities == [Priority.LOW]

    def test_archived_true(self, filter_service: FilterService):
        """archived:true enables showing archived tasks."""
        f = filter_service.parse("archived:true")
        assert f.show_archived is True

    def test_archived_false(self, filter_service: FilterService):
        """archived:false keeps archived hidden."""
        f = filter_service.parse("archived:false")
        assert f.show_archived is False

    def test_complex_expression(self, filter_service: FilterService):
        """Complex expressions with multiple types."""
        f = filter_service.parse("login tag:bug priority:high state:todo -tag:wontfix")
        assert f.text == "login"
        assert f.tags == ["bug"]
        assert f.exclude_tags == ["wontfix"]
        assert f.priorities == [Priority.HIGH]
        assert f.states == ["todo"]

    def test_case_insensitive_values(self, filter_service: FilterService):
        """Values are lowercased for matching."""
        f = filter_service.parse("tag:BUG priority:HIGH state:TODO")
        assert f.tags == ["bug"]
        assert f.priorities == [Priority.HIGH]
        assert f.states == ["todo"]


class TestFilterApplication:
    """Tests for applying filters to tasks."""

    @pytest.fixture
    def sample_tasks(self) -> list[Task]:
        """Create sample tasks for testing."""
        return [
            Task(
                filename="bug1.md",
                title="Login Bug",
                state=STATE_TODO,
                priority=Priority.HIGH,
                tags=["bug", "auth"],
                body="Users can't login",
            ),
            Task(
                filename="feature1.md",
                title="Add Dark Mode",
                state=STATE_IN_PROGRESS,
                priority=Priority.MEDIUM,
                tags=["feature", "ui"],
                body="Implement dark theme",
            ),
            Task(
                filename="bug2.md",
                title="Crash on Startup",
                state=STATE_TODO,
                priority=Priority.CRITICAL,
                tags=["bug", "critical"],
                body="App crashes immediately",
            ),
            Task(
                filename="done1.md",
                title="Setup CI",
                state=STATE_DONE,
                priority=Priority.LOW,
                tags=["devops"],
                body="Configure GitHub Actions",
            ),
            Task(
                filename="archived1.md",
                title="Old Feature",
                state=STATE_ARCHIVED,
                priority=Priority.MEDIUM,
                tags=["feature"],
                body="Deprecated feature",
            ),
        ]

    def test_empty_filter_excludes_archived(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Empty filter returns all non-archived tasks."""
        f = Filter()
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 4
        assert all(t.state != STATE_ARCHIVED for t in result)

    def test_show_archived(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """show_archived=True includes archived tasks."""
        f = Filter(show_archived=True)
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 5

    def test_text_search_in_title(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Text search matches title."""
        f = Filter(text="login")
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 1
        assert result[0].filename == "bug1.md"

    def test_text_search_in_body(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Text search matches body."""
        f = Filter(text="github")
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 1
        assert result[0].filename == "done1.md"

    def test_text_search_case_insensitive(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Text search is case insensitive."""
        f = Filter(text="LOGIN")
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 1

    def test_tag_filter(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Tag filter matches tasks with the tag."""
        f = Filter(tags=["bug"])
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 2
        filenames = {t.filename for t in result}
        assert filenames == {"bug1.md", "bug2.md"}

    def test_multiple_tags_any_match(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Multiple tags match if ANY tag matches."""
        f = Filter(tags=["auth", "devops"])
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 2
        filenames = {t.filename for t in result}
        assert filenames == {"bug1.md", "done1.md"}

    def test_exclude_tag(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Exclude tag removes matching tasks."""
        f = Filter(tags=["bug"], exclude_tags=["critical"])
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 1
        assert result[0].filename == "bug1.md"

    def test_state_filter(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """State filter matches tasks in that state."""
        f = Filter(states=[STATE_TODO])
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 2
        assert all(t.state == STATE_TODO for t in result)

    def test_multiple_states_any_match(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Multiple states match if ANY state matches."""
        f = Filter(states=[STATE_TODO, STATE_DONE])
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 3

    def test_priority_filter(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Priority filter matches tasks with that priority."""
        f = Filter(priorities=[Priority.HIGH])
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 1
        assert result[0].filename == "bug1.md"

    def test_combined_filters_and(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Multiple filter types are ANDed together."""
        f = Filter(tags=["bug"], states=[STATE_TODO], priorities=[Priority.CRITICAL])
        result = filter_service.apply(sample_tasks, f)
        assert len(result) == 1
        assert result[0].filename == "bug2.md"

    def test_no_matches(
        self, filter_service: FilterService, sample_tasks: list[Task]
    ):
        """Returns empty list when no tasks match."""
        f = Filter(tags=["nonexistent"])
        result = filter_service.apply(sample_tasks, f)
        assert result == []
