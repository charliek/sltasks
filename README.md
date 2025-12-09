# sltasks

A terminal-based Kanban TUI for managing tasks stored as Markdown files.

## Features

- **Markdown-native**: Tasks are plain `.md` files with YAML front matter
- **Git-friendly**: All data is version-controllable text
- **Vim-style navigation**: `h/j/k/l` keys for fast keyboard-driven workflow
- **Custom columns**: Configure 2-6 columns via `sltasks.yml`
- **Filtering**: Search by text, tags, state, or priority
- **External editor**: Edit tasks in your `$EDITOR`

## Installation

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone the repository
git clone git@github.com:charliek/sltasks.git
cd sltasks

# Install dependencies
uv sync

# Run the application
uv run sltasks
```

## Development

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
```

## Quick Start

### 1. Initialize a project

```bash
# Generate default sltasks.yml config
uv run sltasks --generate
```

This creates `sltasks.yml` in the current directory and a `.tasks/` folder for your task files.

### 2. Launch the TUI

```bash
uv run sltasks
```

### 3. Create your first task

Press `n` to create a new task. Your `$EDITOR` opens with a template. Save and close to add the task to the board.

### 4. Navigate and manage tasks

| Key | Action |
|-----|--------|
| `h` / `l` | Move between columns |
| `j` / `k` | Move between tasks |
| `H` / `L` | Move task to prev/next column |
| `J` / `K` | Reorder task within column |
| `n` | New task |
| `e` | Edit task in `$EDITOR` |
| `Enter` | Preview task |
| `a` | Archive task |
| `d` | Delete task (with confirmation) |
| `space` | Cycle task through columns |
| `/` | Filter tasks |
| `?` | Show help |
| `r` | Refresh board |
| `q` | Quit |

## Task File Format

Tasks are stored as Markdown files with YAML front matter in `.tasks/`:

```markdown
---
title: Fix login timeout bug
state: todo
priority: high
type: bug
tags:
- backend
created: '2025-01-01T12:00:00+00:00'
updated: '2025-01-02T14:00:00+00:00'
---

## Description

Users are experiencing timeout errors when logging in.

## Acceptance Criteria

- [ ] Identify root cause
- [ ] Implement fix
```

All front matter fields are optional. Files without front matter use defaults.

## Configuration

Create `sltasks.yml` in your project root to customize columns and task types:

```yaml
version: 1
task_root: .tasks
board:
  columns:
  - id: todo
    title: To Do
  - id: in_progress
    title: In Progress
  - id: done
    title: Done
  types:
  - id: feature
    color: blue
  - id: bug
    color: red
    type_alias:
    - defect
  - id: task
    color: white
```

**Column constraints:**
- 2-6 columns allowed
- Column IDs must be lowercase alphanumeric with underscores
- `archived` is reserved (always available but not shown as a column)

**Task types:**
- Types categorize tasks with colored display and optional templates
- Templates in `{task_root}/templates/` provide default content for new tasks
- Run `sltasks --generate` to create default templates

## Filtering

Press `/` to enter filter mode. Examples:

```
bug                     # Free text search in title/body
tag:backend             # Tasks with "backend" tag
-tag:wontfix            # Exclude "wontfix" tag
state:in_progress       # Tasks in specific column
priority:high           # Filter by priority (low/medium/high/critical)
type:bug                # Filter by task type
type:bug type:feature   # Tasks with type "bug" OR "feature"
archived:true           # Show archived tasks
tag:bug priority:high   # Combine multiple filters (AND)
type:bug priority:high  # Bugs with high priority
```

Press `Escape` to clear the filter.

## CLI Options

```bash
sltasks [OPTIONS]

Options:
  --task-root PATH  Path to project root containing sltasks.yml
  --generate        Generate default sltasks.yml config and exit
  --version         Show version
  --help            Show help
```

## License

MIT
