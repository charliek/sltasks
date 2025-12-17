"""GitHub search syntax filter parser for sync operations.

Parses filter expressions like:
- "assignee:@me"
- "label:bug"
- "is:open"
- "assignee:@me label:bug is:open" (AND'd together)
- "*" (match all)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParsedFilter:
    """Parsed representation of a single filter expression.

    Multiple terms in one filter are AND'd together.
    Multiple filters in config are OR'd - any match syncs the issue.
    """

    assignee: str | None = None  # "@me" or specific username
    labels: tuple[str, ...] = field(default_factory=tuple)  # All must match
    milestone: str | None = None
    state: str = "open"  # "open", "closed", "all"
    repo: str | None = None  # "owner/repo" to filter by repository
    is_wildcard: bool = False  # True if filter is "*"
    priority: tuple[str, ...] = field(default_factory=tuple)  # Priority IDs to match (any)


class FilterParseError(ValueError):
    """Raised when a filter expression cannot be parsed."""

    pass


class SyncFilterParser:
    """Parser for GitHub search syntax filter expressions.

    Supported syntax:
    - assignee:@me - issues assigned to authenticated user
    - assignee:USER - issues assigned to specific user
    - label:NAME - issues with specific label (can appear multiple times)
    - is:open / is:closed - filter by state
    - milestone:NAME - issues in milestone
    - repo:owner/name - filter by repository
    - * - match all issues (wildcard)

    Multiple terms in one filter are AND'd together.
    """

    # Pattern for key:value or key:"quoted value"
    TOKEN_PATTERN = re.compile(r'(\w+):(?:"([^"]+)"|(\S+))')

    def parse(self, expression: str) -> ParsedFilter:
        """Parse a filter expression string into a ParsedFilter.

        Args:
            expression: Filter string like "assignee:@me label:bug is:open"

        Returns:
            ParsedFilter with extracted criteria

        Raises:
            FilterParseError: If expression contains invalid syntax
        """
        expression = expression.strip()

        # Handle wildcard
        if expression == "*":
            return ParsedFilter(is_wildcard=True, state="all")

        # Handle empty expression
        if not expression:
            return ParsedFilter()

        # Parse tokens
        assignee: str | None = None
        labels: list[str] = []
        milestone: str | None = None
        state: str = "open"
        repo: str | None = None
        priority: list[str] = []

        for key, value in self._tokenize(expression):
            key_lower = key.lower()

            if key_lower == "assignee":
                assignee = value
            elif key_lower == "label":
                labels.append(value)
            elif key_lower == "milestone":
                milestone = value
            elif key_lower == "is":
                value_lower = value.lower()
                if value_lower == "open":
                    state = "open"
                elif value_lower == "closed":
                    state = "closed"
                else:
                    raise FilterParseError(
                        f"Invalid is: value '{value}'. Expected 'open' or 'closed'."
                    )
            elif key_lower == "repo":
                # Validate repo format
                if "/" not in value:
                    raise FilterParseError(f"Invalid repo format '{value}'. Expected 'owner/repo'.")
                repo = value
            elif key_lower == "priority":
                # Parse comma-separated priorities: "priority:p1,p2" -> ["p1", "p2"]
                priority.extend(p.strip().lower() for p in value.split(",") if p.strip())
            else:
                # Unknown key - fail explicitly rather than silently ignore
                raise FilterParseError(
                    f"Unknown filter key '{key}'. "
                    f"Supported: assignee, label, milestone, is, repo, priority"
                )

        return ParsedFilter(
            assignee=assignee,
            labels=tuple(labels),
            milestone=milestone,
            state=state,
            repo=repo,
            priority=tuple(priority),
        )

    def _tokenize(self, expression: str) -> list[tuple[str, str]]:
        """Extract key:value pairs from expression.

        Args:
            expression: Filter string to tokenize

        Returns:
            List of (key, value) tuples
        """
        tokens: list[tuple[str, str]] = []
        for match in self.TOKEN_PATTERN.finditer(expression):
            key = match.group(1)
            # Use quoted value if present, otherwise unquoted
            value = match.group(2) or match.group(3)
            tokens.append((key, value))
        return tokens

    def matches_issue(
        self,
        filter_: ParsedFilter,
        issue: dict,
        current_user: str,
        priority_field: str | None = None,
        board_priorities: list[str] | None = None,
    ) -> bool:
        """Check if an issue matches the filter criteria.

        All criteria in the filter must match (AND logic).

        Args:
            filter_: Parsed filter to match against
            issue: Issue data dict with fields:
                - assignees: list of {"login": str}
                - labels: list of {"name": str}
                - milestone: {"title": str} or None
                - state: "OPEN" or "CLOSED"
                - repository: {"nameWithOwner": str}
                - fieldValues: {"nodes": [...]} for project fields
            current_user: Authenticated username (for @me expansion)
            priority_field: Name of GitHub project field for priority (e.g., "Priority")
            board_priorities: List of valid priority IDs from board config (e.g., ["p0", "p1", "p2"])

        Returns:
            True if issue matches ALL criteria in the filter
        """
        # Wildcard matches everything
        if filter_.is_wildcard:
            return True

        # Check assignee
        if filter_.assignee is not None:
            expected_user = current_user if filter_.assignee == "@me" else filter_.assignee
            assignees = issue.get("assignees", [])
            assignee_logins = [a.get("login", "") for a in assignees]
            if expected_user not in assignee_logins:
                return False

        # Check labels (all must match)
        if filter_.labels:
            issue_labels = issue.get("labels", [])
            issue_label_names = {label.get("name", "") for label in issue_labels}
            for required_label in filter_.labels:
                if required_label not in issue_label_names:
                    return False

        # Check milestone
        if filter_.milestone is not None:
            issue_milestone = issue.get("milestone")
            if issue_milestone is None:
                return False
            if issue_milestone.get("title") != filter_.milestone:
                return False

        # Check state
        if filter_.state != "all":
            issue_state = issue.get("state", "OPEN").upper()
            expected_state = filter_.state.upper()
            if issue_state != expected_state:
                return False

        # Check repository
        if filter_.repo is not None:
            issue_repo = issue.get("repository", {}).get("nameWithOwner", "")
            if issue_repo.lower() != filter_.repo.lower():
                return False

        # Check priority (any in list matches)
        if filter_.priority:
            issue_priority = self._get_issue_priority(issue, priority_field, board_priorities)
            if issue_priority is None or issue_priority.lower() not in filter_.priority:
                return False

        return True

    def _get_issue_priority(
        self,
        issue: dict,
        priority_field: str | None,
        board_priorities: list[str] | None,
    ) -> str | None:
        """Extract priority from issue data.

        Checks priority field first (if configured), then falls back to labels.

        Args:
            issue: Issue data dict
            priority_field: Name of GitHub project field for priority
            board_priorities: List of valid priority IDs from board config

        Returns:
            Priority ID (lowercase) or None if not found
        """
        # Try to get priority from project field
        if priority_field:
            field_values = issue.get("fieldValues", {}).get("nodes", [])
            for fv in field_values:
                field_name = fv.get("field", {}).get("name", "")
                if field_name == priority_field:
                    # Single-select field has "name" attribute
                    value = fv.get("name")
                    if value:
                        # Map field value to priority ID if we have board config
                        # Field values might be "P1", "P2" etc - normalize to lowercase
                        return value.lower()

        # Fall back to labels - look for "priority:X" pattern
        labels = issue.get("labels", [])
        for label in labels:
            label_name = label.get("name", "")
            if label_name.lower().startswith("priority:"):
                return label_name.split(":", 1)[1].lower()

        # Also check if any label matches a known priority ID
        if board_priorities:
            for label in labels:
                label_name = label.get("name", "").lower()
                if label_name in [p.lower() for p in board_priorities]:
                    return label_name

        return None

    def matches_any_filter(
        self,
        filters: list[ParsedFilter],
        issue: dict,
        current_user: str,
        priority_field: str | None = None,
        board_priorities: list[str] | None = None,
    ) -> bool:
        """Check if an issue matches any of the filters (OR logic).

        Args:
            filters: List of parsed filters
            issue: Issue data dict
            current_user: Authenticated username
            priority_field: Name of GitHub project field for priority
            board_priorities: List of valid priority IDs from board config

        Returns:
            True if issue matches at least one filter
        """
        if not filters:
            # No filters configured - match nothing
            return False

        return any(
            self.matches_issue(filter_, issue, current_user, priority_field, board_priorities)
            for filter_ in filters
        )
