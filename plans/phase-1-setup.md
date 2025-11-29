# Phase 1: Project Setup & Core Infrastructure

## Overview

This phase establishes the project foundation: Python version, dependencies, package structure, and the basic CLI entry point. After this phase, we should be able to run `uv run kosmos` and see a placeholder message.

## Goals

1. Configure Python 3.13 as the project version
2. Add all required dependencies
3. Create the `src/kosmos/` package structure
4. Set up a working CLI entry point
5. Verify the setup works with `uv run kosmos`

## Task Checklist

- [x] Update `.python-version` to `3.13`
- [x] Update `pyproject.toml`:
  - [x] Set `requires-python = ">=3.13"`
  - [x] Add runtime dependencies (textual, pydantic-settings, python-frontmatter)
  - [x] Add dev dependencies (pytest)
  - [x] Configure package location (`packages = [{include = "kosmos", from = "src"}]`)
  - [x] Add CLI entry point (`kosmos = "kosmos.__main__:main"`)
- [x] Remove old `main.py` file
- [x] Create directory structure:
  - [x] `src/kosmos/__init__.py`
  - [x] `src/kosmos/__main__.py`
  - [x] `src/kosmos/config/__init__.py`
  - [x] `src/kosmos/models/__init__.py`
  - [x] `src/kosmos/repositories/__init__.py`
  - [x] `src/kosmos/services/__init__.py`
  - [x] `src/kosmos/ui/__init__.py`
  - [x] `src/kosmos/ui/screens/__init__.py`
  - [x] `src/kosmos/ui/widgets/__init__.py`
  - [x] `src/kosmos/utils/__init__.py`
  - [x] `tests/__init__.py`
- [x] Run `uv sync` to install dependencies
- [x] Verify `uv run kosmos` works

## Detailed Specifications

### pyproject.toml Structure

```toml
[project]
name = "kosmos"
version = "0.1.0"
description = "Terminal-based Kanban TUI for markdown task management"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "textual>=0.89.0",
    "pydantic-settings>=2.6.0",
    "python-frontmatter>=1.1.0",
]

[project.scripts]
kosmos = "kosmos.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/kosmos"]

[dependency-groups]
dev = [
    "pytest>=8.0.0",
]
```

### __main__.py (Initial)

```python
"""CLI entry point for Kosmos."""


def main() -> None:
    """Main entry point."""
    print("Kosmos - Terminal Kanban TUI")
    print("Setup complete! TUI coming in Phase 5.")


if __name__ == "__main__":
    main()
```

### __init__.py

```python
"""Kosmos - Terminal-based Kanban TUI for markdown task management."""

__version__ = "0.1.0"
```

## Dependencies

| Package | Purpose | Min Version |
|---------|---------|-------------|
| textual | TUI framework | 0.89.0 |
| pydantic-settings | Configuration management | 2.6.0 |
| python-frontmatter | Markdown/YAML parsing | 1.1.0 |
| pytest | Testing (dev) | 8.0.0 |

## Verification Steps

1. Run `uv sync` - should complete without errors
2. Run `uv run kosmos` - should print placeholder message
3. Run `uv run python -c "import kosmos; print(kosmos.__version__)"` - should print "0.1.0"

## Deviations from Plan

| Date | Deviation | Reason |
|------|-----------|--------|
| 2025-11-28 | Used `[tool.hatch.build.targets.wheel]` instead of `packages = [{include = ...}]` | Hatchling uses different syntax for specifying package location |

## Completion Notes

**Phase 1 completed on 2025-11-28**

Verification results:
- `uv sync` installed 23 packages successfully
- `uv run kosmos` prints expected placeholder message
- `uv run python -c "import kosmos; print(kosmos.__version__)"` prints "0.1.0"

Installed package versions:
- textual 6.6.0
- pydantic-settings 2.12.0
- python-frontmatter 1.1.0
- pytest 9.0.1

## Key Notes

- We're using `uv` for package management (not pip/poetry)
- The `src/` layout is a Python best practice that prevents accidental imports from the local directory
- All `__init__.py` files start empty except the root one which defines `__version__`
- We're using hatchling as the build backend (uv default)
