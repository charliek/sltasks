---
state: done
priority: medium
created: '2025-11-29T22:30:00+00:00'
updated: '2025-11-29T19:30:10.643793+00:00'
---

# Phase 7: Generate Config Command

## Overview

Add a `--generate` CLI command that creates the task directory and default `sltasks.yml` configuration file. This allows users to quickly bootstrap a project with customizable columns instead of starting from scratch.

## Goals

1. Add `--generate` flag to CLI that creates directory and config file
2. Honor existing `--task-root` flag for custom locations
3. Provide colorful, informative output showing each step
4. Skip gracefully if directory/file already exists
5. Set foundation for future init/setup commands

## User Experience

```bash
# Generate in default .tasks/ directory
$ kosmos --generate
✓ Created directory: .tasks/
✓ Generated config: .tasks/sltasks.yml

# Generate in custom location
$ kosmos --task-root my-project/.tasks --generate
✓ Created directory: my-project/.tasks/
✓ Generated config: my-project/.tasks/sltasks.yml

# Already exists - graceful exit
$ kosmos --generate
• Directory exists: .tasks/
• Config exists: .tasks/sltasks.yml
Nothing to generate.
```

## Task Checklist

- [x] Update `src/kosmos/__main__.py`:
  - [x] Add `--generate` argument to argparse
  - [x] Handle --generate command (exits after completion)
- [x] Create `src/kosmos/cli/` module:
  - [x] `__init__.py` - exports
  - [x] `generate.py` - generate command logic
  - [x] `output.py` - colorful terminal output helpers
- [x] Implement generate logic:
  - [x] Check if directory exists, create if not
  - [x] Check if sltasks.yml exists, create if not
  - [x] Generate valid YAML from SltasksConfig.default()
  - [x] Use ANSI colors for output (with TTY detection)
- [x] Add tests:
  - [x] Test directory creation
  - [x] Test file generation
  - [x] Test skip when exists
  - [x] Test custom --task-root path
  - [x] Test generated config matches model default

## Detailed Specifications

### CLI Argument

```python
parser.add_argument(
    "--generate",
    action="store_true",
    help="Generate default sltasks.yml config in task directory",
)
```

### Output Helper Module

```python
# src/kosmos/cli/output.py
"""Colorful CLI output helpers."""

# ANSI color codes
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RESET = "\033[0m"
CHECK = "✓"
BULLET = "•"


def success(message: str) -> None:
    """Print success message with green checkmark."""
    print(f"{GREEN}{CHECK}{RESET} {message}")


def info(message: str) -> None:
    """Print info message with bullet."""
    print(f"{YELLOW}{BULLET}{RESET} {message}")


def header(message: str) -> None:
    """Print header message in blue."""
    print(f"{BLUE}{message}{RESET}")
```

### Generate Command Implementation

**Key Design Decision**: Use `SltasksConfig.default()` as the single source of truth and serialize it to YAML. This ensures the generated file always matches the internal default representation - no duplicate hardcoded configs to maintain.

```python
# src/kosmos/cli/generate.py
"""Generate command for creating default config."""

from pathlib import Path

import yaml

from ..models.sltasks_config import SltasksConfig
from .output import success, info


CONFIG_FILE = "sltasks.yml"

# Header comments for generated file
CONFIG_HEADER = """\
# Kosmos Board Configuration
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
```

### Updated Main Entry Point

```python
# src/kosmos/__main__.py
def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Build settings from CLI args
    settings_kwargs: dict = {}
    if args.task_root:
        settings_kwargs["task_root"] = args.task_root

    settings = Settings(**settings_kwargs)

    # Handle --generate command
    if args.generate:
        from .cli.generate import run_generate
        exit_code = run_generate(settings.task_root)
        raise SystemExit(exit_code)

    # Normal app startup
    from .app import run
    run(settings)
```

### Generated Config File

The generated `sltasks.yml` includes helpful comments followed by YAML serialized from `SltasksConfig.default()`:

```yaml
# Kosmos Board Configuration
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

version: 1
board:
  columns:
  - id: todo
    title: To Do
  - id: in_progress
    title: In Progress
  - id: done
    title: Done
```

## Test Cases

```python
# tests/test_generate.py

import pytest
from pathlib import Path
from kosmos.cli.generate import run_generate, CONFIG_FILE


class TestGenerate:
    """Tests for generate command."""

    def test_creates_directory_and_file(self, tmp_path: Path):
        """Generate creates both directory and config."""
        task_root = tmp_path / ".tasks"

        exit_code = run_generate(task_root)

        assert exit_code == 0
        assert task_root.exists()
        assert (task_root / CONFIG_FILE).exists()

    def test_creates_file_in_existing_directory(self, tmp_path: Path):
        """Generate creates file when directory exists."""
        task_root = tmp_path / ".tasks"
        task_root.mkdir()

        exit_code = run_generate(task_root)

        assert exit_code == 0
        assert (task_root / CONFIG_FILE).exists()

    def test_skips_when_both_exist(self, tmp_path: Path):
        """Generate returns 1 when nothing to do."""
        task_root = tmp_path / ".tasks"
        task_root.mkdir()
        (task_root / CONFIG_FILE).write_text("existing")

        exit_code = run_generate(task_root)

        assert exit_code == 1

    def test_nested_directory_creation(self, tmp_path: Path):
        """Generate creates nested directories."""
        task_root = tmp_path / "deep" / "nested" / ".tasks"

        exit_code = run_generate(task_root)

        assert exit_code == 0
        assert task_root.exists()

    def test_generated_config_is_valid(self, tmp_path: Path):
        """Generated config can be loaded by ConfigService."""
        from kosmos.services import ConfigService

        task_root = tmp_path / ".tasks"
        run_generate(task_root)

        service = ConfigService(task_root)
        config = service.get_config()

        assert len(config.board.columns) == 3
        assert not service.has_config_error

    def test_custom_task_root_path(self, tmp_path: Path):
        """Generate honors custom --task-root path."""
        custom_root = tmp_path / "my-project" / "tasks"

        exit_code = run_generate(custom_root)

        assert exit_code == 0
        assert custom_root.exists()
        assert (custom_root / CONFIG_FILE).exists()

    def test_generated_matches_model_default(self, tmp_path: Path):
        """Generated config matches SltasksConfig.default()."""
        from kosmos.services import ConfigService
        from kosmos.models import SltasksConfig

        task_root = tmp_path / ".tasks"
        run_generate(task_root)

        service = ConfigService(task_root)
        loaded_config = service.get_config()
        default_config = SltasksConfig.default()

        # Column IDs should match
        assert loaded_config.board.column_ids == default_config.board.column_ids
        # Titles should match
        for i, col in enumerate(loaded_config.board.columns):
            assert col.title == default_config.board.columns[i].title
```

## Future Considerations

This command lays groundwork for future enhancements:

- `--generate --force` to overwrite existing config
- `--generate --template=<name>` for different column presets (scrum, kanban, etc.)
- Interactive mode asking user for column configuration
- `kosmos init` as alias for `--generate`

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|

## Completion Notes

**Phase 7 status: Complete**

Completed on 2025-11-29.

Files created:
- `src/kosmos/cli/__init__.py` - CLI module exports
- `src/kosmos/cli/output.py` - Colorful output helpers (success, info, header)
- `src/kosmos/cli/generate.py` - Generate command implementation
- `tests/test_generate.py` - 13 tests for generate functionality

Files modified:
- `src/kosmos/__main__.py` - Added `--generate` argument

Key implementation details:
- Uses `SltasksConfig.default().model_dump()` as single source of truth
- YAML serialized with helpful header comments
- TTY detection for color support
- Exit code 0 when something created, 1 when nothing to do
- `--task-root` honored for custom locations

Verification:
- All 173 tests passing
- Manual testing confirms:
  - `kosmos --generate` creates .tasks/sltasks.yml
  - `kosmos --task-root custom/.tasks --generate` creates in custom location
  - Running again shows "Nothing to generate" with exit code 1

## Key Notes

- Exit code 0 = something was created
- Exit code 1 = nothing to generate (already exists)
- Colors use ANSI codes for broad terminal compatibility
- Config includes comments to guide users
- `--generate` is mutually exclusive with running the TUI
- **Single source of truth**: Generated config uses `SltasksConfig.default().model_dump()` - no hardcoded duplicate config
- `--task-root` is honored - generates in custom location when specified