# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

sltasks is a terminal-based Kanban TUI for markdown task management. Tasks are stored as individual markdown files with YAML front matter in a configurable tasks directory (default: `.tasks/`).

### Core Principles

- **Markdown files are the single source of truth** - Users or LLMs can create/edit task files directly; the TUI adapts automatically
- **Terminal-first** - Fast, keyboard-driven interface
- **Git-friendly** - All data is plain text, version controllable
- **Minimal configuration** - Works out of the box with sensible defaults

## Commands

```bash
# Run the TUI application
uv run sltasks

# Run with custom project root
uv run sltasks --task-root /path/to/project

# Generate default config file
uv run sltasks --generate

# Run tests
uv run pytest

# Run single test
uv run pytest tests/test_models.py::test_function_name

# Build documentation
uv run mkdocs build -d site-build

# Serve documentation locally
uv run mkdocs serve

# Linting
./scripts/lint.sh                  # Run all lint checks
uv run ruff check .                # Lint check
uv run ruff format --check .       # Format check
uv run pyrefly check               # Type check
uv run ruff check . --fix          # Auto-fix lint issues
uv run ruff format .               # Auto-format code
uv run pre-commit run --all-files  # Run pre-commit hooks
```

## Architecture

### Layer Structure

```
CLI (__main__.py) → App (app.py) → Services → Repository → Filesystem
                         ↓
                   UI (Textual screens/widgets)
```

- **CLI Layer** (`__main__.py`): Parses args, creates Settings, launches app
- **App Layer** (`app.py`): Textual App subclass, handles keybindings, coordinates services
- **Service Layer** (`services/`): Business logic
  - `ConfigService`: Loads `sltasks.yml`, provides board configuration
  - `TaskService`: CRUD operations on tasks, opens external editor
  - `BoardService`: Board state management, task movement between columns
  - `FilterService`: Parses filter expressions, applies filters to task lists
  - `TemplateService`: Loads task templates, merges template frontmatter with new tasks
- **Repository Layer** (`repositories/`): Task storage backends
  - `RepositoryProtocol`: Interface for storage backends (supports filesystem, future GitHub/Jira)
  - `FilesystemRepository`: File I/O, manages task files and `tasks.yaml` ordering
- **UI Layer** (`ui/`): Textual screens and widgets

### Data Flow

1. Tasks stored as `.md` files with YAML front matter (title, state, priority, type, tags, created, updated)
2. Task ordering maintained in `tasks.yaml` (auto-generated, keyed by column)
3. Board configuration in `sltasks.yml` at project root defines columns (2-6 custom columns) and types
4. Templates in `{task_root}/templates/` provide default content for new tasks
5. Files are source of truth for task state; YAML provides ordering within columns

### Key Models

- `Task`: Pydantic model with frontmatter fields (title, state, priority, type, tags), body content, and `provider_data`
- `Board`/`BoardOrder`: Board state with tasks grouped by column
- `SltasksConfig`/`BoardConfig`/`ColumnConfig`/`TypeConfig`/`PriorityConfig`: Configuration hierarchy from `sltasks.yml`
- `RepositoryProtocol`: Interface for task storage backends
- `ProviderData`: Discriminated union of provider-specific data models (`FileProviderData`, `GitHubProviderData`, `GitHubPRProviderData`, `JiraProviderData`)

### Task File Format

```markdown
---
title: Task title
state: todo          # Column ID (e.g., todo, in_progress, done, or custom)
priority: medium     # low, medium, high, critical
type: feature        # Task type (feature, bug, task, or custom)
tags:
- tag1
created: '2025-01-01T12:00:00+00:00'
updated: '2025-01-01T12:00:00+00:00'
---

Markdown body content here.
```

### Task Types

Types are configured in `sltasks.yml` under `board.types`:
- Each type has `id`, optional `template`, `color`, and optional `type_alias`
- Templates in `{task_root}/templates/` provide default body content and frontmatter
- Default types: feature (blue), bug (red), task (white)

### Custom Columns

Columns are configured in `sltasks.yml`:
- Column IDs must be lowercase alphanumeric with underscores
- 2-6 columns allowed
- `archived` is reserved and cannot be used as a column ID
- Default: todo, in_progress, done

## Key Keybindings (for context)

- `h/j/k/l` or arrows: Navigation
- `H/L` or Shift+arrows: Move task between columns
- `K/J` or Shift+up/down: Reorder task within column
- `n`: New task, `e`: Edit, `a`: Archive, `d`: Delete
- `/`: Filter mode, `?`: Help, `space`: Toggle state (cycle columns)

## Key Architectural Insights

### Data Flow Principles

- **File state is truth**: The task file's `state` field always wins over YAML column placement
- **Filename is the stable identifier**: Titles can change; filename is the key
- **YAML provides ordering only**: `tasks.yaml` tracks position within columns, not state

### Service Layer Design

- **Services own business logic**: Repository handles only I/O operations
- **Archived tasks are special**: Excluded from normal state flow, always available but never shown as a column
- **FilterService is stateless**: No repository dependency needed
- **ConfigService caches config**: Loaded once, provides board configuration to all other services

### Textual Patterns

- Use `App.suspend()` for external editor integration
- Access services via `self.app.service_name` pattern
- Styles in `ui/styles.tcss` using built-in CSS variables (`$primary`, `$surface`, etc.)
- Use `call_after_refresh()` for deferred focus after DOM rebuilds

### Testing Approach

- Integration tests at service layer catch regressions without UI brittleness
- Use real filesystem via `tmp_path` fixture (no mocking)
- Test files: repository, services, models, filters, slugs, config

### Design Decisions

- **Repository Protocol**: `RepositoryProtocol` defines the interface for task storage backends (filesystem, planned GitHub/Jira)
- **Provider Data Pattern**: `Task.provider_data` uses a discriminated union for type-safe provider-specific metadata
- **String-based states**: `Task.state` is a string, not an enum, to support custom columns
- **String-based priorities**: `Task.priority` is a string with configurable `PriorityConfig` for colors/aliases
- **Canonical aliases**: `TypeConfig` and `PriorityConfig` support `canonical_alias` for external system write-back
- **No backwards compatibility shims**: Early project, remove deprecated code rather than maintain it

## Code Style

- Python 3.13+ with type hints
- Ruff for linting and formatting (100 char line length)
- Pyrefly for type checking
- Pre-commit hooks enforce style on commit
