"""Sync command for fetching GitHub issues to local files."""

import logging
from pathlib import Path

from ..github.client import GitHubAuthError, GitHubClient, GitHubClientError
from ..models import ChangeSet, Conflict
from ..services.config_service import ConfigService
from ..sync.engine import GitHubSyncEngine
from .output import error, header, info, success

logger = logging.getLogger(__name__)


def run_sync(
    project_root: Path,
    dry_run: bool = False,
    force: bool = False,
) -> int:
    """Fetch issues from GitHub to local files.

    Args:
        project_root: Path to project root containing sltasks.yml
        dry_run: Show what would sync without writing files
        force: Overwrite local changes (resolve conflicts to GitHub)

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    # Load configuration
    config_service = ConfigService(project_root)
    config = config_service.get_config()

    # Validate GitHub configuration
    if not config.github:
        error("GitHub configuration not found in sltasks.yml")
        info("Run 'sltasks --github-setup' to configure GitHub integration")
        return 1

    if not config.github.sync or not config.github.sync.enabled:
        error("GitHub sync is not enabled")
        info("Add 'sync.enabled: true' to your github config in sltasks.yml")
        return 1

    if not config.github.sync.filters:
        error("No sync filters configured")
        info("Add 'sync.filters' to specify which issues to sync")
        info("Example: filters: ['assignee:@me', 'label:urgent']")
        return 1

    # Authenticate with GitHub
    header("Authenticating with GitHub...")
    try:
        base_url = config.github.base_url or "api.github.com"
        client = GitHubClient.from_environment(base_url)
    except GitHubAuthError as e:
        error(f"GitHub authentication failed: {e}")
        info("Set GITHUB_TOKEN environment variable or run 'gh auth login'")
        return 1
    except GitHubClientError as e:
        error(f"GitHub client error: {e}")
        return 1

    # Initialize sync engine
    task_root = _get_sync_task_root(config_service, config.github.sync)
    engine = GitHubSyncEngine(config_service, client, task_root)

    # Detect changes
    header("Analyzing sync status...")
    changes = engine.detect_changes()

    # Display summary
    _display_change_summary(changes, dry_run)

    # Check for nothing to do
    if not changes.to_pull and not changes.conflicts:
        info("Everything is up to date")
        return 0

    # Warn about conflicts
    if changes.conflicts and not force and not dry_run:
        _display_conflicts(changes.conflicts)
        error(f"{len(changes.conflicts)} conflict(s) detected")
        info("Use --force to overwrite local changes")
        info("Or set 'push_changes: true' in file frontmatter to push local version")
        return 1

    # Show what would be synced
    if dry_run:
        _display_dry_run_details(changes)
        return 0

    # Execute sync
    header("Syncing from GitHub...")
    result = engine.sync_from_github(dry_run=False, force=force)

    # Report results
    print()
    if result.pulled > 0:
        success(f"Synced {result.pulled} file(s)")
    if result.skipped > 0:
        info(f"Skipped {result.skipped} (no changes)")
    if result.conflicts > 0:
        info(f"Conflicts resolved: {result.conflicts}")
    if result.errors:
        for err in result.errors:
            error(err)

    return 0 if not result.has_errors else 1


def _get_sync_task_root(config_service: ConfigService, sync_config) -> Path:
    """Get task root for synced files."""
    if sync_config.task_root:
        return config_service.project_root / sync_config.task_root
    return config_service.task_root


def _display_change_summary(changes: ChangeSet, dry_run: bool) -> None:
    """Display summary of detected changes."""
    prefix = "[DRY RUN] " if dry_run else ""
    print()
    print(f"{prefix}Sync Summary:")
    print(f"  To fetch: {len(changes.to_pull)} issue(s)")
    print(f"  To push: {len(changes.to_push)} file(s)")
    print(f"  Conflicts: {len(changes.conflicts)}")
    print()


def _display_conflicts(conflicts: list[Conflict]) -> None:
    """Display conflict details."""
    print()
    print("Conflicts detected:")
    for c in conflicts:
        print(f"  - {c.task_id}")
        print(f"    Issue: {c.repository}#{c.issue_number}")
        print(f"    Local updated: {c.local_updated.isoformat()}")
        print(f"    Remote updated: {c.remote_updated.isoformat()}")
        print(f"    Last synced: {c.last_synced.isoformat()}")
    print()


def _display_dry_run_details(changes: ChangeSet) -> None:
    """Display details of what would be synced."""
    if changes.to_pull:
        print("Would fetch:")
        for issue_key in changes.to_pull:
            print(f"  - {issue_key}")
        print()

    if changes.to_push:
        print("Files with local changes (not synced, use 'sltasks push' if needed):")
        for task_id in changes.to_push:
            print(f"  - {task_id}")
        print()

    if changes.conflicts:
        print("Conflicts (use --force to overwrite):")
        for c in changes.conflicts:
            print(f"  - {c.task_id} ({c.repository}#{c.issue_number})")
        print()
