"""Provider-specific data models for different storage backends.

This module defines typed data structures for each provider type using
a discriminated union pattern. Each provider has its own model with
fields specific to that backend.

The discriminator field is `provider`, which uses Literal types for
type narrowing support.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FileProviderData(BaseModel):
    """Provider data for filesystem tasks.

    For filesystem tasks, most metadata is derived:
    - filepath is derived from task.id + task_root
    - No additional fields needed

    This model exists primarily to identify file-based tasks
    in the discriminated union.
    """

    provider: Literal["file"] = "file"


class GitHubProviderData(BaseModel):
    """Provider data for GitHub Projects tasks.

    Stores GitHub-specific identifiers needed for GraphQL mutations
    and label roundtrip tracking.
    """

    provider: Literal["github"] = "github"

    # GraphQL identifiers (required for mutations)
    project_item_id: str  # "PVTI_..." - needed for moving items
    issue_node_id: str  # "I_kw..." - needed for issue queries

    # Repository and issue reference
    repository: str  # "owner/repo"
    issue_number: int  # 123

    # Label tracking for roundtrip (original labels that mapped to type/priority)
    type_label: str | None = None
    priority_label: str | None = None

    # Sync tracking (Phase 2)
    last_synced: datetime | None = None  # When this issue was last synced to/from filesystem
    priority_source: str = "labels"  # "labels" or "field" - where priority came from


class GitHubPRProviderData(BaseModel):
    """Provider data for GitHub Pull Request tasks.

    Stores PR-specific data for display and linking.
    This provider is read-only - PRs cannot be modified from sltasks.
    """

    provider: Literal["github-prs"] = "github-prs"

    # Repository and PR reference
    owner: str  # Repository owner
    repo: str  # Repository name
    pr_number: int  # PR number

    # Branch information
    head_branch: str  # Source branch
    base_branch: str  # Target branch

    # Author and status
    author: str  # PR author username
    review_summary: str | None = None  # e.g., "✓2 ○1 ✗0"
    ci_status: str | None = None  # "passing", "failing", "pending"
    is_draft: bool = False


class JiraProviderData(BaseModel):
    """Provider data for Jira tasks.

    Stores Jira-specific identifiers. Unlike GitHub, Jira has native
    priority and issue type fields, so no label tracking is needed.
    """

    provider: Literal["jira"] = "jira"

    # Jira identifiers
    issue_key: str  # "PROJ-123"
    project_key: str  # "PROJ"


# Discriminated union of all provider data types
# Use isinstance() checks to narrow the type
ProviderData = FileProviderData | GitHubProviderData | GitHubPRProviderData | JiraProviderData

# Type alias for optional provider data (used in Task model)
OptionalProviderData = ProviderData | None
