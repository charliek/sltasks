"""Tests for GitHubProjectsRepository."""

from unittest.mock import MagicMock

import pytest

from sltasks.models import BoardOrder, GitHubProviderData, Task
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

    def test_get_all_extracts_assignees(self, repo, mock_client):
        """get_all extracts assignees from GitHub issues."""
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
                                    "options": [{"id": "opt_todo", "name": "To Do"}],
                                }
                            ]
                        },
                    }
                }
            },
            # Second call: get items with assignees
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
                                    "assignees": {
                                        "nodes": [
                                            {"login": "alice"},
                                            {"login": "bob"},
                                        ]
                                    },
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
        assert task.assignees == ["alice", "bob"]

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

    def test_extract_priority_from_labels_no_match_returns_none(self, repo):
        """Priority returns None when no labels match."""
        priority, label = repo._extract_priority_from_labels(["feature", "docs"])
        assert priority is None
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


class TestGitHubReorderTask:
    """Tests for GitHub Projects task reordering."""

    def test_reorder_task_moves_down_and_calls_api(self, repo, mock_client):
        """Verify reorder_task with delta=1 moves task down and calls API."""
        task1 = Task(
            id="testuser/testrepo#1",
            title="Task 1",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_item1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        task2 = Task(
            id="testuser/testrepo#2",
            title="Task 2",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_item2",
                issue_node_id="I_456",
                repository="testuser/testrepo",
                issue_number=2,
            ),
        )
        repo._tasks = {
            "testuser/testrepo#1": task1,
            "testuser/testrepo#2": task2,
        }
        repo._project_id = "PVT_project"
        # Set up board order: task1, task2
        repo._board_order = BoardOrder(
            columns={"to_do": ["testuser/testrepo#1", "testuser/testrepo#2"]}
        )

        # Move task1 down (delta=1)
        result = repo.reorder_task("testuser/testrepo#1", 1)

        assert result is True
        # After swap: task2, task1 - so task1 should be after task2
        mock_client.mutate.assert_called_once()
        call_args = mock_client.mutate.call_args
        assert call_args[0][1]["projectId"] == "PVT_project"
        assert call_args[0][1]["itemId"] == "PVTI_item1"
        assert call_args[0][1]["afterId"] == "PVTI_item2"
        # Verify board order was updated
        assert repo._board_order.columns["to_do"] == ["testuser/testrepo#2", "testuser/testrepo#1"]

    def test_reorder_task_moves_up_to_first_position(self, repo, mock_client):
        """Verify afterId is None when moving to first position."""
        task1 = Task(
            id="testuser/testrepo#1",
            title="Task 1",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_item1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        task2 = Task(
            id="testuser/testrepo#2",
            title="Task 2",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_item2",
                issue_node_id="I_456",
                repository="testuser/testrepo",
                issue_number=2,
            ),
        )
        repo._tasks = {
            "testuser/testrepo#1": task1,
            "testuser/testrepo#2": task2,
        }
        repo._project_id = "PVT_project"
        # Set up board order: task1, task2
        repo._board_order = BoardOrder(
            columns={"to_do": ["testuser/testrepo#1", "testuser/testrepo#2"]}
        )

        # Move task2 up (delta=-1) to first position
        result = repo.reorder_task("testuser/testrepo#2", -1)

        assert result is True
        call_args = mock_client.mutate.call_args
        # task2 is now at index 0, so afterId should be None
        assert call_args[0][1]["afterId"] is None
        # Verify board order was updated
        assert repo._board_order.columns["to_do"] == ["testuser/testrepo#2", "testuser/testrepo#1"]

    def test_reorder_task_with_invalid_task_returns_false(self, repo):
        """Verify returns False if task not found."""
        # Add a dummy task so _tasks is truthy (prevents get_all() call)
        dummy_task = Task(
            id="dummy",
            title="Dummy",
            state="to_do",
            priority="medium",
        )
        repo._tasks = {"dummy": dummy_task}
        repo._board_order = BoardOrder(columns={"to_do": ["dummy"]})

        result = repo.reorder_task("nonexistent", -1)

        assert result is False

    def test_reorder_task_at_boundary_returns_false(self, repo, mock_client):
        """Verify returns False when at boundary (can't move further)."""
        task = Task(
            id="testuser/testrepo#1",
            title="Task 1",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_item1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        repo._tasks = {"testuser/testrepo#1": task}
        repo._project_id = "PVT_project"
        repo._board_order = BoardOrder(columns={"to_do": ["testuser/testrepo#1"]})

        # Try to move up when already at top
        result = repo.reorder_task("testuser/testrepo#1", -1)

        assert result is False
        # API should not be called
        mock_client.mutate.assert_not_called()


class TestGitHubFetchRepoLabels:
    """Tests for _fetch_repo_labels method."""

    def test_fetch_repo_labels_returns_label_map(self, repo, mock_client):
        """_fetch_repo_labels returns dict mapping label name to ID."""
        mock_client.query.return_value = {
            "repository": {
                "labels": {
                    "nodes": [
                        {"id": "LA_123", "name": "bug"},
                        {"id": "LA_456", "name": "feature"},
                        {"id": "LA_789", "name": "high"},
                    ]
                }
            }
        }

        result = repo._fetch_repo_labels("testuser/testrepo")

        assert result == {
            "bug": "LA_123",
            "feature": "LA_456",
            "high": "LA_789",
        }

    def test_fetch_repo_labels_caches_result(self, repo, mock_client):
        """_fetch_repo_labels caches and reuses results."""
        mock_client.query.return_value = {
            "repository": {"labels": {"nodes": [{"id": "LA_123", "name": "bug"}]}}
        }

        # First call
        result1 = repo._fetch_repo_labels("testuser/testrepo")
        # Second call should use cache
        result2 = repo._fetch_repo_labels("testuser/testrepo")

        assert result1 == result2
        assert mock_client.query.call_count == 1  # Only called once

    def test_fetch_repo_labels_handles_api_error(self, repo, mock_client):
        """_fetch_repo_labels returns empty dict on API error."""
        from sltasks.github import GitHubClientError

        mock_client.query.side_effect = GitHubClientError("API error")

        result = repo._fetch_repo_labels("testuser/testrepo")

        assert result == {}


class TestGitHubComputeLabelChanges:
    """Tests for _compute_label_changes method."""

    def test_compute_type_label_change(self, repo):
        """Computes correct add/remove when type changes."""
        old_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            type="bug",
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label="bug",
                priority_label=None,
            ),
        )

        new_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            type="feature",
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label="bug",  # Still has old label tracked
                priority_label=None,
            ),
        )

        labels_to_add, labels_to_remove = repo._compute_label_changes(new_task, old_task)

        assert "feature" in labels_to_add
        assert "bug" in labels_to_remove

    def test_compute_priority_label_change_when_no_priority_field(self, repo):
        """Computes priority label changes when not using priority field."""
        # Ensure no priority_field is configured (default fixture has none)
        old_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            type=None,
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label=None,
                priority_label="medium",
            ),
        )

        new_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="high",
            type=None,
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label=None,
                priority_label="medium",  # Old label still tracked
            ),
        )

        labels_to_add, labels_to_remove = repo._compute_label_changes(new_task, old_task)

        assert "high" in labels_to_add
        assert "medium" in labels_to_remove

    def test_compute_tag_additions(self, repo):
        """Computes new tags to add."""
        old_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            tags=["backend"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        new_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            tags=["backend", "urgent", "api"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        labels_to_add, _labels_to_remove = repo._compute_label_changes(new_task, old_task)

        assert "urgent" in labels_to_add
        assert "api" in labels_to_add
        assert "backend" not in labels_to_add

    def test_compute_tag_removals(self, repo):
        """Computes tags to remove."""
        old_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            tags=["backend", "urgent", "api"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        new_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            tags=["backend"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        _labels_to_add, labels_to_remove = repo._compute_label_changes(new_task, old_task)

        assert "urgent" in labels_to_remove
        assert "api" in labels_to_remove
        assert "backend" not in labels_to_remove

    def test_compute_no_changes(self, repo):
        """Returns empty lists when no label changes."""
        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            type="bug",
            tags=["backend"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label="bug",
                priority_label="medium",  # Must match current priority
            ),
        )

        labels_to_add, labels_to_remove = repo._compute_label_changes(task, task)

        assert labels_to_add == []
        assert labels_to_remove == []


class TestGitHubUpdateLabels:
    """Tests for _update_labels method."""

    def test_update_labels_adds_labels(self, repo, mock_client):
        """_update_labels calls ADD_LABELS mutation."""
        repo._repo_labels = {"testuser/testrepo": {"urgent": "LA_urgent", "api": "LA_api"}}

        repo._update_labels(
            issue_node_id="I_123",
            repository="testuser/testrepo",
            labels_to_add=["urgent", "api"],
            labels_to_remove=[],
        )

        # Check ADD_LABELS was called
        add_call = None
        for call in mock_client.mutate.call_args_list:
            if "addLabelsToLabelable" in call[0][0]:
                add_call = call
                break

        assert add_call is not None
        assert set(add_call[0][1]["labelIds"]) == {"LA_urgent", "LA_api"}

    def test_update_labels_removes_labels(self, repo, mock_client):
        """_update_labels calls REMOVE_LABELS mutation."""
        repo._repo_labels = {"testuser/testrepo": {"old_label": "LA_old"}}

        repo._update_labels(
            issue_node_id="I_123",
            repository="testuser/testrepo",
            labels_to_add=[],
            labels_to_remove=["old_label"],
        )

        # Check REMOVE_LABELS was called
        remove_call = None
        for call in mock_client.mutate.call_args_list:
            if "removeLabelsFromLabelable" in call[0][0]:
                remove_call = call
                break

        assert remove_call is not None
        assert remove_call[0][1]["labelIds"] == ["LA_old"]

    def test_update_labels_skips_unknown_labels(self, repo, mock_client):
        """_update_labels skips labels not found in repo."""
        repo._repo_labels = {"testuser/testrepo": {"known": "LA_known"}}

        repo._update_labels(
            issue_node_id="I_123",
            repository="testuser/testrepo",
            labels_to_add=["known", "unknown"],
            labels_to_remove=[],
        )

        # Should only add the known label
        add_call = mock_client.mutate.call_args
        assert add_call[0][1]["labelIds"] == ["LA_known"]

    def test_update_labels_no_op_when_empty(self, repo, mock_client):
        """_update_labels does nothing when no changes."""
        repo._update_labels(
            issue_node_id="I_123",
            repository="testuser/testrepo",
            labels_to_add=[],
            labels_to_remove=[],
        )

        mock_client.mutate.assert_not_called()


class TestGitHubUpdatePriorityField:
    """Tests for _update_priority_field method."""

    def test_update_priority_field_when_configured(self, mock_config_service, mock_client):
        """_update_priority_field updates field when priority_field is set."""
        # Configure priority field
        github_config = mock_config_service.get_config.return_value.github
        github_config.priority_field = "Priority"

        repo = GitHubProjectsRepository(mock_config_service)
        repo._client = mock_client
        repo._project_id = "PVT_123"
        repo._priority_field_id = "PVTSSF_priority"
        repo._priority_options = {
            "Low": "opt_low",
            "Medium": "opt_medium",
            "High": "opt_high",
        }
        repo._priority_options_ordered = ["Low", "Medium", "High"]

        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="high",  # Index 2 in board config priorities
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        repo._update_priority_field(task)

        mock_client.mutate.assert_called_once()
        call_args = mock_client.mutate.call_args
        assert call_args[0][1]["fieldId"] == "PVTSSF_priority"
        assert call_args[0][1]["optionId"] == "opt_high"

    def test_update_priority_field_no_op_when_not_configured(self, repo, mock_client):
        """_update_priority_field does nothing when priority_field not set."""
        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="high",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        repo._update_priority_field(task)

        mock_client.mutate.assert_not_called()


class TestGitHubUpdateIssueWithLabels:
    """Tests for _update_issue with label support."""

    def test_update_issue_updates_labels(self, repo, mock_client):
        """_update_issue calls label update methods."""
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        repo._status_options = {"To Do": "opt_todo"}
        repo._repo_labels = {
            "testuser/testrepo": {
                "bug": "LA_bug",
                "feature": "LA_feature",
            }
        }

        # Old task in cache with type=bug
        old_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            type="bug",
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label="bug",
            ),
        )
        repo._tasks = {"testuser/testrepo#1": old_task}

        # New task with type=feature
        new_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            type="feature",
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label="bug",
            ),
        )

        repo._update_issue(new_task)

        # Should have called mutations for labels
        mutation_calls = [call[0][0] for call in mock_client.mutate.call_args_list]

        # Should have called UPDATE_ISSUE and label mutations
        assert any("updateIssue" in call for call in mutation_calls)

    def test_update_issue_updates_provider_data_labels(self, repo):
        """_update_issue updates provider_data with new label tracking."""
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        repo._status_options = {"To Do": "opt_todo"}
        repo._repo_labels = {"testuser/testrepo": {"feature": "LA_feature"}}

        task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            type="feature",
            tags=[],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
                type_label=None,  # Was not set before
            ),
        )

        result = repo._update_issue(task)

        # Provider data should now track the type label
        assert result.provider_data.type_label == "feature"


class TestGitHubReturnsCopies:
    """Tests for repository methods returning copies to prevent cache mutation.

    With frozen Task model, these tests verify that returned tasks are separate
    instances from cached tasks, enabling proper old-vs-new comparison during save.
    """

    def test_get_by_id_returns_separate_instance(self, repo):
        """get_by_id returns a separate instance, not the cached task."""
        # Setup: populate the cache with a task
        original_task = Task(
            id="testuser/testrepo#1",
            title="Original Title",
            state="to_do",
            priority="medium",
            tags=["tag1", "tag2"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        repo._tasks = {"testuser/testrepo#1": original_task}

        # Get the task
        returned_task = repo.get_by_id("testuser/testrepo#1")

        # Verify it's a separate instance (different object identity)
        cached_task = repo._tasks["testuser/testrepo#1"]
        assert returned_task is not cached_task
        # But has the same values
        assert returned_task.title == cached_task.title
        assert returned_task.tags == cached_task.tags

    def test_get_all_returns_separate_instances(self, repo):
        """_sorted_tasks returns separate instances, not cached tasks."""
        # Setup: populate the cache with tasks
        original_task = Task(
            id="testuser/testrepo#1",
            title="Original Title",
            state="to_do",
            priority="medium",
            tags=["tag1", "tag2"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        repo._tasks = {"testuser/testrepo#1": original_task}
        repo._project_id = "PVT_123"  # Prevent fetch

        # Get all tasks (uses _sorted_tasks internally)
        tasks = repo._sorted_tasks()

        # Verify returned task is a separate instance
        cached_task = repo._tasks["testuser/testrepo#1"]
        assert tasks[0] is not cached_task
        # But has the same values
        assert tasks[0].title == cached_task.title
        assert tasks[0].tags == cached_task.tags

    def test_tag_changes_detected_with_model_copy(self, repo):
        """Tag changes are correctly detected when using model_copy for updates."""
        # Setup cache with original task
        original_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            tags=["old-tag"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        repo._tasks = {"testuser/testrepo#1": original_task}
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        repo._status_options = {"To Do": "opt_todo"}
        repo._repo_labels = {"testuser/testrepo": {"new-tag": "LA_newtag", "old-tag": "LA_oldtag"}}

        # Get task (returns copy), create updated version with model_copy
        task = repo.get_by_id("testuser/testrepo#1")
        updated_task = task.model_copy(update={"tags": ["new-tag"]})

        # Compute label changes - old_task from cache should have ["old-tag"]
        old_task = repo._tasks.get("testuser/testrepo#1")
        labels_to_add, labels_to_remove = repo._compute_label_changes(updated_task, old_task)

        # Should detect the tag change
        assert "new-tag" in labels_to_add
        assert "old-tag" in labels_to_remove

    def test_tag_changes_detected_via_get_all_flow(self, repo):
        """Tag changes are detected when task comes from get_all (UI flow)."""
        # Setup cache with original task
        original_task = Task(
            id="testuser/testrepo#1",
            title="Test",
            state="to_do",
            priority="medium",
            tags=["old-tag"],
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        repo._tasks = {"testuser/testrepo#1": original_task}
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        repo._status_options = {"To Do": "opt_todo"}
        repo._repo_labels = {"testuser/testrepo": {"new-tag": "LA_newtag", "old-tag": "LA_oldtag"}}

        # Simulate UI flow: get_all returns tasks for display
        tasks = repo._sorted_tasks()
        task = tasks[0]

        # User edits task (creates new instance with model_copy since Task is frozen)
        updated_task = task.model_copy(update={"tags": ["new-tag"]})

        # Compute label changes - old_task from cache should have ["old-tag"]
        old_task = repo._tasks.get("testuser/testrepo#1")
        labels_to_add, labels_to_remove = repo._compute_label_changes(updated_task, old_task)

        # Should detect the tag change
        assert "new-tag" in labels_to_add
        assert "old-tag" in labels_to_remove


class TestGitHubExtractPriorityReturnsNone:
    """Tests for _extract_priority_from_labels returning None."""

    def test_extract_priority_returns_none_when_no_match(self, repo):
        """_extract_priority_from_labels returns (None, None) when no label matches."""
        labels = ["unrelated-label", "another-label"]
        priority, matched_label = repo._extract_priority_from_labels(labels)
        assert priority is None
        assert matched_label is None

    def test_extract_priority_returns_none_for_empty_labels(self, repo):
        """_extract_priority_from_labels returns (None, None) for empty label list."""
        priority, matched_label = repo._extract_priority_from_labels([])
        assert priority is None
        assert matched_label is None
