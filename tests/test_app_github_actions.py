"""Tests for app action handlers with GitHub provider.

These tests verify that user feedback (notifications) is properly shown
after GitHub operations, including success, failure, and edge cases.
"""

import logging
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from sltasks.github import GitHubClientError
from sltasks.models import GitHubProviderData, Task


class TestActionEditTaskNotifications:
    """Tests for edit task action notifications."""

    def test_action_edit_task_shows_notification_on_success(self):
        """Verify notification appears after editing a GitHub task."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.config_service = MagicMock()
        app.config_service.task_root = None
        app.task_service = MagicMock()
        app.task_service.open_in_editor.return_value = True
        app.board_service = MagicMock()

        # Mock screen with task
        mock_screen = MagicMock()
        mock_task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        mock_screen.get_current_task.return_value = mock_task

        # Mock the screen property and isinstance check
        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
            patch.object(app, "suspend"),
        ):
            app.action_edit_task()

        app.notify.assert_called_once_with("Task updated", timeout=2)

    def test_action_edit_task_shows_error_on_api_failure(self):
        """Verify error notification when GitHub API fails during reload."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.config_service = MagicMock()
        app.config_service.task_root = None
        app.task_service = MagicMock()
        app.task_service.open_in_editor.return_value = True
        app.board_service = MagicMock()
        app.board_service.reload.side_effect = GitHubClientError("API rate limit exceeded")

        # Mock screen with task
        mock_screen = MagicMock()
        mock_task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        mock_screen.get_current_task.return_value = mock_task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
            patch.object(app, "suspend"),
        ):
            app.action_edit_task()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "Failed to save" in call_args[0][0]
        assert call_args[1]["severity"] == "error"


class TestActionMoveTaskNotifications:
    """Tests for move task action notifications."""

    def test_action_move_task_right_shows_notification_on_success(self):
        """Verify notification appears after moving a GitHub task."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()

        # Mock screen with task
        mock_screen = MagicMock()
        original_task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        moved_task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="in_progress",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        mock_screen.get_current_task.return_value = original_task
        app.board_service.move_task_right.return_value = moved_task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_right()

        app.notify.assert_called_once_with("Moved to in progress", timeout=2)
        mock_screen.refresh_board.assert_called_once()

    def test_action_move_task_left_at_first_column_shows_notification(self):
        """Verify feedback when task is already at first column."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()

        # Mock screen with task at first column
        mock_screen = MagicMock()
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="backlog",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        mock_screen.get_current_task.return_value = task
        # Return same task (state unchanged) to indicate already at edge
        app.board_service.move_task_left.return_value = task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_left()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "Already at first column" in call_args[0][0]
        assert call_args[1]["severity"] == "information"

    def test_action_move_task_right_at_last_column_shows_notification(self):
        """Verify feedback when task is already at last column."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()

        # Mock screen with task at last column
        mock_screen = MagicMock()
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="done",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        mock_screen.get_current_task.return_value = task
        # Return same task (state unchanged) to indicate already at edge
        app.board_service.move_task_right.return_value = task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_right()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "Already at last column" in call_args[0][0]
        assert call_args[1]["severity"] == "information"

    def test_action_move_task_shows_error_on_api_failure(self):
        """Verify error notification when GitHub API fails during move."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()
        app.board_service.move_task_right.side_effect = GitHubClientError("Network error")

        mock_screen = MagicMock()
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )
        mock_screen.get_current_task.return_value = task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_right()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "Failed to move" in call_args[0][0]
        assert call_args[1]["severity"] == "error"


class TestActionMoveTaskUpDownNotifications:
    """Tests for move task up/down action notifications."""

    def test_action_move_task_up_shows_notification_on_success(self):
        """Verify notification appears after moving task up."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()
        app.board_service.reorder_task.return_value = True

        mock_screen = MagicMock()
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
        )
        mock_screen.get_current_task.return_value = task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_up()

        app.notify.assert_called_once_with("Moved up", timeout=1)
        mock_screen.refresh_board.assert_called_once()

    def test_action_move_task_up_at_top_shows_notification(self):
        """Verify feedback when task is already at top."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()
        app.board_service.reorder_task.return_value = False

        mock_screen = MagicMock()
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
        )
        mock_screen.get_current_task.return_value = task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_up()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "Already at top" in call_args[0][0]
        assert call_args[1]["severity"] == "information"

    def test_action_move_task_down_shows_notification_on_success(self):
        """Verify notification appears after moving task down."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()
        app.board_service.reorder_task.return_value = True

        mock_screen = MagicMock()
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
        )
        mock_screen.get_current_task.return_value = task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_down()

        app.notify.assert_called_once_with("Moved down", timeout=1)
        mock_screen.refresh_board.assert_called_once()

    def test_action_move_task_down_at_bottom_shows_notification(self):
        """Verify feedback when task is already at bottom."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()
        app.board_service.reorder_task.return_value = False

        mock_screen = MagicMock()
        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
        )
        mock_screen.get_current_task.return_value = task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_down()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "Already at bottom" in call_args[0][0]
        assert call_args[1]["severity"] == "information"


class TestUpdateIssueWarningLogging:
    """Tests for warning logging in _update_issue()."""

    def test_update_issue_logs_warning_on_unmapped_state(self, caplog):
        """Verify warning logged when state cannot be mapped to GitHub status."""
        from unittest.mock import MagicMock

        from sltasks.repositories.github_projects import GitHubProjectsRepository

        # Create repo with mocked dependencies
        mock_config_service = MagicMock()
        mock_config_service.get_config.return_value = MagicMock(
            github=MagicMock(
                project_url="https://github.com/users/testuser/projects/1",
                default_repo="testuser/testrepo",
            )
        )

        repo = GitHubProjectsRepository(mock_config_service)
        repo._client = MagicMock()
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        repo._status_options = {"To Do": "opt_todo", "Done": "opt_done"}
        repo._project_metadata_fetched = True

        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="unknown_state",  # State that won't map to any status
            priority="medium",
            body="Body",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        with caplog.at_level(logging.WARNING):
            repo._update_issue(task)

        assert any(
            "Could not map state 'unknown_state'" in record.message for record in caplog.records
        )

    def test_update_issue_logs_warning_on_missing_option_id(self, caplog):
        """Verify warning logged when status has no matching option ID."""
        from unittest.mock import MagicMock

        from sltasks.repositories.github_projects import GitHubProjectsRepository

        mock_config_service = MagicMock()
        mock_config_service.get_config.return_value = MagicMock(
            github=MagicMock(
                project_url="https://github.com/users/testuser/projects/1",
                default_repo="testuser/testrepo",
            )
        )

        repo = GitHubProjectsRepository(mock_config_service)
        repo._client = MagicMock()
        repo._project_id = "PVT_123"
        repo._status_field_id = "PVTSSF_123"
        # Status options don't include "In Progress"
        repo._status_options = {"To Do": "opt_todo", "Done": "opt_done"}
        repo._project_metadata_fetched = True

        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="in_progress",  # Maps to "In Progress" but no option ID
            priority="medium",
            body="Body",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        # Mock _map_state_to_status to return a status that's not in options
        with (
            patch.object(repo, "_map_state_to_status", return_value="In Progress"),
            caplog.at_level(logging.WARNING),
        ):
            repo._update_issue(task)

        assert any("has no matching option ID" in record.message for record in caplog.records)


class TestObjectAliasingBug:
    """Tests for the object aliasing bug fix.

    The board_service returns the same Task object from cache that the screen holds.
    When board_service modifies task.state, it modifies the same object.
    The fix captures original_state before calling move operations.
    """

    def test_move_task_right_detects_change_with_aliased_object(self):
        """Verify move is detected even when screen and result are same object.

        This is the core aliasing scenario: get_current_task() and move_task_right()
        return the same Task object from cache. The fix uses original_state to detect change.
        """
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()

        mock_screen = MagicMock()
        # Single shared task object (simulates cache aliasing)
        shared_task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        mock_screen.get_current_task.return_value = shared_task

        def move_and_modify(_task_id):
            # Simulates what board_service.move_task_right does:
            # modifies task.state and returns the same object
            shared_task.state = "in_progress"
            return shared_task

        app.board_service.move_task_right.side_effect = move_and_modify

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_right()

        # Should detect the change and show success notification
        app.notify.assert_called_once_with("Moved to in progress", timeout=2)
        mock_screen.refresh_board.assert_called_once()

    def test_move_task_left_detects_change_with_aliased_object(self):
        """Verify move is detected even when screen and result are same object."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()

        mock_screen = MagicMock()
        shared_task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="in_progress",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        mock_screen.get_current_task.return_value = shared_task

        def move_and_modify(_task_id):
            shared_task.state = "to_do"
            return shared_task

        app.board_service.move_task_left.side_effect = move_and_modify

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_left()

        app.notify.assert_called_once_with("Moved to to do", timeout=2)
        mock_screen.refresh_board.assert_called_once()

    def test_move_task_right_at_boundary_with_aliased_object(self):
        """Verify boundary detection works with aliased object."""
        from sltasks.app import SltasksApp

        app = SltasksApp.__new__(SltasksApp)
        app.notify = MagicMock()
        app.board_service = MagicMock()

        mock_screen = MagicMock()
        shared_task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="done",
            priority="medium",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        mock_screen.get_current_task.return_value = shared_task
        # At boundary, board_service returns same object without modifying state
        app.board_service.move_task_right.return_value = shared_task

        with (
            patch.object(SltasksApp, "screen", new_callable=PropertyMock, return_value=mock_screen),
            patch("sltasks.app.isinstance", return_value=True),
        ):
            app.action_move_task_right()

        app.notify.assert_called_once()
        call_args = app.notify.call_args
        assert "Already at last column" in call_args[0][0]
        assert call_args[1]["severity"] == "information"


class TestGitHubClientErrorPropagation:
    """Tests to verify GitHubClientError propagates correctly."""

    def test_update_issue_propagates_api_error(self):
        """Verify GitHubClientError propagates from _update_issue()."""
        from unittest.mock import MagicMock

        from sltasks.repositories.github_projects import GitHubProjectsRepository

        mock_config_service = MagicMock()
        mock_config_service.get_config.return_value = MagicMock(
            github=MagicMock(
                project_url="https://github.com/users/testuser/projects/1",
                default_repo="testuser/testrepo",
            )
        )

        repo = GitHubProjectsRepository(mock_config_service)
        repo._client = MagicMock()
        repo._client.mutate.side_effect = GitHubClientError("API error")

        task = Task(
            id="testuser/testrepo#1",
            title="Test Task",
            state="to_do",
            priority="medium",
            body="Body",
            provider_data=GitHubProviderData(
                project_item_id="PVTI_1",
                issue_node_id="I_123",
                repository="testuser/testrepo",
                issue_number=1,
            ),
        )

        with pytest.raises(GitHubClientError, match="API error"):
            repo._update_issue(task)
