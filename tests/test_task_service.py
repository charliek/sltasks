"""Integration tests for TaskService."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from sltasks.models import GitHubProviderData, Task
from sltasks.models.sltasks_config import (
    BoardConfig,
    ColumnConfig,
    GitHubConfig,
    PriorityConfig,
    SltasksConfig,
    TypeConfig,
)
from sltasks.models.task import STATE_IN_PROGRESS, STATE_TODO
from sltasks.repositories import FilesystemRepository
from sltasks.services import TaskService


@pytest.fixture
def task_dir(tmp_path: Path) -> Path:
    """Create a temporary task directory."""
    task_root = tmp_path / ".tasks"
    task_root.mkdir()
    return task_root


@pytest.fixture
def repo(task_dir: Path) -> FilesystemRepository:
    """Create a repository with a temporary directory."""
    return FilesystemRepository(task_dir)


@pytest.fixture
def task_service(repo: FilesystemRepository) -> TaskService:
    """Create a TaskService with the repository."""
    return TaskService(repo)


class TestTaskServiceCreate:
    """Tests for task creation."""

    def test_create_task_basic(self, task_service: TaskService, task_dir: Path):
        """create_task creates a task file with correct defaults."""
        task = task_service.create_task("My New Task")

        assert task.id == "my-new-task.md"
        assert task.title == "My New Task"
        assert task.state == STATE_TODO
        assert task.priority == "medium"
        assert task.created is not None
        assert task.updated is not None
        assert (task_dir / "my-new-task.md").exists()

    def test_create_task_in_specific_state(self, task_service: TaskService):
        """create_task respects state parameter."""
        task = task_service.create_task(
            "In Progress Task",
            state=STATE_IN_PROGRESS,
            priority="high",
        )

        assert task.state == STATE_IN_PROGRESS
        assert task.priority == "high"

    def test_create_task_unique_id_collision(self, task_service: TaskService):
        """Creating tasks with same title generates unique IDs."""
        task1 = task_service.create_task("Fix Bug")
        task2 = task_service.create_task("Fix Bug")

        assert task1.id == "fix-bug.md"
        assert task2.id == "fix-bug-1.md"

    def test_create_task_multiple_collisions(self, task_service: TaskService):
        """Handles 3+ tasks with same title."""
        task1 = task_service.create_task("Same Title")
        task2 = task_service.create_task("Same Title")
        task3 = task_service.create_task("Same Title")

        assert task1.id == "same-title.md"
        assert task2.id == "same-title-1.md"
        assert task3.id == "same-title-2.md"


class TestTaskServiceUpdate:
    """Tests for task updates."""

    def test_update_task_changes_updated_timestamp(
        self, task_service: TaskService, repo: FilesystemRepository
    ):
        """update_task automatically updates the timestamp."""
        task = task_service.create_task("Update Me")
        original_updated = task.updated

        # Modify and update
        task.title = "Updated Title"
        updated_task = task_service.update_task(task)

        assert updated_task.updated > original_updated
        assert updated_task.title == "Updated Title"

        # Verify persisted
        reloaded = repo.get_by_id(task.id)
        assert reloaded.title == "Updated Title"


class TestTaskServiceDelete:
    """Tests for task deletion."""

    def test_delete_task_removes_file(
        self, task_service: TaskService, task_dir: Path, repo: FilesystemRepository
    ):
        """delete_task removes the file and board order entry."""
        task = task_service.create_task("Delete Me")
        task_id = task.id
        assert (task_dir / task_id).exists()

        task_service.delete_task(task_id)

        assert not (task_dir / task_id).exists()
        assert repo.get_by_id(task_id) is None


class TestTaskServiceGet:
    """Tests for task retrieval."""

    def test_get_task_returns_none_for_missing(self, task_service: TaskService):
        """get_task returns None for non-existent task."""
        result = task_service.get_task("nonexistent.md")
        assert result is None


# --- Tests for GitHub task editing with frontmatter ---


@pytest.fixture
def mock_config_service_for_editing():
    """Create a mock config service with GitHub config."""
    service = MagicMock()

    github_config = GitHubConfig(
        project_url="https://github.com/users/testuser/projects/1",
        default_repo="testuser/testrepo",
        featured_labels=["backend", "frontend", "api"],
    )

    board_config = BoardConfig(
        columns=[
            ColumnConfig(id="todo", title="To Do"),
            ColumnConfig(id="in_progress", title="In Progress"),
            ColumnConfig(id="done", title="Done"),
        ],
        types=[
            TypeConfig(id="feature", color="blue"),
            TypeConfig(id="bug", color="red"),
            TypeConfig(id="task", color="white"),
        ],
        priorities=[
            PriorityConfig(id="low", label="Low", color="green"),
            PriorityConfig(id="medium", label="Medium", color="yellow"),
            PriorityConfig(id="high", label="High", color="orange1"),
            PriorityConfig(id="critical", label="Critical", color="red"),
        ],
    )

    config = SltasksConfig(
        provider="github",
        github=github_config,
        board=board_config,
    )

    service.get_config.return_value = config
    service.get_board_config.return_value = board_config

    return service


@pytest.fixture
def github_task_service(repo: FilesystemRepository, mock_config_service_for_editing):
    """Create a TaskService with mock config for GitHub editing tests."""
    return TaskService(repo, config_service=mock_config_service_for_editing)


class TestGetValidOptionsComment:
    """Tests for _get_valid_options_comment helper."""

    def test_priority_options_comment(self, github_task_service):
        """Returns valid priority options comment."""
        comment = github_task_service._get_valid_options_comment("priority")
        assert "# Valid:" in comment
        assert "low" in comment
        assert "medium" in comment
        assert "high" in comment
        assert "critical" in comment

    def test_type_options_comment(self, github_task_service):
        """Returns valid type options comment."""
        comment = github_task_service._get_valid_options_comment("type")
        assert "# Valid:" in comment
        assert "feature" in comment
        assert "bug" in comment
        assert "task" in comment

    def test_state_options_comment(self, github_task_service):
        """Returns valid state options comment."""
        comment = github_task_service._get_valid_options_comment("state")
        assert "# Valid:" in comment
        assert "todo" in comment
        assert "in_progress" in comment
        assert "done" in comment

    def test_tags_options_comment(self, github_task_service):
        """Returns tags options from featured_labels."""
        comment = github_task_service._get_valid_options_comment("tags")
        assert "# Options:" in comment
        assert "backend" in comment
        assert "frontend" in comment
        assert "api" in comment

    def test_no_config_returns_empty(self, task_service):
        """Returns empty string when no config service."""
        comment = task_service._get_valid_options_comment("priority")
        assert comment == ""

    def test_empty_featured_labels_returns_empty(self, repo):
        """Returns empty for tags when no featured_labels configured."""
        service = MagicMock()
        github_config = GitHubConfig(
            project_url="https://github.com/users/testuser/projects/1",
            featured_labels=[],  # Empty
        )
        board_config = BoardConfig.default()
        config = SltasksConfig(provider="github", github=github_config, board=board_config)
        service.get_config.return_value = config
        service.get_board_config.return_value = board_config

        ts = TaskService(repo, config_service=service)
        comment = ts._get_valid_options_comment("tags")
        assert comment == ""


class TestFormatGitHubTaskForEditing:
    """Tests for _format_github_task_for_editing."""

    def test_format_includes_yaml_frontmatter(self, github_task_service):
        """Output includes YAML frontmatter delimiters."""
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="in_progress",
            priority="high",
            type="bug",
            tags=["backend"],
            body="Task body content",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        result = github_task_service._format_github_task_for_editing(task)

        assert result.startswith("---\n")
        assert "\n---\n" in result

    def test_format_includes_editable_fields(self, github_task_service):
        """Output includes title, priority, type, tags."""
        task = Task(
            id="testuser/testrepo#1",
            title="My Task Title",
            state="todo",
            priority="high",
            type="feature",
            tags=["backend", "api"],
            body="Body content",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        result = github_task_service._format_github_task_for_editing(task)

        assert "title: My Task Title" in result
        assert "priority: high" in result
        assert "type: feature" in result
        assert "- backend" in result
        assert "- api" in result

    def test_format_includes_readonly_fields_as_comments(self, github_task_service):
        """Read-only fields are shown as comments."""
        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="in_progress",
            priority="medium",
            created=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            updated=datetime(2025, 1, 2, 12, 0, 0, tzinfo=UTC),
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=42,
            ),
        )

        result = github_task_service._format_github_task_for_editing(task)

        assert "# state: in_progress" in result
        assert "# issue: testuser/testrepo#42" in result
        assert "# created:" in result
        assert "# updated:" in result
        assert "# Read-only fields" in result

    def test_format_includes_valid_options_comments(self, github_task_service):
        """Output includes comments showing valid options."""
        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="todo",
            priority="medium",
            type="bug",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        result = github_task_service._format_github_task_for_editing(task)

        assert "# Valid: low, medium, high, critical" in result
        assert "# Valid: feature, bug, task" in result

    def test_format_includes_body_after_frontmatter(self, github_task_service):
        """Body content appears after frontmatter."""
        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="todo",
            priority="medium",
            body="This is the body content.\n\nWith multiple paragraphs.",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        result = github_task_service._format_github_task_for_editing(task)

        # Body should come after the closing ---
        parts = result.split("---")
        assert len(parts) == 3  # Before first ---, frontmatter, after second ---
        body_section = parts[2]
        assert "This is the body content." in body_section
        assert "With multiple paragraphs." in body_section

    def test_format_empty_tags_shows_empty_list(self, github_task_service):
        """Empty tags shows tags: []."""
        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="todo",
            priority="medium",
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        result = github_task_service._format_github_task_for_editing(task)
        assert "tags: []" in result


class TestParseGitHubTaskFromEditing:
    """Tests for _parse_github_task_from_editing."""

    def test_parse_extracts_all_fields(self, github_task_service):
        """Parsing extracts title, body, priority, type, tags."""
        content = """---
title: Updated Title
priority: critical
type: feature
tags:
  - backend
  - urgent
---

This is the body content.
"""

        result = github_task_service._parse_github_task_from_editing(content)

        assert result["title"] == "Updated Title"
        assert result["priority"] == "critical"
        assert result["type"] == "feature"
        assert result["tags"] == ["backend", "urgent"]
        assert "This is the body content." in result["body"]

    def test_parse_ignores_readonly_comments(self, github_task_service):
        """Commented read-only fields are ignored."""
        content = """---
title: Test
priority: high
type: bug
tags: []
# state: in_progress
# issue: testuser/testrepo#1
# created: '2025-01-01T00:00:00+00:00'
---

Body
"""

        result = github_task_service._parse_github_task_from_editing(content)

        # state should not be in result
        assert "state" not in result
        assert "issue" not in result
        assert "created" not in result

    def test_parse_handles_missing_optional_fields(self, github_task_service):
        """Parsing handles content with minimal fields."""
        content = """---
title: Just a title
---

Body only
"""

        result = github_task_service._parse_github_task_from_editing(content)

        assert result["title"] == "Just a title"
        assert "Body only" in result["body"]
        assert "priority" not in result
        assert "type" not in result
        assert "tags" not in result

    def test_parse_handles_empty_type(self, github_task_service):
        """Empty type value parses as None."""
        content = """---
title: Test
priority: medium
type:
tags: []
---

Body
"""

        result = github_task_service._parse_github_task_from_editing(content)

        assert result["type"] is None

    def test_parse_handles_empty_body(self, github_task_service):
        """Empty body is handled."""
        content = """---
title: Test
priority: medium
---

"""

        result = github_task_service._parse_github_task_from_editing(content)

        assert result["body"] == ""

    def test_parse_preserves_body_formatting(self, github_task_service):
        """Body formatting (newlines, etc.) is preserved."""
        content = """---
title: Test
---

# Heading

- List item 1
- List item 2

```python
code block
```
"""

        result = github_task_service._parse_github_task_from_editing(content)

        assert "# Heading" in result["body"]
        assert "- List item 1" in result["body"]
        assert "```python" in result["body"]
