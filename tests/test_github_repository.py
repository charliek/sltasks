"""Tests for GitHubProjectsRepository."""

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
from sltasks.repositories.github_projects import GitHubProjectsRepository


@pytest.fixture
def mock_config_service():
    """Create a mock config service."""
    service = MagicMock()

    # Default GitHub config
    github_config = GitHubConfig(
        project_url="https://github.com/users/testuser/projects/1",
        default_repo="testuser/testrepo",
    )

    # Default board config - columns must match slugified GitHub Status options
    # GitHub Status options will be: "To Do" -> "to_do", "In Progress" -> "in_progress", "Done" -> "done"
    board_config = BoardConfig(
        columns=[
            ColumnConfig(id="to_do", title="To Do"),
            ColumnConfig(id="in_progress", title="In Progress"),
            ColumnConfig(id="done", title="Done"),
        ],
        types=[
            TypeConfig(id="feature", color="blue"),
            TypeConfig(id="bug", color="red", type_alias=["defect"]),
        ],
        priorities=[
            PriorityConfig(id="low", label="Low", color="green"),
            PriorityConfig(id="medium", label="Medium", color="yellow"),
            PriorityConfig(id="high", label="High", color="orange1"),
        ],
    )

    # Full config
    config = SltasksConfig(
        provider="github",
        github=github_config,
        board=board_config,
    )

    service.get_config.return_value = config
    service.get_board_config.return_value = board_config

    return service


@pytest.fixture
def mock_client():
    """Create a mock GitHub client."""
    return MagicMock()


@pytest.fixture
def repo(mock_config_service, mock_client):
    """Create a repository with mocked dependencies."""
    repo = GitHubProjectsRepository(mock_config_service)
    repo._client = mock_client
    return repo


class TestGitHubProjectsRepositoryValidate:
    """Tests for repository validation."""

    def test_validate_success(self, repo, mock_client):
        """Validate returns True when project is accessible."""
        # Status options must match the board columns after slugification
        # Board has: to_do, in_progress, done
        mock_client.query.return_value = {
            "user": {
                "projectV2": {
                    "id": "PVT_123",
                    "title": "Test Project",
                    "fields": {
                        "nodes": [
                            {
                                "name": "Status",
                                "id": "PVTSSF_123",
                                "options": [
                                    {"id": "opt1", "name": "To Do"},
                                    {"id": "opt2", "name": "In Progress"},
                                    {"id": "opt3", "name": "Done"},
                                ],
                            }
                        ]
                    },
                }
            }
        }

        valid, error = repo.validate()

        assert valid is True
        assert error is None
        assert repo._project_id == "PVT_123"
        assert repo._status_field_id == "PVTSSF_123"

    def test_validate_project_not_found(self, repo, mock_client):
        """Validate returns False when project not found."""
        mock_client.query.return_value = {"user": {"projectV2": None}}

        valid, error = repo.validate()

        assert valid is False
        assert "not found" in error.lower()

    def test_validate_no_status_field(self, repo, mock_client):
        """Validate returns False when Status field is missing."""
        mock_client.query.return_value = {
            "user": {
                "projectV2": {
                    "id": "PVT_123",
                    "title": "Test Project",
                    "fields": {
                        "nodes": [
                            {"name": "Title", "id": "PVTF_title"},
                        ]
                    },
                }
            }
        }

        valid, error = repo.validate()

        assert valid is False
        assert "status field not found" in error.lower()


class TestGitHubProjectsRepositoryGetAll:
    """Tests for get_all method."""

    def test_get_all_maps_issues_to_tasks(self, repo, mock_client):
        """get_all maps GitHub issues to Task objects."""
        # Setup project metadata
        mock_client.query.side_effect = [
            # First call: get project
            {
                "user": {
                    "projectV2": {
                        "id": "PVT_123",
                        "fields": {
                            "nodes": [
                                {
                                    "name": "Status",
                                    "id": "PVTSSF_123",
                                    "options": [
                                        {"id": "opt_todo", "name": "To Do"},
                                        {"id": "opt_done", "name": "Done"},
                                    ],
                                }
                            ]
                        },
                    }
                }
            },
            # Second call: get items
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "fieldValues": {
                                    "nodes": [
                                        {
                                            "field": {"name": "Status"},
                                            "name": "To Do",
                                            "optionId": "opt_todo",
                                        }
                                    ]
                                },
                                "content": {
                                    "id": "I_123",
                                    "number": 1,
                                    "title": "Test Issue",
                                    "body": "Issue body",
                                    "state": "OPEN",
                                    "labels": {"nodes": []},
                                    "createdAt": "2025-01-01T00:00:00Z",
                                    "updatedAt": "2025-01-02T00:00:00Z",
                                    "repository": {"nameWithOwner": "testuser/testrepo"},
                                },
                            }
                        ],
                    }
                }
            },
        ]

        tasks = repo.get_all()

        assert len(tasks) == 1
        task = tasks[0]
        assert task.id == "testuser/testrepo#1"
        assert task.title == "Test Issue"
        assert task.body == "Issue body"
        assert task.state == "to_do"  # "To Do" slugifies to "to_do"
        assert isinstance(task.provider_data, GitHubProviderData)
        assert task.provider_data.issue_number == 1

    def test_get_all_handles_pagination(self, repo, mock_client):
        """get_all handles paginated results."""
        # Setup project metadata and paginated items
        mock_client.query.side_effect = [
            # Project metadata
            {
                "user": {
                    "projectV2": {
                        "id": "PVT_123",
                        "fields": {
                            "nodes": [
                                {
                                    "name": "Status",
                                    "id": "PVTSSF_123",
                                    "options": [{"id": "opt1", "name": "To Do"}],
                                }
                            ]
                        },
                    }
                }
            },
            # First page
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor1"},
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "fieldValues": {"nodes": []},
                                "content": {
                                    "id": "I_1",
                                    "number": 1,
                                    "title": "Issue 1",
                                    "body": "",
                                    "state": "OPEN",
                                    "labels": {"nodes": []},
                                    "createdAt": "2025-01-01T00:00:00Z",
                                    "updatedAt": "2025-01-01T00:00:00Z",
                                    "repository": {"nameWithOwner": "testuser/testrepo"},
                                },
                            }
                        ],
                    }
                }
            },
            # Second page
            {
                "node": {
                    "items": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "PVTI_2",
                                "fieldValues": {"nodes": []},
                                "content": {
                                    "id": "I_2",
                                    "number": 2,
                                    "title": "Issue 2",
                                    "body": "",
                                    "state": "OPEN",
                                    "labels": {"nodes": []},
                                    "createdAt": "2025-01-01T00:00:00Z",
                                    "updatedAt": "2025-01-01T00:00:00Z",
                                    "repository": {"nameWithOwner": "testuser/testrepo"},
                                },
                            }
                        ],
                    }
                }
            },
        ]

        tasks = repo.get_all()

        assert len(tasks) == 2
        assert tasks[0].id == "testuser/testrepo#1"
        assert tasks[1].id == "testuser/testrepo#2"


class TestGitHubProjectsRepositoryStatusMapping:
    """Tests for status/state mapping."""

    def test_map_status_to_state_direct_slugification(self, repo):
        """Status maps to state via direct slugification."""
        # "To Do" -> "to_do", "In Progress" -> "in_progress", "Done" -> "done"
        assert repo._map_status_to_state("To Do") == "to_do"
        assert repo._map_status_to_state("In Progress") == "in_progress"
        assert repo._map_status_to_state("Done") == "done"

    def test_map_status_to_state_handles_variations(self, repo):
        """Status handles various naming conventions."""
        assert repo._map_status_to_state("In review") == "in_review"
        assert repo._map_status_to_state("Ready") == "ready"
        assert repo._map_status_to_state("Backlog") == "backlog"

    def test_map_status_to_state_null_defaults_to_first(self, repo):
        """Null status maps to first column."""
        assert repo._map_status_to_state(None) == "to_do"

    def test_map_state_to_status(self, repo):
        """State maps back to GitHub Status option."""
        # Setup status options
        repo._status_options = {
            "To Do": "opt_todo",
            "In Progress": "opt_ip",
            "Done": "opt_done",
        }

        # "to_do" should find "To Do" since slugify_column_id("To Do") == "to_do"
        assert repo._map_state_to_status("to_do") == "To Do"
        assert repo._map_state_to_status("in_progress") == "In Progress"
        assert repo._map_state_to_status("done") == "Done"
        assert repo._map_state_to_status("unknown") is None


class TestGitHubProjectsRepositoryLabelMapping:
    """Tests for label to type/priority mapping."""

    def test_extract_type_from_labels_direct_match(self, repo):
        """Type extracts from label matching type ID."""
        type_id, label = repo._extract_type_from_labels(["feature", "urgent"])
        assert type_id == "feature"
        assert label == "feature"

    def test_extract_type_from_labels_alias_match(self, repo):
        """Type extracts from label matching type alias."""
        type_id, label = repo._extract_type_from_labels(["defect", "urgent"])
        assert type_id == "bug"
        assert label == "defect"

    def test_extract_type_from_labels_no_match(self, repo):
        """No type when no labels match."""
        type_id, label = repo._extract_type_from_labels(["urgent", "docs"])
        assert type_id is None
        assert label is None

    def test_extract_priority_from_labels_direct_match(self, repo):
        """Priority extracts from label matching priority ID."""
        priority, label = repo._extract_priority_from_labels(["high", "feature"])
        assert priority == "high"
        assert label == "high"

    def test_extract_priority_from_labels_no_match_defaults_medium(self, repo):
        """Priority defaults to medium when no labels match."""
        priority, label = repo._extract_priority_from_labels(["feature", "docs"])
        assert priority == "medium"
        assert label is None


class TestGitHubProjectsRepositorySave:
    """Tests for save method."""

    def test_save_new_task_creates_issue(self, repo, mock_client):
        """save() creates new issue for task without provider_data."""
        # Setup metadata
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        repo._status_options = {"To Do": "opt_todo"}

        # Mock API responses
        mock_client.query.return_value = {
            "repository": {"id": "R_123", "nameWithOwner": "testuser/testrepo"}
        }
        mock_client.mutate.side_effect = [
            # Create issue
            {
                "createIssue": {
                    "issue": {
                        "id": "I_new",
                        "number": 42,
                        "title": "New Issue",
                        "body": "Body content",
                        "createdAt": "2025-01-01T00:00:00Z",
                        "updatedAt": "2025-01-01T00:00:00Z",
                        "repository": {"nameWithOwner": "testuser/testrepo"},
                    }
                }
            },
            # Add to project
            {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}},
            # Update status field
            {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}},
        ]

        task = Task(
            id="temp",
            title="New Issue",
            state="to_do",  # Matches slugified "To Do"
            priority="medium",
            body="Body content",
        )

        result = repo.save(task)

        assert result.id == "testuser/testrepo#42"
        assert isinstance(result.provider_data, GitHubProviderData)
        assert result.provider_data.issue_number == 42

    def test_save_existing_task_updates_issue(self, repo, mock_client):
        """save() updates existing issue."""
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        repo._status_options = {"To Do": "opt_todo", "Done": "opt_done"}

        mock_client.mutate.return_value = {
            "updateIssue": {
                "issue": {
                    "id": "I_123",
                    "number": 1,
                    "title": "Updated",
                    "body": "New body",
                    "updatedAt": "2025-01-02T00:00:00Z",
                }
            }
        }

        task = Task(
            id="testuser/testrepo#1",
            title="Updated Title",
            state="done",
            priority="medium",
            body="New body",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        result = repo.save(task)

        assert result.title == "Updated Title"
        # Verify update mutation was called
        assert mock_client.mutate.call_count >= 1


class TestGitHubProjectsRepositoryDelete:
    """Tests for delete method."""

    def test_delete_closes_issue(self, repo, mock_client):
        """delete() closes the issue."""
        repo._tasks = {
            "testuser/testrepo#1": Task(
                id="testuser/testrepo#1",
                title="Test",
                state="to_do",
                priority="medium",
                provider_data=GitHubProviderData(
                    project_item_id="PVTI_1",
                    issue_node_id="I_123",
                    repository="testuser/testrepo",
                    issue_number=1,
                ),
            )
        }
        repo._board_order = MagicMock()

        mock_client.mutate.return_value = {
            "closeIssue": {"issue": {"id": "I_123", "state": "CLOSED"}}
        }

        repo.delete("testuser/testrepo#1")

        mock_client.mutate.assert_called_once()
        assert "testuser/testrepo#1" not in repo._tasks


class TestGitHubProjectsRepositoryBoardOrder:
    """Tests for board order methods."""

    def test_get_board_order_builds_from_tasks(self, repo):
        """get_board_order builds order from cached tasks."""
        repo._tasks = {
            "testuser/testrepo#1": Task(
                id="testuser/testrepo#1",
                title="Task 1",
                state="to_do",
                priority="medium",
            ),
            "testuser/testrepo#2": Task(
                id="testuser/testrepo#2",
                title="Task 2",
                state="done",
                priority="medium",
            ),
        }

        order = repo.get_board_order()

        assert "testuser/testrepo#1" in order.columns.get("to_do", [])
        assert "testuser/testrepo#2" in order.columns.get("done", [])

    def test_reload_clears_caches(self, repo):
        """reload() clears task and order caches."""
        repo._tasks = {"test": MagicMock()}
        repo._board_order = MagicMock()

        repo.reload()

        assert repo._tasks == {}
        assert repo._board_order is None
