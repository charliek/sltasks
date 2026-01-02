"""Push command for creating GitHub issues from local files."""

import logging
from pathlib import Path

from ..github.client import GitHubAuthError, GitHubClient, GitHubClientError
from ..models import Task
from ..services.config_service import ConfigService
from ..sync.engine import GitHubPushEngine, PostPushAction
from .output import error, header, info, success

logger = logging.getLogger(__name__)


def run_push(
    project_root: Path,
    files: list[str] | None = None,
    dry_run: bool = False,
    yes: bool = False,
    delete: bool = False,
    archive: bool = False,
) -> int:
    """Push local tasks to GitHub as new issues.

    Args:
        project_root: Path to project root containing sltasks.yml
        files: Specific files to push (default: all local-only tasks)
        dry_run: Show what would be pushed without creating issues
        yes: Skip confirmation prompt
        delete: Delete local files after push
        archive: Archive local files after push (set archived: true)

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

    if not config.github.default_repo:
        error("default_repo is required in github config to push issues")
        info("Add 'default_repo: owner/repo' to your sltasks.yml github section")
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

    # Initialize push engine
    task_root = config_service.task_root
    engine = GitHubPushEngine(config_service, client, task_root)

    # Find tasks to push
    header("Finding local-only tasks...")
    all_local_tasks = engine.find_local_only_tasks()

    if not all_local_tasks:
        info("No local-only tasks found to push")
        return 0

    # Filter by specified files if provided
    tasks_to_push: list[Task]
    if files:
        file_set = set(files)
        # Also handle .md extension
        file_set.update(f if f.endswith(".md") else f"{f}.md" for f in files)
        tasks_to_push = [t for t in all_local_tasks if t.id in file_set]
        if not tasks_to_push:
            error("None of the specified files are local-only tasks")
            info(f"Local-only tasks found: {', '.join(t.id for t in all_local_tasks)}")
            return 1
    else:
        tasks_to_push = all_local_tasks

    # Show preview
    header(f"\n{'[DRY RUN] ' if dry_run else ''}Tasks to push to GitHub:")
    print(f"Target repository: {config.github.default_repo}")
    print()
    for task in tasks_to_push:
        title = task.title or task.display_title
        state_str = f" [{task.state}]" if task.state != "todo" else ""
        type_str = f" ({task.type})" if task.type else ""
        priority_str = f" !{task.priority}" if task.priority else ""
        print(f"  - {task.id}: {title}{type_str}{priority_str}{state_str}")
    print()

    # Confirm if not dry-run and not --yes
    if not dry_run and not yes:
        try:
            response = input(f"Push {len(tasks_to_push)} task(s) to GitHub? [y/N] ").strip().lower()
            if response not in ("y", "yes"):
                info("Push cancelled")
                return 0
        except (KeyboardInterrupt, EOFError):
            print()
            info("Push cancelled")
            return 0

    # Execute push
    header("\nPushing to GitHub..." if not dry_run else "\n[DRY RUN] Would push:")
    result = engine.push_new_issues(tasks_to_push, dry_run=dry_run)

    # Report results
    if result.created:
        for issue_id in result.created:
            success(f"Created: {issue_id}")
    if result.errors:
        for err in result.errors:
            error(err)

    print()
    if dry_run:
        info(f"Would create {result.success_count} issue(s)")
    else:
        info(f"Created {result.success_count} issue(s)")

    # Handle post-push file management (only if not dry-run)
    if not dry_run and result.success_count > 0:
        # Determine post-push action
        action: PostPushAction | None = None
        if delete:
            action = "delete"
        elif archive:
            action = "archive"
        else:
            # Prompt user
            action = _prompt_post_push_action()

        if action:
            header(f"\n{'Deleting' if action == 'delete' else 'Archiving'} pushed files...")
            # Map created issue IDs back to tasks
            # result.created format: "owner/repo#123" or for dry-run "owner/repo#(new) - title"
            for i, issue_id in enumerate(result.created):
                if i < len(tasks_to_push):
                    task = tasks_to_push[i]
                    try:
                        engine.handle_pushed_file(task, issue_id, action)
                        success(f"{'Deleted' if action == 'delete' else 'Archived'}: {task.id}")
                    except Exception as e:
                        error(f"Failed to handle {task.id}: {e}")

    return 0 if not result.has_errors else 1


def _prompt_post_push_action() -> PostPushAction | None:
    """Prompt user for post-push file action.

    Returns:
        Action to take, or None to keep files as-is
    """
    print()
    print("What would you like to do with the pushed files?")
    print("  1. Keep files (no change)")
    print("  2. Delete files")
    print("  3. Archive files (mark as archived)")
    print()

    try:
        choice = input("Choose [1/2/3]: ").strip()
        if choice == "2":
            return "delete"
        elif choice == "3":
            return "archive"
        else:
            return None
    except (KeyboardInterrupt, EOFError):
        print()
        return None
