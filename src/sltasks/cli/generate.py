"""Generate command for creating default config."""

from pathlib import Path

import yaml

from ..models.sltasks_config import SltasksConfig
from .output import success, info


CONFIG_FILE = "sltasks.yml"

# Header comments for generated file
CONFIG_HEADER = """\
# sltasks Board Configuration
# Customize your kanban columns below (2-6 columns supported)
#
# Column constraints:
#   - Minimum 2 columns, maximum 6 columns
#   - Column IDs must be lowercase with underscores only
#   - 'archived' is reserved and cannot be used as a column ID
#
# Example custom columns:
#   columns:
#     - id: backlog
#       title: "Backlog"
#     - id: in_progress
#       title: "In Progress"
#     - id: review
#       title: "Code Review"
#     - id: done
#       title: "Done"

"""


def generate_config_yaml() -> str:
    """Generate YAML config from default SltasksConfig model.

    Uses SltasksConfig.default() as the single source of truth,
    ensuring generated config always matches internal defaults.
    """
    config = SltasksConfig.default()
    # Use model_dump() to get dict, then serialize to YAML
    config_dict = config.model_dump()
    yaml_content = yaml.dump(config_dict, default_flow_style=False, sort_keys=False)
    return CONFIG_HEADER + yaml_content


def run_generate(task_root: Path) -> int:
    """
    Generate default configuration.

    Args:
        task_root: Path to task directory (honors --task-root)

    Returns:
        Exit code (0 = success, 1 = nothing to do)
    """
    dir_created = False
    file_created = False

    # Check/create directory
    if not task_root.exists():
        task_root.mkdir(parents=True)
        success(f"Created directory: {task_root}/")
        dir_created = True
    else:
        info(f"Directory exists: {task_root}/")

    # Check/create config file
    config_path = task_root / CONFIG_FILE
    if not config_path.exists():
        config_path.write_text(generate_config_yaml())
        success(f"Generated config: {config_path}")
        file_created = True
    else:
        info(f"Config exists: {config_path}")

    # Summary
    if not dir_created and not file_created:
        print("Nothing to generate.")
        return 1

    return 0
