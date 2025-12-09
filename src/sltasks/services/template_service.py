"""Template service for loading task templates."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter

if TYPE_CHECKING:
    from .config_service import ConfigService

logger = logging.getLogger(__name__)


class TemplateService:
    """Service for loading and applying task templates."""

    TEMPLATES_DIR = "templates"

    def __init__(self, config_service: ConfigService) -> None:
        """Initialize the template service.

        Args:
            config_service: ConfigService for accessing config and task_root
        """
        self._config_service = config_service

    @property
    def templates_path(self) -> Path:
        """Get path to templates directory within task_root."""
        return self._config_service.task_root / self.TEMPLATES_DIR

    def get_template(self, type_id: str) -> tuple[dict, str] | None:
        """
        Load template for a type.

        Args:
            type_id: The type ID to load template for

        Returns:
            (frontmatter_dict, body_content) or None if not found
        """
        config = self._config_service.get_board_config()
        type_config = config.get_type(type_id)

        if type_config is None:
            logger.debug(f"No type config found for: {type_id}")
            return None

        template_file = self.templates_path / type_config.template_filename

        if not template_file.exists():
            logger.debug(f"Template not found: {template_file}")
            return None

        try:
            post = frontmatter.load(template_file)
            return dict(post.metadata), post.content
        except Exception as e:
            logger.warning(f"Failed to load template {template_file}: {e}")
            return None

    def apply_template(
        self,
        type_id: str,
        base_frontmatter: dict,
    ) -> tuple[dict, str]:
        """
        Apply template to task creation.

        Template frontmatter fields are used as defaults (won't override
        values already in base_frontmatter).

        Args:
            type_id: Type to get template for
            base_frontmatter: Frontmatter dict (title, state, created, updated)

        Returns:
            (merged_frontmatter, body_content)
        """
        template = self.get_template(type_id)

        if template is None:
            return base_frontmatter, ""

        template_fm, template_body = template

        # Merge: template values are defaults, base values override
        merged = dict(template_fm)
        merged.update(base_frontmatter)

        # Always set type to the canonical ID
        merged["type"] = type_id

        return merged, template_body
