"""GitHub Projects V2 Repository Implementation."""

from __future__ import annotations

import os
from datetime import datetime
from typing import TYPE_CHECKING, Any

import httpx

from ..models import BoardOrder, Priority, Task
from ..models.sltasks_config import BoardConfig, GitHubConfig
from .protocol import RepositoryCapabilities

if TYPE_CHECKING:
    from ..services.config_service import ConfigService


class GitHubRepository:
    """Repository implementation for GitHub Projects V2."""

    def __init__(self, config: GitHubConfig, config_service: ConfigService | None = None) -> None:
        """
        Initialize the GitHub repository.

        Args:
            config: GitHub configuration object
            config_service: Config service for board configuration
        """
        self.config = config
        self._config_service = config_service
        self._token = self._get_token()
        self._client = httpx.Client(
            base_url="https://api.github.com",
            headers={
                "Authorization": f"bearer {self._token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

        # Cache for project metadata
        self._project_id: str | None = None
        self._status_field: dict[str, Any] | None = None
        self._status_options: dict[str, str] = {}  # name -> optionId
        self._status_options_rev: dict[str, str] = {}  # optionId -> name

        # Cache for tasks
        self._tasks: dict[str, Task] = {}

    @property
    def capabilities(self) -> RepositoryCapabilities:
        """Get repository capabilities (Read-only for now)."""
        return RepositoryCapabilities(
            can_create=False,
            can_edit=False,
            can_delete=False,
            can_move_column=False,
            can_reorder=False,
            can_archive=False,
        )

    def _get_token(self) -> str:
        """Get GitHub token from environment."""
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            # Try gh CLI if available (placeholder logic)
            # For now, just raise error if env var is missing
            raise ValueError("GITHUB_TOKEN environment variable is not set")
        return token

    def ensure_directory(self) -> None:
        """No-op for GitHub repository."""
        pass

    def _get_board_config(self) -> BoardConfig:
        """Get board config, using default if no config service."""
        if self._config_service:
            return self._config_service.get_board_config()
        return BoardConfig.default()

    def _query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query."""
        response = self._client.post(
            "/graphql", json={"query": query, "variables": variables or {}}
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL Error: {data['errors']}")
        return data["data"]

    def _fetch_project_metadata(self) -> None:
        """Fetch project ID and fields."""
        if self._project_id:
            return

        # Query to find project and status field
        if self.config.project_url:
            # Parse URL to get owner and number
            # https://github.com/orgs/myorg/projects/5
            # https://github.com/users/myuser/projects/5
            # https://github.com/users/myuser/projects/5/views/1
            parts = self.config.project_url.rstrip("/").split("/")

            # Remove views/X suffix if present
            if "views" in parts:
                views_idx = parts.index("views")
                parts = parts[:views_idx]

            try:
                project_number = int(parts[-1])
                owner = parts[-3]
                is_org = parts[-4] == "orgs"
            except (ValueError, IndexError) as err:
                raise ValueError(f"Invalid project URL: {self.config.project_url}") from err
        else:
            owner = self.config.owner
            project_number = self.config.project_number
            is_org = self.config.owner_type == "org"

        if not owner or not project_number:
            raise ValueError("GitHub configuration requires project_url or owner/project_number")

        query_root = "organization(login: $owner)" if is_org else "user(login: $owner)"

        query = f"""
        query GetProject($owner: String!, $number: Int!) {{
            {query_root} {{
                projectV2(number: $number) {{
                    id
                    title
                    fields(first: 20) {{
                        nodes {{
                            ... on ProjectV2SingleSelectField {{
                                id
                                name
                                options {{
                                    id
                                    name
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
        """

        data = self._query(query, {"owner": owner, "number": project_number})
        root = data["organization"] if is_org else data["user"]
        project = root.get("projectV2")

        if not project:
            raise ValueError(f"Project not found: {owner}/projects/{project_number}")

        self._project_id = project["id"]

        # Find status field
        for field in project["fields"]["nodes"]:
            if field.get("name") == "Status":
                self._status_field = field
                for opt in field["options"]:
                    self._status_options[opt["name"]] = opt["id"]
                    self._status_options_rev[opt["id"]] = opt["name"]
                break

        if not self._status_field:
            raise ValueError("Status field not found in project")

    def get_all(self) -> list[Task]:
        """Fetch all tasks from GitHub Project."""
        self._fetch_project_metadata()
        self._tasks.clear()

        query = """
        query GetItems($projectId: ID!, $cursor: String) {
            node(id: $projectId) {
                ... on ProjectV2 {
                    items(first: 100, after: $cursor) {
                        pageInfo {
                            hasNextPage
                            endCursor
                        }
                        nodes {
                            id
                            fieldValues(first: 20) {
                                nodes {
                                    ... on ProjectV2ItemFieldSingleSelectValue {
                                        name
                                        field {
                                            ... on ProjectV2FieldCommon {
                                                name
                                            }
                                        }
                                    }
                                }
                            }
                            content {
                                ... on Issue {
                                    id
                                    number
                                    title
                                    body
                                    state
                                    createdAt
                                    updatedAt
                                    repository {
                                        nameWithOwner
                                    }
                                    labels(first: 10) {
                                        nodes {
                                            name
                                        }
                                    }
                                }
                                ... on PullRequest {
                                    id
                                    number
                                    title
                                    body
                                    state
                                    createdAt
                                    updatedAt
                                    repository {
                                        nameWithOwner
                                    }
                                    labels(first: 10) {
                                        nodes {
                                            name
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        """

        cursor = None
        has_next = True

        while has_next:
            data = self._query(query, {"projectId": self._project_id, "cursor": cursor})
            items_data = data["node"]["items"]

            for node in items_data["nodes"]:
                task = self._parse_item(node)
                if task:
                    self._tasks[task.filename] = task

            has_next = items_data["pageInfo"]["hasNextPage"]
            cursor = items_data["pageInfo"]["endCursor"]

        return list(self._tasks.values())

    def _parse_item(self, node: dict[str, Any]) -> Task | None:
        """Parse a GitHub Project item into a Task."""
        content = node.get("content")
        if not content:
            # Draft issue or redacted item
            return None

        # Determine status
        status = "todo"  # Default
        for fv in node.get("fieldValues", {}).get("nodes", []):
            if fv.get("field", {}).get("name") == "Status":
                status = fv.get("name", "todo")
                break

        # Map status to board columns
        board_config = self._get_board_config()
        canonical_state = board_config.resolve_status(status.lower())

        # If the status is not mapped and not valid, default to first column
        if not board_config.is_valid_status(canonical_state):
            # Try mapping case-insensitive match against alias
            pass  # For now, let it be what it is, UI handles unknown columns by hiding or putting in 'archived'?
            # Actually UI might crash if unknown state.
            # Sltasks treats unknown states as just another state, but board view needs them in columns.
            # If status doesn't match a column, it won't show up on board unless we map it.
            # Let's trust the resolve_status which handles aliases.
            pass

        # Parse labels for tags and priority
        labels = [label["name"] for label in content.get("labels", {}).get("nodes", [])]

        priority = Priority.MEDIUM
        tags = []
        task_type = None

        for label in labels:
            lower_label = label.lower()
            if lower_label in ("priority:high", "high", "p1"):
                priority = Priority.HIGH
            elif lower_label in ("priority:critical", "critical", "p0"):
                priority = Priority.CRITICAL
            elif lower_label in ("priority:low", "low", "p3"):
                priority = Priority.LOW
            elif lower_label in ("bug", "type:bug"):
                task_type = "bug"
            elif lower_label in ("feature", "type:feature"):
                task_type = "feature"
            else:
                tags.append(label)

        repo = content["repository"]["nameWithOwner"]
        number = content["number"]
        filename = f"{repo}#{number}"

        return Task(
            filename=filename,
            filepath=None,  # No local file
            title=content["title"],
            state=canonical_state,
            priority=priority,
            tags=tags,
            type=task_type,
            created=self._parse_datetime(content["createdAt"]),
            updated=self._parse_datetime(content["updatedAt"]),
            body=content["body"] or "",
        )

    def _parse_datetime(self, val: str) -> datetime:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))

    def get_by_id(self, filename: str) -> Task | None:
        """Get task by filename (ID)."""
        # If we have it in cache, return it
        if filename in self._tasks:
            return self._tasks[filename]

        # Otherwise we might need to fetch all, since fetching single by ID
        # is harder with just 'owner/repo#123' without parsing and using issue API
        # which returns Issue, not ProjectItem.
        # For MVP/Phase 1, relying on get_all cache is acceptable.
        self.get_all()
        return self._tasks.get(filename)

    def save(self, task: Task) -> Task:
        """Save task - Not implemented for Read-Only."""
        raise NotImplementedError("GitHub integration is currently read-only")

    def delete(self, filename: str) -> None:
        """Delete task - Not implemented for Read-Only."""
        raise NotImplementedError("GitHub integration is currently read-only")

    def get_board_order(self) -> BoardOrder:
        """
        Generate board order from fetched tasks.

        GitHub Projects have their own order, but capturing it exactly requires
        fetching 'previousItemId' or using the 'rank' field if exposed.
        For Phase 1, we will just list tasks in the order returned by the API
        (usually creation or update order depending on query) grouped by status.
        """
        # Ensure we have data
        if not self._tasks:
            self.get_all()

        config = self._get_board_config()
        order = BoardOrder.from_config(config)

        # Populate columns
        for task in self._tasks.values():
            if task.state in order.columns:
                order.columns[task.state].append(task.filename)
            elif task.state == "archived":
                # Ensure archived column exists if we have archived tasks
                if "archived" not in order.columns:
                    order.columns["archived"] = []
                order.columns["archived"].append(task.filename)
            else:
                # Handle unknown states -> put in first column or ignore?
                # Better to put in first column (todo) or a special 'unknown' if we wanted
                # But for now, if resolve_status didn't map it, it might be a custom status
                # that we don't have a column for.
                # Let's append to the first column as a fallback if it's not mapped.
                pass

        return order

    def save_board_order(self, order: BoardOrder) -> None:
        """Save board order - Not implemented for Read-Only."""
        pass  # No-op or raise, but board service might call it. Better to no-op for now.

    def rename_in_board_order(self, old_filename: str, new_filename: str) -> None:
        pass

    def reload(self) -> None:
        """Reload tasks."""
        self._tasks.clear()
        self._project_id = None  # Force re-fetch of metadata just in case
        self.get_all()
