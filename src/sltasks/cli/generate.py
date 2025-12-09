"""Generate command for creating default config."""

import importlib.resources
import logging
import sys
from pathlib import Path

import yaml

from ..models.sltasks_config import SltasksConfig
from .output import success, info, error

logger = logging.getLogger(__name__)

CONFIG_FILE = "sltasks.yml"
TEMPLATES_DIR = "templates"

# Header comments for generated file
CONFIG_HEADER = """\
# sltasks Board Configuration
#
# task_root: Relative path to directory containing task files
#
# Column constraints:
#   - Minimum 2 columns, maximum 6 columns
#   - Column IDs must be lowercase with underscores only
#   - 'archived' is reserved and cannot be used as a column ID
#
# Status Aliases:
#   - Optional list of alternative status values mapping to column ID
#   - Useful for mapping existing file states or synonyms
#
# Task Types:
#   - Define types with optional templates in {task_root}/templates/
#   - Each type has: id, template (optional), color, type_alias (optional)
#   - color: Named color (blue, red, etc.) or hex (#ff0000)
#   - Templates provide default content and frontmatter for new tasks
#
# Example custom columns:
#   columns:
#     - id: backlog
#       title: "Backlog"
#       status_alias:
#         - pending
#     - id: in_progress
#       title: "In Progress"
#     - id: done
#       title: "Done"
#       status_alias:
#         - completed
#         - finished

"""


def prompt_task_root() -> str:
    """Prompt user for task directory name."""
    # Non-interactive: use default
    if not sys.stdin.isatty():
        return ".tasks"

    print("Enter task directory name (default: .tasks): ", end="", flush=True)
    user_input = input().strip()
    return user_input if user_input else ".tasks"


def _is_valid_task_root(name: str, project_root: Path) -> bool:
    """Validate task root name."""
    path = Path(name)

    # Must be relative
    if path.is_absolute():
        return False

    # Must resolve to within project_root
    try:
        resolved = (project_root / path).resolve()
        resolved.relative_to(project_root.resolve())
    except ValueError:
        return False

    return True


def generate_config_yaml(task_root: str = ".tasks") -> str:
    """Generate YAML config from default SltasksConfig model.

    Uses SltasksConfig.default() as the single source of truth,
    ensuring generated config always matches internal defaults.

    Args:
        task_root: The task directory path to include in config
    """
    config = SltasksConfig.default()
    # Use model_dump() to get dict, then serialize to YAML
    config_dict = config.model_dump()
    config_dict["task_root"] = task_root  # Use provided task_root

    # Clean up empty status_alias fields in columns
    if "board" in config_dict and "columns" in config_dict["board"]:
        for col in config_dict["board"]["columns"]:
            if "status_alias" in col and not col["status_alias"]:
                del col["status_alias"]

    # Clean up types: remove None templates and empty type_alias
    if "board" in config_dict and "types" in config_dict["board"]:
        for type_cfg in config_dict["board"]["types"]:
            if "template" in type_cfg and type_cfg["template"] is None:
                del type_cfg["template"]
            if "type_alias" in type_cfg and not type_cfg["type_alias"]:
                del type_cfg["type_alias"]

    yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    return CONFIG_HEADER + yaml_content


def _copy_bundled_templates(task_root: Path) -> bool:
    """Copy bundled default templates to task_root/templates/.

    Args:
        task_root: Path to the task directory

    Returns:
        True if templates were created, False if already exist
    """
    templates_dir = task_root / TEMPLATES_DIR

    # Check if templates already exist
    if templates_dir.exists() and any(templates_dir.glob("*.md")):
        return False

    templates_dir.mkdir(exist_ok=True)

    try:
        # Use importlib.resources to access bundled templates
        package_templates = importlib.resources.files("sltasks.data.templates")
        templates_copied = 0

        for resource in package_templates.iterdir():
            if resource.name.endswith(".md"):
                content = resource.read_text()
                (templates_dir / resource.name).write_text(content)
                templates_copied += 1

        return templates_copied > 0
    except Exception as e:
        logger.warning(f"Failed to copy templates: {e}")
        return False


def run_generate(project_root: Path) -> int:
    """
    Generate default configuration.

    Args:
        project_root: Path to project root where sltasks.yml will be created

    Returns:
        Exit code (0 = success, 1 = nothing to do)
    """
    config_created = False
    dir_created = False
    templates_created = False

    config_path = project_root / CONFIG_FILE

    # Check if config already exists
    if config_path.exists():
        info(f"Config exists: {config_path}")
        # Load existing config to get task_root
        with open(config_path) as f:
            data = yaml.safe_load(f) or {}
        task_root_name = data.get("task_root", ".tasks")
    else:
        # Prompt for task directory name
        task_root_name = prompt_task_root()

        # Validate the name
        if not _is_valid_task_root(task_root_name, project_root):
            error(f"Invalid task directory: {task_root_name}")
            return 1

        # Ensure project_root exists
        if not project_root.exists():
            project_root.mkdir(parents=True)

        # Write config file
        config_path.write_text(generate_config_yaml(task_root_name))
        success(f"Generated config: {config_path}")
        config_created = True

    # Create task directory if it doesn't exist
    task_dir = project_root / task_root_name
    if not task_dir.exists():
        task_dir.mkdir(parents=True)
        success(f"Created directory: {task_dir}/")
        dir_created = True
    else:
        info(f"Directory exists: {task_dir}/")

    # Copy bundled templates if not already present
    templates_dir = task_dir / TEMPLATES_DIR
    if templates_dir.exists() and any(templates_dir.glob("*.md")):
        info(f"Templates exist: {templates_dir}/")
    else:
        if _copy_bundled_templates(task_dir):
            success(f"Created templates: {templates_dir}/")
            templates_created = True

    # Summary
    if not config_created and not dir_created and not templates_created:
        print("Nothing to generate.")
        return 1

    return 0
