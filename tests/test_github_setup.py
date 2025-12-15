"""Tests for GitHub setup CLI module."""

from sltasks.cli.github_setup import (
    ProjectMetadata,
    find_priority_fields,
    generate_columns_config,
    generate_config,
    generate_priorities_config,
    generate_yaml,
    parse_project_url,
)


class TestParseProjectUrl:
    """Tests for parse_project_url function."""

    def test_user_project_url(self):
        """Parses user project URL correctly."""
        url = "https://github.com/users/testuser/projects/1"
        result = parse_project_url(url)

        assert result == ("user", "testuser", 1)

    def test_user_project_url_with_view(self):
        """Parses user project URL with view number."""
        url = "https://github.com/users/testuser/projects/1/views/2"
        result = parse_project_url(url)

        assert result == ("user", "testuser", 1)

    def test_org_project_url(self):
        """Parses org project URL correctly."""
        url = "https://github.com/orgs/myorg/projects/42"
        result = parse_project_url(url)

        assert result == ("org", "myorg", 42)

    def test_org_project_url_with_view(self):
        """Parses org project URL with view number."""
        url = "https://github.com/orgs/myorg/projects/42/views/1"
        result = parse_project_url(url)

        assert result == ("org", "myorg", 42)

    def test_http_url(self):
        """Parses HTTP URL (upgrades to HTTPS in pattern)."""
        url = "http://github.com/users/testuser/projects/5"
        result = parse_project_url(url)

        assert result == ("user", "testuser", 5)

    def test_invalid_url_no_projects(self):
        """Returns None for URL without /projects/."""
        url = "https://github.com/testuser/testrepo"
        result = parse_project_url(url)

        assert result is None

    def test_invalid_url_wrong_format(self):
        """Returns None for wrong URL format."""
        url = "https://github.com/testuser/projects/1"
        result = parse_project_url(url)

        assert result is None

    def test_invalid_url_not_github(self):
        """Returns None for non-GitHub URL."""
        url = "https://gitlab.com/users/testuser/projects/1"
        result = parse_project_url(url)

        assert result is None

    def test_invalid_url_empty(self):
        """Returns None for empty string."""
        result = parse_project_url("")

        assert result is None


class TestFindPriorityFields:
    """Tests for find_priority_fields function."""

    def test_finds_priority_field(self):
        """Finds field named Priority."""
        metadata = ProjectMetadata(
            id="PVT_123",
            title="Test",
            status_options=[],
            single_select_fields={"Priority": [], "Labels": []},
            detected_repos=[],
        )

        result = find_priority_fields(metadata)

        assert result == ["Priority"]

    def test_finds_severity_field(self):
        """Finds field named Severity."""
        metadata = ProjectMetadata(
            id="PVT_123",
            title="Test",
            status_options=[],
            single_select_fields={"Severity": [], "Other": []},
            detected_repos=[],
        )

        result = find_priority_fields(metadata)

        assert result == ["Severity"]

    def test_finds_multiple_priority_fields(self):
        """Finds multiple priority-like fields."""
        metadata = ProjectMetadata(
            id="PVT_123",
            title="Test",
            status_options=[],
            single_select_fields={"Priority": [], "Urgency": [], "Type": []},
            detected_repos=[],
        )

        result = find_priority_fields(metadata)

        assert "Priority" in result
        assert "Urgency" in result
        assert "Type" not in result

    def test_case_insensitive_match(self):
        """Matches priority keywords case-insensitively."""
        metadata = ProjectMetadata(
            id="PVT_123",
            title="Test",
            status_options=[],
            single_select_fields={"PRIORITY": [], "importance_level": []},
            detected_repos=[],
        )

        result = find_priority_fields(metadata)

        assert "PRIORITY" in result
        assert "importance_level" in result

    def test_no_priority_fields(self):
        """Returns empty list when no priority fields found."""
        metadata = ProjectMetadata(
            id="PVT_123",
            title="Test",
            status_options=[],
            single_select_fields={"Status": [], "Labels": []},
            detected_repos=[],
        )

        result = find_priority_fields(metadata)

        assert result == []


class TestGenerateColumnsConfig:
    """Tests for generate_columns_config function."""

    def test_generates_columns_from_status(self):
        """Generates column config from Status options."""
        status_options = [
            {"id": "opt1", "name": "To Do"},
            {"id": "opt2", "name": "In Progress"},
            {"id": "opt3", "name": "Done"},
        ]

        result = generate_columns_config(status_options)

        assert len(result) == 3
        assert result[0] == {"id": "to_do", "title": "To Do"}
        assert result[1] == {"id": "in_progress", "title": "In Progress"}
        assert result[2] == {"id": "done", "title": "Done"}

    def test_handles_special_characters(self):
        """Handles Status options with special characters."""
        status_options = [
            {"id": "opt1", "name": "Ready ✓"},
            {"id": "opt2", "name": "In Review"},
        ]

        result = generate_columns_config(status_options)

        assert result[0] == {"id": "ready", "title": "Ready ✓"}
        assert result[1] == {"id": "in_review", "title": "In Review"}


class TestGeneratePrioritiesConfig:
    """Tests for generate_priorities_config function."""

    def test_default_priorities_when_no_field(self):
        """Returns default priorities when no field options provided."""
        result = generate_priorities_config(None)

        assert len(result) == 4
        assert result[0]["id"] == "low"
        assert result[1]["id"] == "medium"
        assert result[2]["id"] == "high"
        assert result[3]["id"] == "critical"

    def test_generates_from_field_options(self):
        """Generates priorities from field options by position."""
        field_options = [
            {"id": "opt1", "name": "Low"},
            {"id": "opt2", "name": "Medium"},
            {"id": "opt3", "name": "High"},
        ]

        result = generate_priorities_config(field_options)

        assert len(result) == 3
        assert result[0] == {"id": "low", "label": "Low", "color": "green"}
        assert result[1] == {"id": "medium", "label": "Medium", "color": "yellow"}
        assert result[2] == {"id": "high", "label": "High", "color": "orange1"}

    def test_handles_more_than_five_options(self):
        """Uses last color for options beyond 5."""
        field_options = [{"id": f"opt{i}", "name": f"Priority {i}"} for i in range(7)]

        result = generate_priorities_config(field_options)

        assert len(result) == 7
        # Last two should both use the last color
        assert result[5]["color"] == "magenta"
        assert result[6]["color"] == "magenta"


class TestGenerateConfig:
    """Tests for generate_config function."""

    def test_generates_full_config(self):
        """Generates complete config dictionary."""
        columns = [{"id": "to_do", "title": "To Do"}]
        priorities = [{"id": "medium", "label": "Medium", "color": "yellow"}]

        result = generate_config(
            project_url="https://github.com/users/test/projects/1",
            default_repo="test/repo",
            columns=columns,
            priorities=priorities,
            default_status="To Do",
            priority_field="Priority",
        )

        assert result["provider"] == "github"
        assert result["github"]["project_url"] == "https://github.com/users/test/projects/1"
        assert result["github"]["default_repo"] == "test/repo"
        assert result["github"]["default_status"] == "To Do"
        assert result["github"]["priority_field"] == "Priority"
        assert result["board"]["columns"] == columns
        assert result["board"]["priorities"] == priorities
        assert len(result["board"]["types"]) == 3

    def test_omits_optional_fields_when_none(self):
        """Omits default_status and priority_field when not provided."""
        result = generate_config(
            project_url="https://github.com/users/test/projects/1",
            default_repo="test/repo",
            columns=[],
            priorities=[],
        )

        assert "default_status" not in result["github"]
        assert "priority_field" not in result["github"]


class TestGenerateYaml:
    """Tests for generate_yaml function."""

    def test_generates_valid_yaml(self):
        """Generates valid YAML with header."""
        config = {
            "provider": "github",
            "github": {"project_url": "https://example.com"},
        }

        result = generate_yaml(config)

        assert "# sltasks GitHub Projects Configuration" in result
        assert "provider: github" in result
        assert "project_url: https://example.com" in result

    def test_yaml_is_parseable(self):
        """Generated YAML can be parsed back."""
        import yaml

        config = {
            "provider": "github",
            "github": {
                "project_url": "https://github.com/users/test/projects/1",
                "default_repo": "test/repo",
            },
            "board": {
                "columns": [{"id": "todo", "title": "To Do"}],
            },
        }

        yaml_str = generate_yaml(config)
        parsed = yaml.safe_load(yaml_str)

        assert parsed["provider"] == "github"
        assert parsed["github"]["project_url"] == "https://github.com/users/test/projects/1"
