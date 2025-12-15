"""GitHub Projects repository for task storage."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from ..github import GitHubClient, GitHubClientError
from ..github.queries import (
    ADD_ITEM_TO_PROJECT,
    ADD_LABELS,
    CLOSE_ISSUE,
    CREATE_ISSUE,
    GET_ORG_PROJECT,
    GET_PROJECT_ITEMS,
    GET_REPOSITORY,
    GET_REPOSITORY_LABELS,
    GET_USER_PROJECT,
    REMOVE_LABELS,
    UPDATE_ISSUE,
    UPDATE_ITEM_FIELD,
    UPDATE_ITEM_POSITION,
)
from ..models import BoardOrder, GitHubProviderData, Task
from ..models.sltasks_config import BoardConfig, ColumnConfig, GitHubConfig
from ..utils.slug import slugify_column_id

if TYPE_CHECKING:
    from ..services.config_service import ConfigService

logger = logging.getLogger(__name__)


class GitHubProjectsRepository:
    """Repository for GitHub Projects.

    Implements the RepositoryProtocol to store tasks in GitHub Projects.
    Issues are fetched via GraphQL and mapped to Task objects.
    """

    def __init__(self, config_service: ConfigService) -> None:
        """Initialize the repository.

        Args:
            config_service: Config service for GitHub and board configuration
        """
        self._config_service = config_service
        self._client: GitHubClient | None = None

        # Cached data
        self._tasks: dict[str, Task] = {}
        self._board_order: BoardOrder | None = None

        # Project metadata (populated on first access)
        self._project_id: str | None = None
        self._project_title: str | None = None
        self._status_field_id: str | None = None
        self._status_options: dict[str, str] = {}  # option_name -> option_id
        self._reverse_status_options: dict[str, str] = {}  # option_id -> option_name
        self._status_options_ordered: list[str] = []  # Status options in order

        # All single-select fields (for priority field and --github-setup)
        self._single_select_fields: dict[str, dict[str, Any]] = {}  # field_name -> field_info

        # Priority field support (when github.priority_field is configured)
        self._priority_field_id: str | None = None
        self._priority_options: dict[str, str] = {}  # option_name -> option_id
        self._priority_options_ordered: list[str] = []  # Priority options in order

        # Auto-generated columns (when board.columns matches Status field)
        self._generated_columns: list[ColumnConfig] | None = None

        # Repository labels cache (repo -> {label_name: label_id})
        self._repo_labels: dict[str, dict[str, str]] = {}

    # --- Configuration Helpers ---

    def _get_github_config(self) -> GitHubConfig:
        """Get GitHub config from config service."""
        config = self._config_service.get_config()
        if config.github is None:
            raise ValueError("GitHub configuration is required when provider is 'github'")
        return config.github

    def _get_board_config(self) -> BoardConfig:
        """Get board config from config service."""
        return self._config_service.get_board_config()

    def _ensure_client(self) -> GitHubClient:
        """Get or create the GitHub client."""
        if self._client is None:
            github_config = self._get_github_config()
            self._client = GitHubClient.from_environment(github_config.base_url)
        return self._client

    # --- RepositoryProtocol Implementation ---

    def get_all(self) -> list[Task]:
        """Load all tasks from GitHub Project."""
        self._fetch_project_metadata()
        self._fetch_items()
        return self._sorted_tasks()

    def get_by_id(self, task_id: str) -> Task | None:
        """Get a task by ID.

        Args:
            task_id: Task ID in format "owner/repo#123"

        Returns:
            Task if found, None otherwise
        """
        # Ensure tasks are loaded
        if not self._tasks:
            self.get_all()
        return self._tasks.get(task_id)

    def save(self, task: Task) -> Task:
        """Save a task (create or update)."""
        if task.provider_data is None:
            # New task - create issue in GitHub
            return self._create_issue(task)
        elif isinstance(task.provider_data, GitHubProviderData):
            # Existing task - update
            return self._update_issue(task)
        else:
            raise ValueError(f"Cannot save task with provider: {task.provider_data}")

    def delete(self, task_id: str) -> None:
        """Delete a task (close the issue)."""
        task = self.get_by_id(task_id)
        if task is None:
            logger.debug("delete: task not found: %s", task_id)
            return

        if not isinstance(task.provider_data, GitHubProviderData):
            return

        logger.debug("Closing GitHub issue: %s", task_id)
        client = self._ensure_client()
        try:
            client.mutate(
                CLOSE_ISSUE,
                {"issueId": task.provider_data.issue_node_id},
            )
            logger.info("Closed GitHub issue: %s", task_id)
        except GitHubClientError as e:
            # Issue may already be closed
            logger.debug("Failed to close issue (may already be closed): %s", e)

        # Remove from cache
        self._tasks.pop(task_id, None)
        if self._board_order:
            self._board_order.remove_task(task_id)

    def get_board_order(self) -> BoardOrder:
        """Get the board order (derived from cached tasks)."""
        if self._board_order is None:
            self._build_board_order()
        return self._board_order or BoardOrder.default()

    def save_board_order(self, order: BoardOrder) -> None:
        """Save board order.

        For GitHub, this updates task states via field value updates.
        Position ordering is handled separately via updateProjectV2ItemPosition.
        """
        self._board_order = order
        # Note: Individual task moves are handled in save() by updating
        # the Status field. Position reordering uses reorder_task().

    def reorder_task(self, task_id: str, after_task_id: str | None) -> bool:
        """Reorder a task to appear after another task in GitHub Projects.

        Args:
            task_id: The task to move
            after_task_id: The task it should appear after (None for first position)

        Returns:
            True if reordering was persisted to GitHub
        """
        task = self.get_by_id(task_id)
        if task is None or not isinstance(task.provider_data, GitHubProviderData):
            logger.warning("reorder_task: task not found or invalid provider: %s", task_id)
            return False

        after_item_id = None
        if after_task_id:
            after_task = self.get_by_id(after_task_id)
            if after_task and isinstance(after_task.provider_data, GitHubProviderData):
                after_item_id = after_task.provider_data.project_item_id
            else:
                logger.warning("reorder_task: after_task not found: %s", after_task_id)

        client = self._ensure_client()
        self._fetch_project_metadata()

        logger.debug(
            "Reordering task %s after %s (item_id=%s, after_id=%s)",
            task_id,
            after_task_id,
            task.provider_data.project_item_id,
            after_item_id,
        )

        client.mutate(
            UPDATE_ITEM_POSITION,
            {
                "projectId": self._project_id,
                "itemId": task.provider_data.project_item_id,
                "afterId": after_item_id,
            },
        )

        logger.info("Reordered task %s in GitHub project", task_id)
        return True

    def reload(self) -> None:
        """Clear caches and reload from GitHub."""
        logger.debug("Reloading GitHub project data")
        self._tasks.clear()
        self._board_order = None
        # Keep project metadata - it doesn't change often

    def rename_in_board_order(self, old_task_id: str, new_task_id: str) -> None:
        """Rename a task in board order.

        For GitHub, task IDs don't change (issue numbers are permanent).
        """
        pass  # No-op for GitHub

    def validate(self) -> tuple[bool, str | None]:
        """Validate GitHub configuration and connectivity.

        Returns:
            (True, None) if valid, (False, error_message) otherwise
        """
        try:
            # Check that GitHub config exists
            github_config = self._get_github_config()

            # Check that project can be identified
            owner, owner_type, project_number = github_config.get_project_info()

            # Check connectivity and authentication
            client = self._ensure_client()

            # Try to fetch the project
            query = GET_USER_PROJECT if owner_type == "user" else GET_ORG_PROJECT
            result = client.query(query, {"owner": owner, "number": project_number})

            # Check if project was found
            owner_key = "user" if owner_type == "user" else "organization"
            project_data = result.get(owner_key, {}).get("projectV2")
            if not project_data:
                return (
                    False,
                    f"Project not found: {owner}/projects/{project_number}\n"
                    "Check the project URL and your access permissions.",
                )

            # Store project ID for later use
            self._project_id = project_data["id"]

            # Find Status field and all single-select fields
            self._extract_status_field(project_data)
            if not self._status_field_id:
                return (
                    False,
                    "Status field not found in project.\n"
                    "Ensure your GitHub Project has a Status field configured.",
                )

            # Validate board.columns against GitHub Status options
            validation_error = self._validate_columns_against_status()
            if validation_error:
                return (False, validation_error)

            # Validate priority field if configured
            if github_config.priority_field:
                validation_error = self._validate_priority_field(github_config.priority_field)
                if validation_error:
                    return (False, validation_error)

            return (True, None)

        except GitHubClientError as e:
            return (False, str(e))
        except ValueError as e:
            return (False, str(e))

    def _validate_columns_against_status(self) -> str | None:
        """Validate that board.columns match GitHub Status options.

        Returns:
            Error message if validation fails, None if valid
        """
        board_config = self._get_board_config()

        # Build set of valid slugified status names
        valid_column_ids = {slugify_column_id(name) for name in self._status_options}

        # Check each configured column
        for col in board_config.columns:
            if col.id not in valid_column_ids:
                available = ", ".join(sorted(valid_column_ids))
                return (
                    f"Column '{col.id}' not found in GitHub project.\n"
                    f"Available columns: {available}\n"
                    "Run 'sltasks --github-setup' to regenerate configuration."
                )

        return None

    def _validate_priority_field(self, field_name: str) -> str | None:
        """Validate that the configured priority field exists.

        Returns:
            Error message if validation fails, None if valid
        """
        if field_name not in self._single_select_fields:
            available = ", ".join(sorted(self._single_select_fields.keys()))
            return (
                f"Priority field '{field_name}' not found in GitHub project.\n"
                f"Available single-select fields: {available}\n"
                "Run 'sltasks --github-setup' to reconfigure."
            )
        return None

    def get_project_metadata(self) -> dict[str, Any]:
        """Get project metadata for --github-setup command.

        Returns:
            Dict with project title, status options, and single-select fields
        """
        # Ensure metadata is loaded
        self._fetch_project_metadata()

        return {
            "project_title": self._project_title,
            "project_id": self._project_id,
            "status_options": self._status_options_ordered,
            "single_select_fields": {
                name: {
                    "name": info["name"],
                    "options": [opt["name"] for opt in info.get("options", [])],
                }
                for name, info in self._single_select_fields.items()
            },
        }

    def get_status_column_ids(self) -> list[str]:
        """Get column IDs derived from GitHub Status options.

        Returns:
            List of column IDs in the same order as Status options
        """
        return [slugify_column_id(name) for name in self._status_options_ordered]

    # --- Private Methods ---

    def _fetch_project_metadata(self) -> None:
        """Fetch project metadata if not already cached."""
        if self._project_id is not None:
            return

        github_config = self._get_github_config()
        owner, owner_type, project_number = github_config.get_project_info()

        client = self._ensure_client()
        query = GET_USER_PROJECT if owner_type == "user" else GET_ORG_PROJECT
        result = client.query(query, {"owner": owner, "number": project_number})

        owner_key = "user" if owner_type == "user" else "organization"
        project_data = result.get(owner_key, {}).get("projectV2")
        if not project_data:
            raise ValueError(f"Project not found: {owner}/projects/{project_number}")

        self._project_id = project_data["id"]
        self._extract_status_field(project_data)

    def _extract_project_fields(self, project_data: dict[str, Any]) -> None:
        """Extract all project fields including Status field and single-select fields."""
        self._project_title = project_data.get("title", "")
        fields = project_data.get("fields", {}).get("nodes", [])

        # Clear previous state
        self._single_select_fields.clear()

        for field in fields:
            field_name = field.get("name", "")

            # Store all single-select fields
            if "options" in field:
                self._single_select_fields[field_name] = {
                    "id": field["id"],
                    "name": field_name,
                    "options": field.get("options", []),
                }

            # Extract Status field specifically
            if field_name == "Status" and "options" in field:
                self._status_field_id = field["id"]
                options = field.get("options", [])
                self._status_options = {opt["name"]: opt["id"] for opt in options}
                self._reverse_status_options = {opt["id"]: opt["name"] for opt in options}
                self._status_options_ordered = [opt["name"] for opt in options]

        # Extract priority field if configured
        github_config = self._get_github_config()
        if github_config.priority_field:
            self._extract_priority_field(github_config.priority_field)

    def _extract_priority_field(self, field_name: str) -> None:
        """Extract priority field info if it exists."""
        field_info = self._single_select_fields.get(field_name)
        if field_info:
            self._priority_field_id = field_info["id"]
            options = field_info.get("options", [])
            self._priority_options = {opt["name"]: opt["id"] for opt in options}
            self._priority_options_ordered = [opt["name"] for opt in options]

    def _extract_status_field(self, project_data: dict[str, Any]) -> None:
        """Extract Status field ID and options from project data.

        This is a backwards-compatible wrapper around _extract_project_fields.
        """
        self._extract_project_fields(project_data)

    def _fetch_items(self) -> None:
        """Fetch all project items (issues and PRs)."""
        logger.debug("Fetching project items")
        self._tasks.clear()

        if self._project_id is None:
            self._fetch_project_metadata()

        client = self._ensure_client()
        github_config = self._get_github_config()

        cursor = None
        page_count = 0
        while True:
            page_count += 1
            result = client.query(
                GET_PROJECT_ITEMS,
                {"projectId": self._project_id, "cursor": cursor},
            )

            project_node = result.get("node", {})
            items_data = project_node.get("items", {})
            items = items_data.get("nodes", [])

            logger.debug("Page %d: fetched %d items", page_count, len(items))

            for item in items:
                task = self._map_item_to_task(item, github_config)
                if task:
                    self._tasks[task.id] = task

            # Check for pagination
            page_info = items_data.get("pageInfo", {})
            if page_info.get("hasNextPage"):
                cursor = page_info.get("endCursor")
            else:
                break

        logger.info("Fetched %d tasks from GitHub project", len(self._tasks))

        # Build board order from tasks
        self._build_board_order()

    def _map_item_to_task(self, item: dict[str, Any], github_config: GitHubConfig) -> Task | None:
        """Map a GitHub project item to a Task."""
        content = item.get("content")
        if content is None:
            return None  # Draft issue without content

        # Check content type
        content_type = self._get_content_type(content)
        if content_type == "DraftIssue" and not github_config.include_drafts:
            return None
        if content_type == "PullRequest":
            if not github_config.include_prs:
                return None
            if content.get("isDraft") and not github_config.include_drafts:
                return None
        if (
            content_type == "Issue"
            and content.get("state") == "CLOSED"
            and not github_config.include_closed
        ):
            return None

        # Extract repository info
        repo_data = content.get("repository", {})
        repository = repo_data.get("nameWithOwner", "")
        issue_number = content.get("number", 0)

        # Build task ID
        task_id = f"{repository}#{issue_number}"

        # Extract GitHub status from field values
        github_status = self._extract_github_status(item)

        # Map status to sltasks state
        state = self._map_status_to_state(github_status)

        # Extract labels
        labels = [label["name"] for label in content.get("labels", {}).get("nodes", [])]

        # Extract type from labels
        task_type, type_label = self._extract_type_from_labels(labels)

        # Extract priority - from project field if configured, otherwise from labels
        priority, priority_label = self._extract_priority_from_item(item, labels, github_config)

        # Filter out type/priority labels from tags
        tags = [label for label in labels if label != type_label and label != priority_label]

        # Parse timestamps
        created = self._parse_timestamp(content.get("createdAt"))
        updated = self._parse_timestamp(content.get("updatedAt"))

        return Task(
            id=task_id,
            title=content.get("title", ""),
            state=state,
            priority=priority,
            type=task_type,
            tags=tags,
            body=content.get("body", ""),
            created=created,
            updated=updated,
            provider_data=GitHubProviderData(
                project_item_id=item["id"],
                issue_node_id=content.get("id", ""),
                repository=repository,
                issue_number=issue_number,
                type_label=type_label,
                priority_label=priority_label,
            ),
        )

    def _get_content_type(self, content: dict[str, Any]) -> str:
        """Determine content type (Issue, PullRequest, DraftIssue)."""
        if "isDraft" in content:
            return "PullRequest"
        if "number" in content:
            return "Issue"
        return "DraftIssue"

    def _extract_github_status(self, item: dict[str, Any]) -> str | None:
        """Extract the Status field value from a project item."""
        field_values = item.get("fieldValues", {}).get("nodes", [])
        for fv in field_values:
            field = fv.get("field", {})
            if field.get("name") == "Status":
                return fv.get("name")
        return None

    def _map_status_to_state(self, github_status: str | None) -> str:
        """Map GitHub Status field value to sltasks column ID.

        Uses direct slugification: "In Progress" -> "in_progress"
        """
        if github_status is None:
            board_config = self._get_board_config()
            return board_config.columns[0].id if board_config.columns else "todo"

        # Direct mapping via slugify_column_id
        return slugify_column_id(github_status)

    def _map_state_to_status(self, state: str) -> str | None:
        """Map sltasks column ID to GitHub Status field value.

        Finds the Status option whose slugified name matches the state.
        """
        # Find status option that slugifies to this state
        for status_name in self._status_options:
            if slugify_column_id(status_name) == state:
                return status_name

        return None

    def _extract_type_from_labels(self, labels: list[str]) -> tuple[str | None, str | None]:
        """Extract task type from labels.

        Returns:
            (type_id, matched_label) or (None, None) if no match
        """
        board_config = self._get_board_config()

        for label in labels:
            label_lower = label.lower()
            for type_config in board_config.types:
                # Check direct match
                if label_lower == type_config.id:
                    return type_config.id, label
                # Check aliases
                if label_lower in type_config.type_alias:
                    return type_config.id, label
                # Check canonical alias
                if (
                    type_config.canonical_alias
                    and label_lower == type_config.canonical_alias.lower()
                ):
                    return type_config.id, label

        return None, None

    def _extract_priority_from_item(
        self,
        item: dict[str, Any],
        labels: list[str],
        github_config: GitHubConfig,
    ) -> tuple[str, str | None]:
        """Extract priority from project field or labels.

        If github_config.priority_field is set, reads priority from that field.
        Otherwise falls back to label-based extraction.

        Returns:
            (priority_id, matched_label) - defaults to "medium" if no match
        """
        # If priority field is configured, try to read from it
        if github_config.priority_field and self._priority_field_id:
            priority = self._extract_priority_from_field(item, github_config.priority_field)
            if priority:
                return priority, None  # No label when using project field

        # Fall back to label-based priority
        return self._extract_priority_from_labels(labels)

    def _extract_priority_from_field(self, item: dict[str, Any], field_name: str) -> str | None:
        """Extract priority from a project field.

        Maps the field value to board.priorities by position.

        Returns:
            priority_id if found, None otherwise
        """
        board_config = self._get_board_config()

        # Find the field value
        field_values = item.get("fieldValues", {}).get("nodes", [])
        for fv in field_values:
            field = fv.get("field", {})
            if field.get("name") == field_name:
                option_name = fv.get("name")
                if option_name:
                    # Map by position: first option -> first priority
                    try:
                        option_index = self._priority_options_ordered.index(option_name)
                        if option_index < len(board_config.priorities):
                            return board_config.priorities[option_index].id
                    except ValueError:
                        pass
                break

        return None

    def _extract_priority_from_labels(self, labels: list[str]) -> tuple[str, str | None]:
        """Extract priority from labels.

        Returns:
            (priority_id, matched_label) - defaults to "medium" if no match
        """
        board_config = self._get_board_config()

        for label in labels:
            label_lower = label.lower()
            for priority_config in board_config.priorities:
                # Check direct match
                if label_lower == priority_config.id:
                    return priority_config.id, label
                # Check aliases
                if label_lower in priority_config.priority_alias:
                    return priority_config.id, label
                # Check canonical alias
                if (
                    priority_config.canonical_alias
                    and label_lower == priority_config.canonical_alias.lower()
                ):
                    return priority_config.id, label

        return "medium", None

    def _parse_timestamp(self, ts: str | None) -> datetime | None:
        """Parse ISO timestamp from GitHub."""
        if ts is None:
            return None
        try:
            # GitHub returns ISO format with Z suffix
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _build_board_order(self) -> None:
        """Build board order from cached tasks."""
        board_config = self._get_board_config()
        self._board_order = BoardOrder.from_config(board_config)

        # Add tasks to their columns
        for task_id, task in self._tasks.items():
            self._board_order.add_task(task_id, task.state)

    def _sorted_tasks(self) -> list[Task]:
        """Return tasks sorted by board order."""
        if self._board_order is None:
            return list(self._tasks.values())

        board_config = self._get_board_config()
        column_ids = [col.id for col in board_config.columns] + ["archived"]

        position_map: dict[str, tuple[int, int]] = {}
        for state_idx, state in enumerate(column_ids):
            task_ids = self._board_order.columns.get(state, [])
            for pos_idx, task_id in enumerate(task_ids):
                position_map[task_id] = (state_idx, pos_idx)

        def sort_key(task: Task) -> tuple[int, int, str]:
            if task.id in position_map:
                state_idx, pos_idx = position_map[task.id]
                return (state_idx, pos_idx, task.id)
            return (999, 999, task.id)

        return sorted(self._tasks.values(), key=sort_key)

    # --- Issue Operations ---

    def _create_issue(self, task: Task) -> Task:
        """Create a new GitHub issue and add to project."""
        github_config = self._get_github_config()
        client = self._ensure_client()

        # Get target repository
        repo = github_config.default_repo
        if not repo:
            raise ValueError("default_repo is required in github config to create issues")

        logger.debug("Creating issue in repository: %s", repo)

        # Get repository ID
        owner, name = repo.split("/")
        repo_result = client.query(GET_REPOSITORY, {"owner": owner, "name": name})
        repo_data = repo_result.get("repository")
        if not repo_data:
            raise ValueError(f"Repository not found: {repo}")
        repo_id = repo_data["id"]

        # Create the issue
        issue_result = client.mutate(
            CREATE_ISSUE,
            {
                "repositoryId": repo_id,
                "title": task.title or "Untitled",
                "body": task.body,
            },
        )
        issue_data = issue_result.get("createIssue", {}).get("issue", {})

        # Add to project
        self._fetch_project_metadata()  # Ensure project ID is set
        add_result = client.mutate(
            ADD_ITEM_TO_PROJECT,
            {
                "projectId": self._project_id,
                "contentId": issue_data["id"],
            },
        )
        item_data = add_result.get("addProjectV2ItemById", {}).get("item", {})

        # Set status field
        status_name = self._map_state_to_status(task.state)
        if status_name and self._status_field_id:
            option_id = self._status_options.get(status_name)
            if option_id:
                client.mutate(
                    UPDATE_ITEM_FIELD,
                    {
                        "projectId": self._project_id,
                        "itemId": item_data["id"],
                        "fieldId": self._status_field_id,
                        "optionId": option_id,
                    },
                )

        # Update task with provider data
        task_id = f"{repo}#{issue_data['number']}"
        task.id = task_id
        task.provider_data = GitHubProviderData(
            project_item_id=item_data["id"],
            issue_node_id=issue_data["id"],
            repository=repo,
            issue_number=issue_data["number"],
        )

        # Update timestamps
        task.created = self._parse_timestamp(issue_data.get("createdAt"))
        task.updated = self._parse_timestamp(issue_data.get("updatedAt"))

        # Cache the task
        self._tasks[task_id] = task
        if self._board_order:
            self._board_order.add_task(task_id, task.state)

        logger.info("Created GitHub issue: %s", task_id)
        return task

    def _fetch_repo_labels(self, repository: str) -> dict[str, str]:
        """Fetch labels for a repository, caching the result.

        Args:
            repository: Repository in "owner/repo" format

        Returns:
            Dict mapping label name to label node ID
        """
        if repository in self._repo_labels:
            return self._repo_labels[repository]

        client = self._ensure_client()
        owner, name = repository.split("/")

        try:
            result = client.query(GET_REPOSITORY_LABELS, {"owner": owner, "name": name})
            labels_data = result.get("repository", {}).get("labels", {}).get("nodes", [])
            label_map = {label["name"]: label["id"] for label in labels_data}
            self._repo_labels[repository] = label_map
            logger.debug("Fetched %d labels from %s", len(label_map), repository)
            return label_map
        except GitHubClientError as e:
            logger.warning("Failed to fetch labels from %s: %s", repository, e)
            return {}

    def _compute_label_changes(
        self,
        task: Task,
        old_task: Task | None,
    ) -> tuple[list[str], list[str]]:
        """Compute labels to add and remove based on task changes.

        Args:
            task: The updated task
            old_task: The task before updates (for comparing tags)

        Returns:
            Tuple of (labels_to_add, labels_to_remove)
        """
        if not isinstance(task.provider_data, GitHubProviderData):
            return [], []

        board_config = self._get_board_config()
        github_config = self._get_github_config()
        provider = task.provider_data

        labels_to_add: list[str] = []
        labels_to_remove: list[str] = []

        # Track old labels
        old_type_label = provider.type_label
        old_priority_label = provider.priority_label

        # Handle type label changes
        new_type_label: str | None = None
        if task.type:
            type_config = board_config.get_type(task.type)
            if type_config:
                new_type_label = type_config.write_alias
                if new_type_label != old_type_label:
                    if old_type_label:
                        labels_to_remove.append(old_type_label)
                    labels_to_add.append(new_type_label)
        elif old_type_label:
            # Type was cleared
            labels_to_remove.append(old_type_label)

        # Handle priority label changes (only if NOT using priority field)
        new_priority_label: str | None = None
        if not github_config.priority_field:
            priority_config = board_config.get_priority(task.priority)
            if priority_config:
                new_priority_label = priority_config.write_alias
                if new_priority_label != old_priority_label:
                    if old_priority_label:
                        labels_to_remove.append(old_priority_label)
                    labels_to_add.append(new_priority_label)

        # Handle general tag changes
        if old_task:
            old_tags = set(old_task.tags)
            new_tags = set(task.tags)

            # Add new tags (excluding type/priority labels we're already handling)
            for tag in new_tags - old_tags:
                if tag not in labels_to_add and tag != new_type_label and tag != new_priority_label:
                    labels_to_add.append(tag)

            # Remove old tags (but not if they're type/priority labels)
            for tag in old_tags - new_tags:
                if (
                    tag not in labels_to_remove
                    and tag != old_type_label
                    and tag != old_priority_label
                ):
                    labels_to_remove.append(tag)

        return labels_to_add, labels_to_remove

    def _update_labels(
        self,
        issue_node_id: str,
        repository: str,
        labels_to_add: list[str],
        labels_to_remove: list[str],
    ) -> None:
        """Update labels on an issue.

        Args:
            issue_node_id: The issue's GraphQL node ID
            repository: The repository (owner/repo format)
            labels_to_add: Label names to add
            labels_to_remove: Label names to remove
        """
        if not labels_to_add and not labels_to_remove:
            return

        client = self._ensure_client()
        repo_labels = self._fetch_repo_labels(repository)

        # Remove labels first
        if labels_to_remove:
            remove_ids = [repo_labels[name] for name in labels_to_remove if name in repo_labels]
            if remove_ids:
                try:
                    client.mutate(
                        REMOVE_LABELS,
                        {"labelableId": issue_node_id, "labelIds": remove_ids},
                    )
                    logger.debug("Removed labels: %s", labels_to_remove)
                except GitHubClientError as e:
                    logger.warning("Failed to remove labels: %s", e)

        # Add labels
        if labels_to_add:
            add_ids = [repo_labels[name] for name in labels_to_add if name in repo_labels]
            if add_ids:
                try:
                    client.mutate(
                        ADD_LABELS,
                        {"labelableId": issue_node_id, "labelIds": add_ids},
                    )
                    logger.debug("Added labels: %s", labels_to_add)
                except GitHubClientError as e:
                    logger.warning("Failed to add labels: %s", e)

            # Warn about missing labels
            missing = [name for name in labels_to_add if name not in repo_labels]
            if missing:
                logger.warning(
                    "Labels not found in repository %s (will not be created): %s",
                    repository,
                    missing,
                )

    def _update_priority_field(self, task: Task) -> None:
        """Update the priority field for a task if priority_field is configured.

        Maps task.priority to the corresponding field option by position.
        """
        github_config = self._get_github_config()
        if not github_config.priority_field or not self._priority_field_id:
            return

        if not isinstance(task.provider_data, GitHubProviderData):
            return

        board_config = self._get_board_config()

        # Find the priority index
        try:
            priority_index = board_config.priority_ids.index(task.priority)
        except ValueError:
            logger.warning("Unknown priority '%s', not updating field", task.priority)
            return

        # Map to GitHub field option
        if priority_index >= len(self._priority_options_ordered):
            logger.warning(
                "Priority index %d exceeds available options (%d), not updating field",
                priority_index,
                len(self._priority_options_ordered),
            )
            return

        option_name = self._priority_options_ordered[priority_index]
        option_id = self._priority_options.get(option_name)

        if option_id:
            client = self._ensure_client()
            try:
                client.mutate(
                    UPDATE_ITEM_FIELD,
                    {
                        "projectId": self._project_id,
                        "itemId": task.provider_data.project_item_id,
                        "fieldId": self._priority_field_id,
                        "optionId": option_id,
                    },
                )
                logger.debug("Updated priority field to: %s", option_name)
            except GitHubClientError as e:
                logger.warning("Failed to update priority field: %s", e)

    def _update_issue(self, task: Task) -> Task:
        """Update an existing GitHub issue."""
        if not isinstance(task.provider_data, GitHubProviderData):
            raise ValueError("Task must have GitHubProviderData")

        logger.debug("Updating GitHub issue: %s", task.id)

        client = self._ensure_client()
        provider = task.provider_data

        # Get the old task state for comparing changes
        old_task = self._tasks.get(task.id)

        # Update issue title and body
        client.mutate(
            UPDATE_ISSUE,
            {
                "issueId": provider.issue_node_id,
                "title": task.title,
                "body": task.body,
            },
        )

        # Update status field if state changed
        self._fetch_project_metadata()  # Ensure status field info is loaded
        status_name = self._map_state_to_status(task.state)
        if not status_name:
            logger.warning(
                "Could not map state '%s' to GitHub status - status will not be updated",
                task.state,
            )
        elif not self._status_field_id:
            logger.warning("Status field ID not set - cannot update status")
        else:
            option_id = self._status_options.get(status_name)
            if not option_id:
                logger.warning(
                    "Status '%s' has no matching option ID - status will not be updated",
                    status_name,
                )
            else:
                logger.debug("Updating status to: %s", status_name)
                client.mutate(
                    UPDATE_ITEM_FIELD,
                    {
                        "projectId": self._project_id,
                        "itemId": provider.project_item_id,
                        "fieldId": self._status_field_id,
                        "optionId": option_id,
                    },
                )

        # Update priority field (if configured)
        self._update_priority_field(task)

        # Compute and apply label changes (type, priority labels, tags)
        labels_to_add, labels_to_remove = self._compute_label_changes(task, old_task)
        self._update_labels(
            provider.issue_node_id,
            provider.repository,
            labels_to_add,
            labels_to_remove,
        )

        # Update provider_data with new label tracking
        board_config = self._get_board_config()
        if task.type:
            type_config = board_config.get_type(task.type)
            provider.type_label = type_config.write_alias if type_config else None
        else:
            provider.type_label = None

        github_config = self._get_github_config()
        if not github_config.priority_field:
            priority_config = board_config.get_priority(task.priority)
            provider.priority_label = priority_config.write_alias if priority_config else None

        # Update cache
        self._tasks[task.id] = task

        logger.info("Updated GitHub issue: %s", task.id)
        return task
