"""GitHub GraphQL API client."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class GitHubClientError(Exception):
    """Base exception for GitHub client errors."""

    pass


class GitHubAuthError(GitHubClientError):
    """Authentication failed."""

    pass


class GitHubNotFoundError(GitHubClientError):
    """Resource not found."""

    pass


class GitHubForbiddenError(GitHubClientError):
    """Permission denied."""

    pass


class GitHubRateLimitError(GitHubClientError):
    """Rate limit exceeded."""

    pass


class GitHubClient:
    """GitHub GraphQL API client.

    Provides a thin wrapper around the GitHub GraphQL API with:
    - Token authentication (from env var or gh CLI)
    - Enterprise support via custom base_url
    - Error handling and rate limit awareness
    """

    def __init__(self, token: str, base_url: str = "api.github.com"):
        """Initialize the GitHub client.

        Args:
            token: GitHub personal access token
            base_url: API base URL (default: api.github.com, use custom for Enterprise)
        """
        self.token = token
        self.base_url = base_url
        self._graphql_url = f"https://{base_url}/graphql"
        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    @classmethod
    def from_environment(cls, base_url: str = "api.github.com") -> GitHubClient:
        """Create a client from environment variables or gh CLI.

        Tries in order:
        1. GITHUB_TOKEN environment variable
        2. gh auth token (if gh CLI is installed and authenticated)

        Args:
            base_url: API base URL

        Returns:
            Configured GitHubClient

        Raises:
            GitHubAuthError: If no token is available
        """
        # Try GITHUB_TOKEN env var first
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            logger.debug("Using token from GITHUB_TOKEN environment variable")
            return cls(token, base_url)

        # Try gh CLI
        try:
            result = subprocess.run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                check=True,
            )
            token = result.stdout.strip()
            if token:
                logger.debug("Using token from gh CLI")
                return cls(token, base_url)
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.debug("gh CLI not available or not authenticated")

        logger.error("No GitHub token found")
        raise GitHubAuthError(
            "No GitHub token found. Either:\n"
            "  - Set GITHUB_TOKEN environment variable\n"
            "  - Run 'gh auth login' to authenticate with GitHub CLI"
        )

    def execute(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query or mutation.

        Args:
            query: GraphQL query/mutation string
            variables: Query variables

        Returns:
            Response data (the 'data' field from GraphQL response)

        Raises:
            GitHubAuthError: Authentication failed
            GitHubNotFoundError: Resource not found
            GitHubForbiddenError: Permission denied
            GitHubRateLimitError: Rate limit exceeded
            GitHubClientError: Other errors
        """
        # Extract operation name for logging (e.g., "query GetProject" -> "GetProject")
        op_match = re.search(r"(?:query|mutation)\s+(\w+)", query)
        op_name = op_match.group(1) if op_match else "anonymous"

        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        # Log request details (DEBUG level for variables to avoid sensitive data at INFO)
        logger.debug("GraphQL %s: variables=%s", op_name, variables)

        start_time = time.monotonic()
        try:
            response = self._client.post(self._graphql_url, json=payload)
        except httpx.RequestError as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error("GraphQL %s failed after %.0fms: %s", op_name, elapsed_ms, e)
            raise GitHubClientError(f"Request failed: {e}") from e

        elapsed_ms = (time.monotonic() - start_time) * 1000

        # Handle HTTP errors
        if response.status_code == 401:
            logger.error("GraphQL %s: 401 Unauthorized (%.0fms)", op_name, elapsed_ms)
            raise GitHubAuthError(
                "Authentication failed. Check your GITHUB_TOKEN.\n"
                "Required scopes: read:project, project, repo"
            )
        if response.status_code == 403:
            # Check if rate limited
            if "rate limit" in response.text.lower():
                logger.error("GraphQL %s: 403 Rate Limited (%.0fms)", op_name, elapsed_ms)
                raise GitHubRateLimitError("GitHub API rate limit exceeded. Try again later.")
            logger.error("GraphQL %s: 403 Forbidden (%.0fms)", op_name, elapsed_ms)
            raise GitHubForbiddenError(
                "Permission denied. Check that your token has the required scopes:\n"
                "  - read:project (for reading project data)\n"
                "  - project (for modifying project items)\n"
                "  - repo (for issue operations)"
            )
        if response.status_code == 404:
            logger.error("GraphQL %s: 404 Not Found (%.0fms)", op_name, elapsed_ms)
            raise GitHubNotFoundError("Resource not found")

        if response.status_code >= 400:
            logger.error("GraphQL %s: HTTP %d (%.0fms)", op_name, response.status_code, elapsed_ms)
            raise GitHubClientError(f"HTTP {response.status_code}: {response.text}")

        # Parse GraphQL response
        try:
            result = response.json()
        except ValueError as e:
            logger.error("GraphQL %s: Invalid JSON response (%.0fms)", op_name, elapsed_ms)
            raise GitHubClientError(f"Invalid JSON response: {e}") from e

        # Check for GraphQL errors
        if "errors" in result:
            errors = result["errors"]
            error_messages = [e.get("message", str(e)) for e in errors]

            # Check for specific error types
            for error in errors:
                error_type = error.get("type", "")
                message = error.get("message", "")

                if error_type == "NOT_FOUND" or "not found" in message.lower():
                    logger.error(
                        "GraphQL %s: Not Found - %s (%.0fms)", op_name, message, elapsed_ms
                    )
                    raise GitHubNotFoundError(message)
                if error_type == "FORBIDDEN" or "permission" in message.lower():
                    logger.error(
                        "GraphQL %s: Forbidden - %s (%.0fms)", op_name, message, elapsed_ms
                    )
                    raise GitHubForbiddenError(message)

            logger.error("GraphQL %s: errors=%s (%.0fms)", op_name, error_messages, elapsed_ms)
            raise GitHubClientError(f"GraphQL errors: {'; '.join(error_messages)}")

        # Success
        logger.info("GraphQL %s: 200 OK (%.0fms)", op_name, elapsed_ms)
        return result.get("data", {})

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL query (alias for execute)."""
        return self.execute(query, variables)

    def mutate(self, mutation: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a GraphQL mutation (alias for execute)."""
        return self.execute(mutation, variables)
