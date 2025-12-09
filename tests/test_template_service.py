"""Tests for TemplateService."""

import pytest
from pathlib import Path

from sltasks.services import ConfigService, TemplateService


@pytest.fixture
def project_with_templates(tmp_path: Path) -> Path:
    """Create project with templates directory."""
    project = tmp_path / "project"
    project.mkdir()

    # Create config
    config = project / "sltasks.yml"
    config.write_text(
        """
version: 1
task_root: .tasks
board:
  columns:
    - id: todo
      title: To Do
    - id: done
      title: Done
  types:
    - id: feature
      color: blue
    - id: bug
      template: bug-template.md
      color: red
    - id: task
      color: white
"""
    )

    # Create task directory and templates
    task_dir = project / ".tasks"
    task_dir.mkdir()
    templates = task_dir / "templates"
    templates.mkdir()

    (templates / "feature.md").write_text(
        """---
priority: medium
tags:
  - feature
---

## Description

[Describe feature]
"""
    )

    (templates / "bug-template.md").write_text(
        """---
priority: high
tags:
  - bug
---

## Bug Report

[Details]
"""
    )

    return project


@pytest.fixture
def config_service(project_with_templates: Path) -> ConfigService:
    """Create ConfigService for the test project."""
    return ConfigService(project_with_templates)


@pytest.fixture
def template_service(config_service: ConfigService) -> TemplateService:
    """Create TemplateService for the test project."""
    return TemplateService(config_service)


class TestTemplateServiceGetTemplate:
    """Tests for TemplateService.get_template()."""

    def test_get_template_found(self, template_service: TemplateService):
        """get_template returns template content."""
        result = template_service.get_template("feature")

        assert result is not None
        fm, body = result
        assert fm["priority"] == "medium"
        assert "feature" in fm["tags"]
        assert "## Description" in body

    def test_get_template_custom_filename(self, template_service: TemplateService):
        """get_template uses custom template filename."""
        result = template_service.get_template("bug")

        assert result is not None
        fm, body = result
        assert fm["priority"] == "high"
        assert "## Bug Report" in body

    def test_get_template_missing_file(self, template_service: TemplateService):
        """get_template returns None for missing template file."""
        result = template_service.get_template("task")  # No task.md template
        assert result is None

    def test_get_template_unknown_type(self, template_service: TemplateService):
        """get_template returns None for unknown type."""
        result = template_service.get_template("nonexistent")
        assert result is None


class TestTemplateServiceApplyTemplate:
    """Tests for TemplateService.apply_template()."""

    def test_apply_template_merges_frontmatter(self, template_service: TemplateService):
        """apply_template merges base and template frontmatter."""
        base_fm = {
            "title": "My Task",
            "state": "todo",
            "created": "2025-01-01T00:00:00",
            "updated": "2025-01-01T00:00:00",
        }

        merged, body = template_service.apply_template("feature", base_fm)

        # Base values preserved
        assert merged["title"] == "My Task"
        assert merged["state"] == "todo"
        # Template defaults applied
        assert merged["priority"] == "medium"
        assert "feature" in merged["tags"]
        # Type set
        assert merged["type"] == "feature"
        # Body from template
        assert "## Description" in body

    def test_apply_template_base_overrides_template(
        self, template_service: TemplateService
    ):
        """Base frontmatter values override template values."""
        base_fm = {
            "title": "My Task",
            "state": "todo",
            "priority": "critical",  # Override template's medium
            "tags": ["custom"],  # Override template's tags
        }

        merged, _ = template_service.apply_template("feature", base_fm)

        # Base values preserved (overrides template)
        assert merged["priority"] == "critical"
        assert merged["tags"] == ["custom"]

    def test_apply_template_missing_template(self, template_service: TemplateService):
        """apply_template returns base frontmatter when template missing."""
        base_fm = {
            "title": "My Task",
            "state": "todo",
        }

        merged, body = template_service.apply_template("task", base_fm)

        # Base values preserved unchanged (type is set by TaskService, not here)
        assert merged == base_fm
        # Empty body when no template
        assert body == ""

    def test_apply_template_unknown_type(self, template_service: TemplateService):
        """apply_template returns base frontmatter for unknown type."""
        base_fm = {
            "title": "My Task",
            "state": "todo",
        }

        merged, body = template_service.apply_template("unknown", base_fm)

        # Base values preserved
        assert merged == base_fm
        # No body
        assert body == ""


class TestTemplatesPath:
    """Tests for templates path property."""

    def test_templates_path(self, template_service: TemplateService, config_service: ConfigService):
        """templates_path returns correct path."""
        expected = config_service.task_root / "templates"
        assert template_service.templates_path == expected
