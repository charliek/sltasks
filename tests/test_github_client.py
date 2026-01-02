"""Tests for GitHub GraphQL client."""

from unittest.mock import MagicMock, patch

import pytest

from sltasks.github.client import (
    GitHubAuthError,
    GitHubClient,
    GitHubClientError,
    GitHubForbiddenError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)


class TestGitHubClientInit:
    """Tests for GitHubClient initialization."""

    def test_init_with_token(self):
        """Client initializes with token and default base URL."""
        client = GitHubClient("test-token")
        assert client.token == "test-token"
        assert client.base_url == "api.github.com"
        client.close()

    def test_init_with_custom_base_url(self):
        """Client initializes with custom base URL for Enterprise."""
        client = GitHubClient("test-token", base_url="github.mycompany.com")
        assert client.base_url == "github.mycompany.com"
        assert client._graphql_url == "https://github.mycompany.com/graphql"
        client.close()

    def test_context_manager(self):
        """Client works as context manager."""
        with GitHubClient("test-token") as client:
            assert client.token == "test-token"
        # Client should be closed after context exits


class TestGitHubClientFromEnvironment:
    """Tests for GitHubClient.from_environment."""

    def test_from_github_token_env(self):
        """Client creates from GITHUB_TOKEN env var."""
        with patch.dict("os.environ", {"GITHUB_TOKEN": "env-token"}):
            client = GitHubClient.from_environment()
            assert client.token == "env-token"
            client.close()

    def test_from_gh_cli(self):
        """Client creates from gh CLI token."""
        with patch.dict("os.environ", {}, clear=True):
            mock_result = MagicMock()
            mock_result.stdout = "cli-token\n"
            with patch("subprocess.run", return_value=mock_result):
                client = GitHubClient.from_environment()
                assert client.token == "cli-token"
                client.close()

    def test_raises_when_no_token(self):
        """Client raises GitHubAuthError when no token available."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("subprocess.run", side_effect=FileNotFoundError()),
            pytest.raises(GitHubAuthError) as exc_info,
        ):
            GitHubClient.from_environment()
        assert "No GitHub token found" in str(exc_info.value)


class TestGitHubClientExecute:
    """Tests for GitHubClient.execute method."""

    @pytest.fixture
    def client(self):
        """Create a test client."""
        client = GitHubClient("test-token")
        yield client
        client.close()

    def test_execute_success(self, client):
        """Execute returns data on successful response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"user": {"name": "Test"}}}

        with patch.object(client._client, "post", return_value=mock_response):
            result = client.execute("query { user { name } }")
            assert result == {"user": {"name": "Test"}}

    def test_execute_with_variables(self, client):
        """Execute passes variables to request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"node": {"id": "123"}}}

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            result = client.execute("query($id: ID!) { node(id: $id) { id } }", {"id": "123"})

            # Check variables were passed
            call_args = mock_post.call_args
            assert call_args.kwargs["json"]["variables"] == {"id": "123"}
            assert result == {"node": {"id": "123"}}

    def test_execute_401_raises_auth_error(self, client):
        """Execute raises GitHubAuthError on 401 response."""
        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(GitHubAuthError) as exc_info:
                client.execute("query { viewer { login } }")
            assert "Authentication failed" in str(exc_info.value)

    def test_execute_403_rate_limit_raises_rate_limit_error(self, client):
        """Execute raises GitHubRateLimitError on 403 with rate limit message."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "API rate limit exceeded"

        with (
            patch.object(client._client, "post", return_value=mock_response),
            pytest.raises(GitHubRateLimitError),
        ):
            client.execute("query { viewer { login } }")

    def test_execute_403_permission_raises_forbidden_error(self, client):
        """Execute raises GitHubForbiddenError on 403 permission denied."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Resource not accessible"

        with (
            patch.object(client._client, "post", return_value=mock_response),
            pytest.raises(GitHubForbiddenError),
        ):
            client.execute("query { viewer { login } }")

    def test_execute_404_raises_not_found_error(self, client):
        """Execute raises GitHubNotFoundError on 404 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with (
            patch.object(client._client, "post", return_value=mock_response),
            pytest.raises(GitHubNotFoundError),
        ):
            client.execute('query { node(id: "invalid") { id } }')

    def test_execute_graphql_error_raises_client_error(self, client):
        """Execute raises GitHubClientError on GraphQL errors."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"errors": [{"message": "Field 'foo' doesn't exist"}]}

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(GitHubClientError) as exc_info:
                client.execute("query { foo }")
            assert "foo" in str(exc_info.value)

    def test_execute_graphql_not_found_error(self, client):
        """Execute raises GitHubNotFoundError on NOT_FOUND GraphQL error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"type": "NOT_FOUND", "message": "Could not resolve project"}]
        }

        with (
            patch.object(client._client, "post", return_value=mock_response),
            pytest.raises(GitHubNotFoundError),
        ):
            client.execute('query { node(id: "invalid") { id } }')

    def test_query_alias(self, client):
        """query() is an alias for execute()."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"test": True}}

        with patch.object(client._client, "post", return_value=mock_response):
            result = client.query("query { test }")
            assert result == {"test": True}

    def test_mutate_alias(self, client):
        """mutate() is an alias for execute()."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"updateItem": {"id": "123"}}}

        with patch.object(client._client, "post", return_value=mock_response):
            result = client.mutate("mutation { updateItem { id } }")
            assert result == {"updateItem": {"id": "123"}}
