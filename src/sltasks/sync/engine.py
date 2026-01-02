"""GitHub sync engine for bidirectional synchronization.

This module provides the GitHubSyncEngine class which handles:
- Push new local tasks to GitHub as issues (Phase 2A)
- Pull issues from GitHub to local files (Phase 2B)
- Push updates to existing GitHub issues (Phase 2B)
- Conflict detection and resolution (Phase 2B)

The push-only functionality works even without full sync enabled -
it's useful for the LLM workflow where issues are authored locally
and pushed to GitHub.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import frontmatter
import yaml

from ..models import ChangeSet, Conflict, FileProviderData, PushResult, SyncResult, Task
from ..models.sltasks_config import BoardConfig, GitHubConfig
from .file_mapper import (
    generate_synced_filename,
    is_local_only_filename,
    is_synced_filename,
    parse_synced_filename,
)
from .filter_parser import ParsedFilter, SyncFilterParser

if TYPE_CHECKING:
    from ..github.client import GitHubClient
    from ..services.config_service import ConfigService

logger = logging.getLogger(__name__)


PostPushAction = Literal["delete", "archive", "rename"]


class GitHubSyncEngine:
    """Engine for bidirectional sync between local files and GitHub.

    Handles the workflow of:
    1. Finding local-only task files (not synced from GitHub)
    2. Creating GitHub issues from those files
    3. Pulling issues from GitHub to local files (with filters)
    4. Pushing updates to existing GitHub issues
    5. Detecting and resolving conflicts
    6. Handling post-push cleanup (delete, archive, or rename)

    Push functionality works even when sync.enabled is False - useful for
    the LLM workflow where issues are authored locally and pushed to GitHub.
    """

    def __init__(
        self,
        config_service: ConfigService,
        github_client: GitHubClient,
        task_root: Path,
    ) -> None:
        """Initialize the sync engine.

        Args:
            config_service: Configuration service for board/GitHub config
            github_client: Authenticated GitHub client
            task_root: Path to the tasks directory
        """
        self._config_service = config_service
        self._client = github_client
        self._task_root = task_root

        # Filter parser for GitHub search syntax
        self._filter_parser = SyncFilterParser()

        # Cached GitHub project metadata (fetched lazily)
        self._project_id: str | None = None
        self._status_field_id: str | None = None
        self._status_options: dict[str, str] = {}  # status_name -> option_id
        self._repo_labels: dict[str, dict[str, str]] = {}  # repo -> {label_name: label_id}

        # Cached current user (for @me filter expansion)
        self._current_user: str | None = None

    def _get_github_config(self) -> GitHubConfig:
        """Get GitHub configuration."""
        config = self._config_service.get_config()
        if not config.github:
            raise ValueError("GitHub configuration not found in sltasks.yml")
        return config.github

    def _get_board_config(self) -> BoardConfig:
        """Get board configuration."""
        return self._config_service.get_board_config()

    # --- Public API: Push (Phase 2A) ---

    def find_local_only_tasks(self) -> list[Task]:
        """Find all local-only task files (not synced from GitHub).

        Returns:
            List of Task objects that are local-only (can be pushed)
        """
        tasks: list[Task] = []

        if not self._task_root.exists():
            return tasks

        for filepath in self._task_root.glob("*.md"):
            # Skip files that are already synced (have github metadata in name)
            if is_synced_filename(filepath.name):
                continue

            # Only consider local-only files
            if not is_local_only_filename(filepath.name):
                continue

            task = self._parse_task_file(filepath)
            if task is not None and not self._has_github_metadata(filepath):
                tasks.append(task)

        return tasks

    def push_new_issues(
        self,
        tasks: list[Task],
        dry_run: bool = False,
    ) -> PushResult:
        """Push local tasks to GitHub as new issues.

        Args:
            tasks: List of tasks to push
            dry_run: If True, don't actually create issues

        Returns:
            PushResult with created issue IDs and any errors
        """
        result = PushResult(dry_run=dry_run)

        github_config = self._get_github_config()
        if not github_config.default_repo:
            result.errors.append("default_repo is required in github config to push issues")
            return result

        # Fetch project metadata for setting status
        if not dry_run:
            try:
                self._fetch_project_metadata()
            except Exception as e:
                logger.warning("Failed to fetch project metadata: %s", e)
                # Continue anyway - we can still create issues without project status

        for task in tasks:
            try:
                if dry_run:
                    # Generate what the issue ID would be
                    issue_id = f"{github_config.default_repo}#(new)"
                    result.created.append(f"{issue_id} - {task.title or task.display_title}")
                else:
                    issue_id = self._create_github_issue(task)
                    result.created.append(issue_id)
                    logger.info("Created GitHub issue: %s", issue_id)
            except Exception as e:
                error_msg = f"Failed to push '{task.id}': {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        return result

    def handle_pushed_file(
        self,
        task: Task,
        issue_id: str,
        action: PostPushAction,
    ) -> None:
        """Handle a local file after it's been pushed to GitHub.

        Args:
            task: The task that was pushed
            issue_id: The GitHub issue ID (owner/repo#number)
            action: What to do with the file:
                - "delete": Remove the file completely
                - "archive": Mark as archived in frontmatter
                - "rename": Rename to synced filename format
        """
        filepath = self._task_root / task.id

        if not filepath.exists():
            logger.warning("File not found for post-push handling: %s", filepath)
            return

        if action == "delete":
            filepath.unlink()
            logger.info("Deleted local file: %s", task.id)

            # Also remove from tasks.yaml if it exists
            self._remove_from_tasks_yaml(task.id)

        elif action == "archive":
            # Update the file with archived: true
            self._mark_file_archived(filepath)
            logger.info("Archived local file: %s", task.id)

        elif action == "rename":
            # Parse issue_id to get owner, repo, number
            # Format: owner/repo#123
            repo_part, number_str = issue_id.rsplit("#", 1)
            owner, repo = repo_part.split("/")
            issue_number = int(number_str)

            new_filename = generate_synced_filename(
                owner=owner,
                repo=repo,
                issue_number=issue_number,
                title=task.title or task.display_title,
            )
            new_filepath = self._task_root / new_filename

            filepath.rename(new_filepath)
            logger.info("Renamed %s -> %s", task.id, new_filename)

            # Update tasks.yaml with new filename
            self._rename_in_tasks_yaml(task.id, new_filename)

    # --- Public API: Pull (Phase 2B) ---

    def sync_from_github(
        self,
        dry_run: bool = False,
        force: bool = False,
    ) -> SyncResult:
        """Pull issues from GitHub to local files.

        Args:
            dry_run: If True, preview changes without writing files
            force: If True, overwrite local changes (resolve conflicts to GitHub)

        Returns:
            SyncResult with counts and any errors
        """
        result = SyncResult(dry_run=dry_run)

        github_config = self._get_github_config()
        if not github_config.sync or not github_config.sync.enabled:
            result.errors.append("GitHub sync is not enabled (sync.enabled: false)")
            return result

        try:
            # Get current user for @me filter expansion
            current_user = self._get_current_user()

            # Fetch and filter issues
            all_issues = self._fetch_all_project_issues()
            filtered_issues = self._apply_filters(all_issues, current_user)

            logger.info(
                "Filtered %d/%d issues for sync",
                len(filtered_issues),
                len(all_issues),
            )

            # Build map of existing synced files by issue key
            existing_files = self._scan_synced_files()
            existing_by_key = {self._get_issue_key_from_task(task): task for task in existing_files}

            for issue in filtered_issues:
                issue_key = self._get_issue_key_from_issue(issue)
                existing_task = existing_by_key.get(issue_key)

                try:
                    if existing_task:
                        # Check for conflict
                        conflict = self._check_conflict(existing_task, issue)
                        if conflict and not force:
                            # Skip conflicting files unless force
                            result.conflicts += 1
                            logger.warning(
                                "Skipping conflict: %s (use --force to overwrite)",
                                existing_task.id,
                            )
                            continue

                    if dry_run:
                        if existing_task:
                            logger.info("[DRY RUN] Would update: %s", existing_task.id)
                        else:
                            logger.info("[DRY RUN] Would create: %s", issue_key)
                        result.pulled += 1
                    else:
                        filepath = self._write_issue_to_file(issue, existing_task)
                        result.pulled += 1
                        logger.info("Synced: %s", filepath.name)

                except Exception as e:
                    error_msg = f"Failed to sync {issue_key}: {e}"
                    result.errors.append(error_msg)
                    logger.error(error_msg)

        except Exception as e:
            result.errors.append(f"Sync failed: {e}")
            logger.error("Sync failed: %s", e)

        return result

    def detect_changes(self) -> ChangeSet:
        """Detect changes between local files and GitHub.

        Compares synced files with their GitHub counterparts to identify:
        - to_pull: Issues that need to be pulled (new or remote-modified)
        - to_push: Files that need to be pushed (local-modified with push_changes: true)
        - conflicts: Files where both local and remote changed

        Returns:
            ChangeSet with lists of task IDs in each category
        """
        changes = ChangeSet()

        github_config = self._get_github_config()
        if not github_config.sync or not github_config.sync.enabled:
            return changes

        try:
            current_user = self._get_current_user()
            all_issues = self._fetch_all_project_issues()
            filtered_issues = self._apply_filters(all_issues, current_user)

            # Build maps
            existing_files = self._scan_synced_files()
            existing_by_key = {self._get_issue_key_from_task(task): task for task in existing_files}
            remote_by_key = {
                self._get_issue_key_from_issue(issue): issue for issue in filtered_issues
            }

            # Check existing synced files
            for issue_key, local_task in existing_by_key.items():
                if issue_key not in remote_by_key:
                    # Issue removed from GitHub or no longer matches filters
                    # Don't add to any list - will be handled separately
                    continue

                remote_issue = remote_by_key[issue_key]
                github_meta = self._get_github_metadata(local_task)
                if not github_meta:
                    continue

                last_synced = github_meta.get("last_synced")
                if not last_synced:
                    # Never synced - treat as needing pull
                    changes.to_pull.append(local_task.id)
                    continue

                last_synced_dt = self._parse_datetime(last_synced)
                local_updated = local_task.updated
                remote_updated = self._parse_datetime(remote_issue.get("updatedAt", ""))

                local_changed = local_updated and last_synced_dt and local_updated > last_synced_dt
                remote_changed = (
                    remote_updated and last_synced_dt and remote_updated > last_synced_dt
                )

                if local_changed and remote_changed:
                    # Conflict
                    changes.conflicts.append(
                        Conflict(
                            task_id=local_task.id,
                            local_path=str(self._task_root / local_task.id),
                            issue_number=github_meta.get("issue_number", 0),
                            repository=github_meta.get("repository", ""),
                            local_updated=local_updated or datetime.now(UTC),
                            remote_updated=remote_updated or datetime.now(UTC),
                            last_synced=last_synced_dt or datetime.now(UTC),
                        )
                    )
                elif local_changed:
                    # Check if push_changes is set
                    push_changes = self._get_push_changes_flag(local_task)
                    if push_changes:
                        changes.to_push.append(local_task.id)
                elif remote_changed:
                    changes.to_pull.append(local_task.id)

            # Check for new remote issues
            for issue_key, remote_issue in remote_by_key.items():
                if issue_key not in existing_by_key:
                    # Generate what the filename would be
                    content = remote_issue.get("content", {})
                    repo = content.get("repository", {}).get("nameWithOwner", "")
                    number = content.get("number", 0)
                    changes.to_pull.append(f"{repo}#{number}")

            # Add local-only files to push list
            local_only = self.find_local_only_tasks()
            for task in local_only:
                changes.to_push.append(task.id)

        except Exception as e:
            logger.error("Failed to detect changes: %s", e)

        return changes

    # --- Public API: Push Updates (Phase 2B) ---

    def find_modified_synced_tasks(self) -> list[Task]:
        """Find synced files that have local modifications marked for push.

        Returns files where:
        - File has github: section with synced: true
        - File has push_changes: true
        - File updated > github.last_synced

        Returns:
            List of Task objects ready to push updates
        """
        tasks: list[Task] = []

        synced_files = self._scan_synced_files()
        for task in synced_files:
            github_meta = self._get_github_metadata(task)
            if not github_meta:
                continue

            # Check push_changes flag
            if not self._get_push_changes_flag(task):
                continue

            # Check if modified since last sync
            last_synced = github_meta.get("last_synced")
            if last_synced:
                last_synced_dt = self._parse_datetime(last_synced)
                if task.updated and last_synced_dt and task.updated > last_synced_dt:
                    tasks.append(task)

        return tasks

    def push_updates(
        self,
        tasks: list[Task],
        dry_run: bool = False,
    ) -> PushResult:
        """Push local modifications to existing GitHub issues.

        Args:
            tasks: List of synced tasks to update
            dry_run: If True, preview without updating

        Returns:
            PushResult with updated issue IDs and any errors
        """
        result = PushResult(dry_run=dry_run)

        for task in tasks:
            github_meta = self._get_github_metadata(task)
            if not github_meta:
                result.errors.append(f"{task.id}: No GitHub metadata found")
                continue

            issue_number = github_meta.get("issue_number")
            repository = github_meta.get("repository")
            if not issue_number or not repository:
                result.errors.append(f"{task.id}: Missing issue_number or repository")
                continue

            issue_id = f"{repository}#{issue_number}"

            try:
                if dry_run:
                    result.created.append(f"{issue_id} - {task.title} (update)")
                else:
                    self._update_github_issue(task, github_meta)
                    result.created.append(issue_id)
                    logger.info("Updated GitHub issue: %s", issue_id)

                    # Update frontmatter after successful push
                    self._update_sync_metadata(task)

            except Exception as e:
                error_msg = f"Failed to update {issue_id}: {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

        return result

    # --- Internal: GitHub API Operations ---

    def _get_current_user(self) -> str:
        """Get authenticated GitHub username."""
        if self._current_user is not None:
            return self._current_user

        from ..github.queries import GET_VIEWER

        result = self._client.query(GET_VIEWER, {})
        self._current_user = result.get("viewer", {}).get("login", "")
        logger.debug("Current GitHub user: %s", self._current_user)
        return self._current_user

    def _fetch_all_project_issues(self) -> list[dict]:
        """Fetch all issues from GitHub project with pagination.

        Returns:
            List of issue dicts with content and field values
        """
        from ..github.queries import GET_PROJECT_ITEMS

        self._fetch_project_metadata()
        if not self._project_id:
            return []

        issues: list[dict] = []
        cursor = None
        page_count = 0

        while True:
            page_count += 1
            result = self._client.query(
                GET_PROJECT_ITEMS,
                {"projectId": self._project_id, "cursor": cursor},
            )

            project_node = result.get("node", {})
            items_data = project_node.get("items", {})
            items = items_data.get("nodes", [])

            logger.debug("Page %d: fetched %d items", page_count, len(items))

            for item in items:
                content = item.get("content")
                if content is None:
                    continue

                # Skip draft issues
                if "number" not in content:
                    continue

                # Build issue dict for filtering
                repo_data = content.get("repository", {})
                labels = content.get("labels", {}).get("nodes", [])
                assignees = (
                    content.get("assignees", {}).get("nodes", []) if "assignees" in content else []
                )
                milestone = content.get("milestone")

                issue_dict = {
                    "project_item_id": item.get("id"),
                    "content": content,
                    "assignees": assignees,
                    "labels": labels,
                    "milestone": milestone,
                    "state": content.get("state", "OPEN"),
                    "repository": {"nameWithOwner": repo_data.get("nameWithOwner", "")},
                    "updatedAt": content.get("updatedAt"),
                    "createdAt": content.get("createdAt"),
                    "fieldValues": item.get("fieldValues", {}),
                }
                issues.append(issue_dict)

            # Check for pagination
            page_info = items_data.get("pageInfo", {})
            if page_info.get("hasNextPage"):
                cursor = page_info.get("endCursor")
            else:
                break

        logger.info("Fetched %d total issues from GitHub project", len(issues))
        return issues

    def _apply_filters(self, issues: list[dict], current_user: str) -> list[dict]:
        """Apply configured filters to issues.

        Filters are OR'd - any filter match includes the issue.

        Args:
            issues: List of issue dicts
            current_user: Authenticated username for @me expansion

        Returns:
            Filtered list of issues

        Raises:
            FilterParseError: If a filter expression is invalid
        """
        github_config = self._get_github_config()
        if not github_config.sync:
            return []

        filter_strs = github_config.sync.filters
        if not filter_strs:
            # No filters = sync nothing (must explicitly configure)
            return []

        # Parse filters - raise on invalid filters (config errors shouldn't be silent)
        parsed_filters: list[ParsedFilter] = []
        for filter_str in filter_strs:
            # FilterParseError will propagate up - this is intentional
            # Invalid filters should fail loudly, not silently sync everything
            parsed = self._filter_parser.parse(filter_str)
            parsed_filters.append(parsed)

        if not parsed_filters:
            return []

        # Get priority config for filter matching
        priority_field = github_config.priority_field
        board_config = self._get_board_config()
        board_priorities = [p.id for p in board_config.priorities] if board_config else None

        # Apply filters (OR logic)
        filtered = []
        for issue in issues:
            if self._filter_parser.matches_any_filter(
                parsed_filters, issue, current_user, priority_field, board_priorities
            ):
                filtered.append(issue)

        return filtered

    def _fetch_project_metadata(self) -> None:
        """Fetch GitHub project metadata (ID, status field, options)."""
        if self._project_id is not None:
            return  # Already fetched

        from ..github.queries import GET_ORG_PROJECT, GET_USER_PROJECT

        github_config = self._get_github_config()
        if not github_config.project_url:
            logger.warning("No project_url configured, cannot set project status")
            return

        # Parse project URL to get owner, type, and number
        # Format: https://github.com/users/OWNER/projects/N or orgs/OWNER/projects/N
        import re

        match = re.search(
            r"github\.com/(users|orgs)/([^/]+)/projects/(\d+)", github_config.project_url
        )
        if not match:
            logger.warning("Invalid project URL format: %s", github_config.project_url)
            return

        project_type, owner, number = match.groups()
        number = int(number)

        # Query for project metadata
        query = GET_USER_PROJECT if project_type == "users" else GET_ORG_PROJECT
        key = "user" if project_type == "users" else "organization"

        result = self._client.query(query, {"owner": owner, "number": number})
        project_data = result.get(key, {}).get("projectV2")
        if not project_data:
            logger.warning("Project not found: %s", github_config.project_url)
            return

        self._project_id = project_data["id"]

        # Find Status field
        for field in project_data.get("fields", {}).get("nodes", []):
            if field.get("name") == "Status":
                self._status_field_id = field["id"]
                self._status_options = {opt["name"]: opt["id"] for opt in field.get("options", [])}
                break

        logger.debug(
            "Fetched project metadata: id=%s, status_field=%s, options=%s",
            self._project_id,
            self._status_field_id,
            list(self._status_options.keys()),
        )

    def _create_github_issue(self, task: Task) -> str:
        """Create a GitHub issue from a local task.

        Args:
            task: The task to create as an issue

        Returns:
            Issue ID in format "owner/repo#number"
        """
        from ..github.queries import (
            ADD_ITEM_TO_PROJECT,
            ADD_LABELS,
            CREATE_ISSUE,
            GET_REPOSITORY,
            UPDATE_ITEM_FIELD,
        )

        github_config = self._get_github_config()
        board_config = self._get_board_config()

        repo = github_config.default_repo
        if not repo:
            raise ValueError("default_repo is required")

        # Get repository ID
        owner, name = repo.split("/")
        repo_result = self._client.query(GET_REPOSITORY, {"owner": owner, "name": name})
        repo_data = repo_result.get("repository")
        if not repo_data:
            raise ValueError(f"Repository not found: {repo}")
        repo_id = repo_data["id"]

        # Create the issue
        issue_result = self._client.mutate(
            CREATE_ISSUE,
            {
                "repositoryId": repo_id,
                "title": task.title or task.display_title,
                "body": task.body,
            },
        )
        issue_data = issue_result.get("createIssue", {}).get("issue", {})
        issue_node_id = issue_data["id"]
        issue_number = issue_data["number"]
        issue_id = f"{repo}#{issue_number}"

        # Add to project if we have project metadata
        project_item_id = None
        if self._project_id:
            add_result = self._client.mutate(
                ADD_ITEM_TO_PROJECT,
                {
                    "projectId": self._project_id,
                    "contentId": issue_node_id,
                },
            )
            project_item_id = add_result.get("addProjectV2ItemById", {}).get("item", {}).get("id")

            # Set status field based on task state
            if project_item_id and self._status_field_id:
                status_name = self._map_state_to_status(task.state)
                if status_name:
                    option_id = self._status_options.get(status_name)
                    if option_id:
                        self._client.mutate(
                            UPDATE_ITEM_FIELD,
                            {
                                "projectId": self._project_id,
                                "itemId": project_item_id,
                                "fieldId": self._status_field_id,
                                "optionId": option_id,
                            },
                        )

        # Add labels for type, priority, and tags
        labels_to_add = self._compute_labels(task, board_config, github_config)
        if labels_to_add:
            label_ids = self._resolve_label_ids(repo, labels_to_add)
            if label_ids:
                self._client.mutate(
                    ADD_LABELS,
                    {
                        "labelableId": issue_node_id,
                        "labelIds": label_ids,
                    },
                )

        return issue_id

    def _update_github_issue(self, task: Task, github_meta: dict) -> None:
        """Update an existing GitHub issue from local task.

        Args:
            task: The local task with changes
            github_meta: GitHub metadata from frontmatter
        """
        from ..github.queries import UPDATE_ISSUE, UPDATE_ITEM_FIELD

        issue_node_id = github_meta.get("issue_node_id")
        if not issue_node_id:
            raise ValueError("Missing issue_node_id in github metadata")

        # Update title and body
        self._client.mutate(
            UPDATE_ISSUE,
            {
                "issueId": issue_node_id,
                "title": task.title,
                "body": task.body,
            },
        )

        # Update status field if we have project metadata
        project_item_id = github_meta.get("project_item_id")
        if project_item_id and self._project_id and self._status_field_id:
            status_name = self._map_state_to_status(task.state)
            if status_name:
                option_id = self._status_options.get(status_name)
                if option_id:
                    self._client.mutate(
                        UPDATE_ITEM_FIELD,
                        {
                            "projectId": self._project_id,
                            "itemId": project_item_id,
                            "fieldId": self._status_field_id,
                            "optionId": option_id,
                        },
                    )

        # TODO: Update labels for type/priority/tags changes (future enhancement)

    # --- Internal: File Operations ---

    def _write_issue_to_file(self, issue: dict, existing_task: Task | None = None) -> Path:
        """Write a GitHub issue to a local markdown file.

        Args:
            issue: Issue dict from GitHub API
            existing_task: Existing local task if updating

        Returns:
            Path to the written file
        """
        content = issue.get("content", {})
        repo = content.get("repository", {}).get("nameWithOwner", "")
        owner, repo_name = repo.split("/") if "/" in repo else ("", "")
        issue_number = content.get("number", 0)
        title = content.get("title", "")
        body = content.get("body", "")

        # Generate filename
        if existing_task:
            filepath = self._task_root / existing_task.id
        else:
            filename = generate_synced_filename(owner, repo_name, issue_number, title)
            filepath = self._task_root / filename

        # Ensure directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Build frontmatter
        board_config = self._get_board_config()
        github_config = self._get_github_config()

        # Extract status and map to state
        state = self._extract_and_map_status(issue)

        # Extract type from labels
        labels = [label.get("name", "") for label in issue.get("labels", [])]
        task_type, type_label = self._extract_type_from_labels(labels, board_config)

        # Extract priority - check field first, then fall back to labels
        priority: str | None = None
        priority_label: str | None = None
        priority_source = "labels"

        if github_config.priority_field:
            priority = self._extract_priority_from_field(issue, github_config.priority_field)
            if priority:
                priority_source = "field"

        if not priority:
            priority, priority_label = self._extract_priority_from_labels(labels, board_config)
            priority_source = "labels"

        # Filter out type/priority labels from tags
        tags = [label for label in labels if label != type_label and label != priority_label]

        # Extract assignees
        assignees_data = content.get("assignees", {}).get("nodes", [])
        assignees = [a.get("login") for a in assignees_data if a.get("login")]

        now = datetime.now(UTC)

        metadata: dict = {
            "title": title,
            "state": state,
            "priority": priority,
            "type": task_type,
            "tags": tags,
            "created": content.get("createdAt"),
            "updated": content.get("updatedAt"),
            "github": {
                "synced": True,
                "issue_number": issue_number,
                "repository": repo,
                "project_item_id": issue.get("project_item_id", ""),
                "issue_node_id": content.get("id", ""),
                "last_synced": now.isoformat(),
                "priority_source": priority_source,
                "priority_label": priority_label,
            },
            "push_changes": False,
            "close_on_github": False,
        }

        # Add assignees if present
        if assignees:
            metadata["assignees"] = assignees

        # Write file
        post = frontmatter.Post(body)
        post.metadata = metadata

        with filepath.open("w") as f:
            f.write(frontmatter.dumps(post, sort_keys=False))

        # Update tasks.yaml
        self._add_to_tasks_yaml(filepath.name, state)

        return filepath

    def _scan_synced_files(self) -> list[Task]:
        """Scan task directory for synced files.

        Returns:
            List of Task objects that are synced from GitHub
        """
        tasks: list[Task] = []

        if not self._task_root.exists():
            return tasks

        for filepath in self._task_root.glob("*.md"):
            if not is_synced_filename(filepath.name):
                continue

            task = self._parse_task_file(filepath)
            if task is not None and self._has_github_metadata(filepath):
                tasks.append(task)

        return tasks

    def _parse_task_file(self, filepath: Path) -> Task | None:
        """Parse a single task file."""
        try:
            post = frontmatter.load(filepath)  # pyrefly: ignore[bad-argument-type]
            task = Task.from_frontmatter(
                task_id=filepath.name,
                metadata=post.metadata,
                body=post.content,
                provider_data=FileProviderData(),
            )
            return task
        except Exception as e:
            logger.warning("Failed to parse task file %s: %s", filepath, e)
            return None

    def _has_github_metadata(self, filepath: Path) -> bool:
        """Check if a task file has GitHub metadata in its frontmatter."""
        try:
            post = frontmatter.load(filepath)  # pyrefly: ignore[bad-argument-type]
            # Check for github: section in frontmatter
            metadata = dict(post.metadata)  # pyrefly: ignore[bad-argument-type]
            github_data = metadata.get("github", {})
            return isinstance(github_data, dict) and github_data.get("synced", False) is True
        except Exception:
            return False

    def _get_github_metadata(self, task: Task) -> dict | None:
        """Get GitHub metadata from task's frontmatter."""
        filepath = self._task_root / task.id
        if not filepath.exists():
            return None

        try:
            post = frontmatter.load(filepath)  # pyrefly: ignore[bad-argument-type]
            metadata = dict(post.metadata)  # pyrefly: ignore[bad-argument-type]
            github_data = metadata.get("github", {})
            if isinstance(github_data, dict) and github_data.get("synced"):
                return github_data
        except Exception:
            pass
        return None

    def _get_push_changes_flag(self, task: Task) -> bool:
        """Get push_changes flag from task's frontmatter."""
        filepath = self._task_root / task.id
        if not filepath.exists():
            return False

        try:
            post = frontmatter.load(filepath)  # pyrefly: ignore[bad-argument-type]
            metadata = dict(post.metadata)  # pyrefly: ignore[bad-argument-type]
            return metadata.get("push_changes", False) is True
        except Exception:
            return False

    def _check_conflict(self, local_task: Task, remote_issue: dict) -> Conflict | None:
        """Check if there's a conflict between local and remote.

        Returns Conflict if both changed since last sync, None otherwise.
        """
        github_meta = self._get_github_metadata(local_task)
        if not github_meta:
            return None

        last_synced = github_meta.get("last_synced")
        if not last_synced:
            return None

        last_synced_dt = self._parse_datetime(last_synced)
        local_updated = local_task.updated
        remote_updated = self._parse_datetime(remote_issue.get("updatedAt", ""))

        local_changed = local_updated and last_synced_dt and local_updated > last_synced_dt
        remote_changed = remote_updated and last_synced_dt and remote_updated > last_synced_dt

        if local_changed and remote_changed:
            return Conflict(
                task_id=local_task.id,
                local_path=str(self._task_root / local_task.id),
                issue_number=github_meta.get("issue_number", 0),
                repository=github_meta.get("repository", ""),
                local_updated=local_updated or datetime.now(UTC),
                remote_updated=remote_updated or datetime.now(UTC),
                last_synced=last_synced_dt or datetime.now(UTC),
            )

        return None

    def _update_sync_metadata(self, task: Task) -> None:
        """Update sync metadata after successful push.

        Sets last_synced to now and push_changes to false.
        """
        filepath = self._task_root / task.id
        if not filepath.exists():
            return

        try:
            post = frontmatter.load(filepath)  # pyrefly: ignore[bad-argument-type]
            now = datetime.now(UTC)

            # Update github.last_synced
            if "github" in post.metadata:
                post.metadata["github"]["last_synced"] = now.isoformat()  # pyrefly: ignore

            # Reset push_changes
            post.metadata["push_changes"] = False

            with filepath.open("w") as f:
                f.write(frontmatter.dumps(post, sort_keys=False))

        except Exception as e:
            logger.warning("Failed to update sync metadata for %s: %s", task.id, e)

    # --- Internal: Helpers ---

    def _get_issue_key_from_task(self, task: Task) -> str:
        """Get issue key from task (repo#number format)."""
        parsed = parse_synced_filename(task.id)
        if parsed:
            return parsed.issue_id
        return task.id

    def _get_issue_key_from_issue(self, issue: dict) -> str:
        """Get issue key from issue dict (repo#number format)."""
        content = issue.get("content", {})
        repo = content.get("repository", {}).get("nameWithOwner", "")
        number = content.get("number", 0)
        return f"{repo}#{number}"

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            # Handle various ISO formats
            if dt_str.endswith("Z"):
                dt_str = dt_str[:-1] + "+00:00"
            return datetime.fromisoformat(dt_str)
        except Exception:
            return None

    def _map_state_to_status(self, state: str) -> str | None:
        """Map task state to GitHub project status name."""
        board_config = self._get_board_config()

        # First check if state matches a status option directly
        if state in self._status_options:
            return state

        # Check column aliases
        for col in board_config.columns:
            if col.id == state:
                # Check if any alias matches a status option
                for alias in col.status_alias:
                    if alias in self._status_options:
                        return alias
                # Also try the column name directly
                if col.id.replace("_", " ").title() in self._status_options:
                    return col.id.replace("_", " ").title()

        # Try common mappings
        state_mappings = {
            "todo": ["Todo", "To Do", "Backlog"],
            "in_progress": ["In Progress", "In progress", "Doing"],
            "done": ["Done", "Completed", "Closed"],
        }
        for local_state, github_names in state_mappings.items():
            if state == local_state:
                for name in github_names:
                    if name in self._status_options:
                        return name

        return None

    def _extract_and_map_status(self, issue: dict) -> str:
        """Extract status from issue and map to local state."""
        # Extract status from field values
        field_values = issue.get("fieldValues", {}).get("nodes", [])
        github_status = None
        for fv in field_values:
            field = fv.get("field", {})
            if field.get("name") == "Status":
                github_status = fv.get("name")
                break

        if not github_status:
            board_config = self._get_board_config()
            return board_config.columns[0].id if board_config.columns else "todo"

        # Map to local state via slugification
        from ..utils.slug import slugify_column_id

        return slugify_column_id(github_status)

    def _extract_type_from_labels(
        self,
        labels: list[str],
        board_config: BoardConfig,
    ) -> tuple[str | None, str | None]:
        """Extract task type from labels."""
        for label in labels:
            for type_config in board_config.types:
                if type_config.matches_label(label):
                    return type_config.id, label
        return None, None

    def _extract_priority_from_field(
        self,
        issue: dict,
        priority_field: str,
    ) -> str | None:
        """Extract priority from GitHub project field.

        Maps field values to priority IDs based on board config.
        Field values like "P1", "P2" are normalized to lowercase.

        Args:
            issue: Issue dict with fieldValues
            priority_field: Name of the priority field (e.g., "Priority")

        Returns:
            Priority ID (lowercase) or None if not found
        """
        field_values = issue.get("fieldValues", {}).get("nodes", [])
        board_config = self._get_board_config()

        for fv in field_values:
            field_name = fv.get("field", {}).get("name", "")
            if field_name == priority_field:
                # Single-select field has "name" attribute
                value = fv.get("name")
                if value:
                    # Try to match against board priorities
                    value_lower = value.lower()
                    for priority_config in board_config.priorities:
                        if priority_config.id.lower() == value_lower:
                            return priority_config.id
                    # If no exact match, return the value as-is (lowercase)
                    return value_lower

        return None

    def _extract_priority_from_labels(
        self,
        labels: list[str],
        board_config: BoardConfig,
    ) -> tuple[str, str | None]:
        """Extract priority from labels."""
        for label in labels:
            for priority_config in board_config.priorities:
                if priority_config.matches_label(label):
                    return priority_config.id, label
        return "medium", None  # Default priority

    def _compute_labels(
        self,
        task: Task,
        board_config: BoardConfig,
        github_config: GitHubConfig,
    ) -> list[str]:
        """Compute labels to add for a task."""
        labels: list[str] = []

        # Add type label
        if task.type:
            type_config = board_config.get_type(task.type)
            if type_config and type_config.write_alias:
                labels.append(type_config.write_alias)

        # Add priority label (only if not using priority field)
        if not github_config.priority_field and task.priority:
            priority_config = board_config.get_priority(task.priority)
            if priority_config and priority_config.write_alias:
                labels.append(priority_config.write_alias)

        # Add tags as labels
        labels.extend(task.tags)

        return labels

    def _resolve_label_ids(self, repository: str, label_names: list[str]) -> list[str]:
        """Resolve label names to GitHub label IDs."""
        # Fetch repo labels if not cached
        if repository not in self._repo_labels:
            self._fetch_repo_labels(repository)

        label_map = self._repo_labels.get(repository, {})
        return [label_map[name] for name in label_names if name in label_map]

    def _fetch_repo_labels(self, repository: str) -> None:
        """Fetch and cache labels for a repository."""
        from ..github.queries import GET_REPOSITORY_LABELS

        owner, name = repository.split("/")
        try:
            result = self._client.query(GET_REPOSITORY_LABELS, {"owner": owner, "name": name})
            labels_data = result.get("repository", {}).get("labels", {}).get("nodes", [])
            self._repo_labels[repository] = {label["name"]: label["id"] for label in labels_data}
            logger.debug(
                "Fetched %d labels from %s", len(self._repo_labels[repository]), repository
            )
        except Exception as e:
            logger.warning("Failed to fetch labels from %s: %s", repository, e)
            self._repo_labels[repository] = {}

    def _mark_file_archived(self, filepath: Path) -> None:
        """Mark a task file as archived in its frontmatter."""
        post = frontmatter.load(filepath)  # pyrefly: ignore[bad-argument-type]
        post.metadata["archived"] = True
        post.metadata["state"] = "archived"
        post.metadata["updated"] = datetime.now(UTC).isoformat()

        with filepath.open("w") as f:
            f.write(frontmatter.dumps(post, sort_keys=False))

    def _add_to_tasks_yaml(self, task_id: str, state: str) -> None:
        """Add a task to tasks.yaml."""
        yaml_path = self._task_root / "tasks.yaml"

        if yaml_path.exists():
            with yaml_path.open() as f:
                data = yaml.safe_load(f) or {}
        else:
            data = {"columns": {}}

        columns = data.setdefault("columns", {})
        column_tasks = columns.setdefault(state, [])

        if task_id not in column_tasks:
            column_tasks.append(task_id)

        with yaml_path.open("w") as f:
            f.write("# Auto-generated - do not edit manually\n")
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def _remove_from_tasks_yaml(self, task_id: str) -> None:
        """Remove a task from tasks.yaml."""
        yaml_path = self._task_root / "tasks.yaml"
        if not yaml_path.exists():
            return

        with yaml_path.open() as f:
            data = yaml.safe_load(f) or {}

        # Remove from all columns
        columns = data.get("columns", {})
        for column_tasks in columns.values():
            if task_id in column_tasks:
                column_tasks.remove(task_id)

        with yaml_path.open("w") as f:
            f.write("# Auto-generated - do not edit manually\n")
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def _rename_in_tasks_yaml(self, old_id: str, new_id: str) -> None:
        """Rename a task in tasks.yaml."""
        yaml_path = self._task_root / "tasks.yaml"
        if not yaml_path.exists():
            return

        with yaml_path.open() as f:
            data = yaml.safe_load(f) or {}

        # Rename in all columns
        columns = data.get("columns", {})
        for column_tasks in columns.values():
            for i, task_id in enumerate(column_tasks):
                if task_id == old_id:
                    column_tasks[i] = new_id
                    break

        with yaml_path.open("w") as f:
            f.write("# Auto-generated - do not edit manually\n")
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)


# Backward compatibility alias
GitHubPushEngine = GitHubSyncEngine
