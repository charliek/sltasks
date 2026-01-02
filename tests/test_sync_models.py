"""Unit tests for sync models."""

from datetime import UTC, datetime

from sltasks.models.sync import (
    ChangeSet,
    Conflict,
    PushResult,
    SyncResult,
    SyncStatus,
)


class TestSyncStatus:
    """Tests for SyncStatus enum."""

    def test_sync_status_values(self):
        """SyncStatus has all expected values."""
        assert SyncStatus.SYNCED == "synced"
        assert SyncStatus.LOCAL_MODIFIED == "local_modified"
        assert SyncStatus.REMOTE_MODIFIED == "remote_modified"
        assert SyncStatus.CONFLICT == "conflict"
        assert SyncStatus.LOCAL_ONLY == "local_only"

    def test_sync_status_is_str(self):
        """SyncStatus values are strings."""
        assert isinstance(SyncStatus.SYNCED.value, str)
        # SyncStatus inherits from str, so .value gives the string
        assert SyncStatus.SYNCED.value == "synced"


class TestPushResult:
    """Tests for PushResult dataclass."""

    def test_push_result_empty(self):
        """Empty PushResult has correct defaults."""
        result = PushResult()
        assert result.created == []
        assert result.errors == []
        assert result.dry_run is False
        assert result.success_count == 0
        assert result.error_count == 0
        assert result.has_errors is False

    def test_push_result_with_created(self):
        """PushResult with created issues."""
        result = PushResult(created=["owner/repo#1", "owner/repo#2"])
        assert result.success_count == 2
        assert result.error_count == 0
        assert result.has_errors is False

    def test_push_result_with_errors(self):
        """PushResult with errors."""
        result = PushResult(errors=["Error 1", "Error 2"])
        assert result.success_count == 0
        assert result.error_count == 2
        assert result.has_errors is True

    def test_push_result_mixed(self):
        """PushResult with both created and errors."""
        result = PushResult(
            created=["owner/repo#1"],
            errors=["Failed to create issue 2"],
        )
        assert result.success_count == 1
        assert result.error_count == 1
        assert result.has_errors is True

    def test_push_result_dry_run(self):
        """PushResult with dry_run flag."""
        result = PushResult(dry_run=True, created=["owner/repo#(new)"])
        assert result.dry_run is True


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_sync_result_empty(self):
        """Empty SyncResult has correct defaults."""
        result = SyncResult()
        assert result.pulled == 0
        assert result.skipped == 0
        assert result.conflicts == 0
        assert result.errors == []
        assert result.dry_run is False
        assert result.has_errors is False

    def test_sync_result_with_values(self):
        """SyncResult with values."""
        result = SyncResult(pulled=5, skipped=3, conflicts=1)
        assert result.pulled == 5
        assert result.skipped == 3
        assert result.conflicts == 1

    def test_sync_result_with_errors(self):
        """SyncResult with errors."""
        result = SyncResult(errors=["Error 1"])
        assert result.has_errors is True


class TestConflict:
    """Tests for Conflict dataclass."""

    def test_conflict_creation(self):
        """Conflict can be created with required fields."""
        now = datetime.now(UTC)
        conflict = Conflict(
            task_id="task.md",
            local_path="/path/to/task.md",
            issue_number=123,
            repository="owner/repo",
            local_updated=now,
            remote_updated=now,
            last_synced=now,
        )
        assert conflict.task_id == "task.md"
        assert conflict.issue_number == 123
        assert conflict.repository == "owner/repo"


class TestChangeSet:
    """Tests for ChangeSet dataclass."""

    def test_changeset_empty(self):
        """Empty ChangeSet has correct defaults."""
        changes = ChangeSet()
        assert changes.to_pull == []
        assert changes.to_push == []
        assert changes.conflicts == []

    def test_changeset_with_values(self):
        """ChangeSet with values."""
        changes = ChangeSet(
            to_pull=["task1.md", "task2.md"],
            to_push=["task3.md"],
        )
        assert len(changes.to_pull) == 2
        assert len(changes.to_push) == 1
