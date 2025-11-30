# sltasks – Product Requirements Document

> A terminal-based task management TUI (previously known as "Kosmos")

## 1. Overview

**sltasks** is a terminal-based Kanban interface (TUI) for managing tasks stored as Markdown files with YAML front matter. This tool provides lightweight, structured task management for personal projects without the overhead of solutions like Jira or GitHub Projects.

### Core Principles

- **Markdown files are the single source of truth** – Users or LLMs can create/edit task files directly; the TUI adapts automatically
- **Terminal-first** – Fast, keyboard-driven interface
- **Git-friendly** – All data is plain text, version controllable
- **Minimal configuration** – Works out of the box with sensible defaults
- **Extensible** – Designed for future workflow automation

No LLM integration is included within the TUI itself.

---

## 2. File Structure

### 2.1 Directory Layout

```
project-root/
├── .tasks/
│   ├── tasks.yaml          # System-managed kanban metadata
│   ├── fix-login-bug.md
│   ├── add-user-auth.md
│   ├── refactor-api.md
│   └── ...
└── (rest of project)
```

- All task files live in a flat `.tasks/` directory at the repo root
- Location configurable via `--task-root <path>` CLI flag
- Task files use descriptive, filesystem-safe names (no spaces, special chars)

### 2.2 Task File Format

Each task is a standalone Markdown file with optional YAML front matter:

```yaml
---
title: "Fix login timeout bug"
state: todo
priority: high
tags: [bug, auth, backend]
created: 2025-01-01T12:00:00Z
updated: 2025-01-02T14:00:00Z
---

## Description

Users are experiencing timeout errors when logging in during peak hours.

## Acceptance Criteria

- [ ] Identify root cause
- [ ] Implement fix
- [ ] Add monitoring
```

**All fields are optional** to allow any markdown file in the directory to be loaded as a task.

### 2.3 Field Definitions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `title` | string | filename (without .md) | Display name for the task |
| `state` | enum | `todo` | `todo`, `in_progress`, `done`, `archived` |
| `priority` | enum | `medium` | `low`, `medium`, `high`, `critical` |
| `tags` | list | `[]` | Arbitrary user-defined tags |
| `created` | ISO datetime | file creation time | When task was created |
| `updated` | ISO datetime | file modification time | Last modification time |

### 2.4 Kanban Metadata File (tasks.yaml)

This file is **system-managed** and automatically maintained by the TUI. It tracks column ordering and task positions:

```yaml
# Auto-generated - do not edit manually
version: 1
columns:
  todo:
    - fix-login-bug.md
    - add-user-auth.md
  in_progress:
    - refactor-api.md
  done:
    - setup-ci.md
  archived:
    - old-feature.md
```

**Behavior:**

- The TUI reads task files as the source of truth for task content/state
- `tasks.yaml` provides custom ordering within columns
- If a task file exists but isn't in `tasks.yaml`, it's added automatically based on its `state` field
- If a task is listed in `tasks.yaml` but the file doesn't exist, it's removed from the yaml
- If a task's `state` field differs from its yaml column, the file's `state` takes precedence and yaml is updated

---

## 3. TUI Features (MVP)

### 3.1 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  sltasks                                           [Filter: none]   │
├───────────────────┬───────────────────┬───────────────────┬─────────┤
│ TO DO (3)         │ IN PROGRESS (1)   │ DONE (2)          │         │
├───────────────────┼───────────────────┼───────────────────┤         │
│                   │                   │                   │         │
│ ► Fix login bug   │   Refactor API    │   Setup CI        │         │
│   🔴 high         │   🟡 medium       │   🟢 low          │         │
│   bug, auth       │   backend         │   devops          │         │
│                   │                   │                   │         │
│   Add user auth   │                   │   Write docs      │         │
│   🟡 medium       │                   │   🟡 medium       │         │
│   feature         │                   │   docs            │         │
│                   │                   │                   │         │
│   Plan Q2 work    │                   │                   │         │
│   🟡 medium       │                   │                   │         │
│   plan            │                   │                   │         │
│                   │                   │                   │         │
└───────────────────┴───────────────────┴───────────────────┴─────────┘
│ ? help  q quit  f filter  : command                                 │
└─────────────────────────────────────────────────────────────────────┘
```

- Horizontal 3-column layout: To Do, In Progress, Done
- Archive column hidden by default (shown via filter)
- Each task displays: title, priority indicator, tags
- Selected task visually highlighted
- Status bar shows available commands

### 3.2 Keyboard Navigation

| Key | Action |
|-----|--------|
| `↑` / `k` | Move selection up |
| `↓` / `j` | Move selection down |
| `←` / `h` | Move selection to previous column |
| `→` / `l` | Move selection to next column |
| `Shift + ←/→` | Move task to adjacent column |
| `Enter` | Open task in `$EDITOR` |
| `a` | Archive selected task |
| `n` | Create new task |
| `f` | Open filter input |
| `:` | Enter command mode |
| `?` | Show help screen |
| `q` | Quit |

All keybindings customizable via config (future).

### 3.3 Task Detail/Edit

When pressing `Enter` on a task:

- Opens the task's markdown file in the user's `$EDITOR`
- On editor exit, TUI reloads the file and updates display
- Any field changes (state, tags, etc.) are reflected immediately

### 3.4 Task Creation

When pressing `n`:

1. Prompt for task title
2. Generate filesystem-safe filename from title (e.g., "Fix Login Bug" → `fix-login-bug.md`)
3. Create file with default front matter:
   ```yaml
   ---
   title: "Fix Login Bug"
   state: todo
   priority: medium
   tags: []
   created: 2025-01-15T10:30:00Z
   updated: 2025-01-15T10:30:00Z
   ---
   
   
   ```
4. Open in `$EDITOR` for user to add details
5. On save, task appears in To Do column

### 3.5 Tagging System

Tags are arbitrary strings defined per-task. Colors are configured globally:

```yaml
# In config file (future)
tag_colors:
  bug: red
  feature: blue
  plan: cyan
  docs: green
  # Prefix-based tags
  priority:
    critical: red
    high: orange
    medium: yellow
    low: green
```

For MVP, use sensible default colors.

### 3.6 Filtering

Filter syntax supports:

| Filter | Example | Description |
|--------|---------|-------------|
| Text search | `login` | Matches title or body |
| Tag filter | `tag:bug` | Tasks with specific tag |
| State filter | `state:in_progress` | Tasks in specific state |
| Priority filter | `priority:high` | Tasks with specific priority |
| Negation | `-tag:plan` | Exclude matching tasks |
| Archive toggle | `archived:true` | Show archived tasks |
| Combined | `tag:bug priority:high` | Multiple conditions (AND) |

Activated via `f` key or `:filter <expression>` command.

### 3.7 Command Mode

Press `:` to enter command mode. Available commands:

| Command | Description |
|---------|-------------|
| `:filter <expr>` | Apply filter expression |
| `:new` or `:create` | Create new task |
| `:archive` | Archive selected task |
| `:help` | Show help screen |
| `:q` or `:quit` | Quit application |

Tab completion for commands (future enhancement).

### 3.8 Help Screen

Press `?` to show overlay with:

- All keybindings and their actions
- Filter syntax reference
- Command mode commands
- Quick tips

---

## 4. Configuration

### 4.1 CLI Flags (MVP)

```bash
sltasks [OPTIONS]

Options:
  --task-root <PATH>    Path to tasks directory (default: .tasks/)
  --help                Show help
  --version             Show version
```

### 4.2 Config File (Future)

Location: `~/.config/sltasks/config.yaml` or `.tasks/config.yaml`

```yaml
keybindings:
  quit: q
  help: "?"
  filter: f
  archive: a
  new: n
  
tag_colors:
  bug: red
  feature: blue
  
priority_colors:
  critical: red
  high: orange
  medium: yellow
  low: green

default_priority: medium
```

---

## 5. Technical Implementation

### 5.1 Recommended Stack

- **Language:** Python 3.11+
- **TUI Framework:** [Textual](https://textual.textualize.io/)
  - Rapid prototyping
  - Excellent TUI components
  - Good async support for file watching
- **Configuration:** [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- **YAML Parsing:** PyYAML or ruamel.yaml
- **Markdown Parsing:** python-frontmatter

### 5.2 Project Structure

```
sltasks/
├── pyproject.toml
├── README.md
├── src/
│   └── sltasks/
│       ├── __init__.py
│       ├── __main__.py              # CLI entry point
│       ├── app.py                   # Textual application
│       │
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py          # Pydantic Settings classes
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── task.py              # Task domain model
│       │   ├── board.py             # Board state model
│       │   └── enums.py             # TaskState, Priority enums
│       │
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── base.py              # Abstract repository interface
│       │   ├── filesystem.py        # File-based implementation
│       │   └── (future: jira.py, github.py)
│       │
│       ├── services/
│       │   ├── __init__.py
│       │   ├── task_service.py      # Task CRUD operations
│       │   ├── board_service.py     # Board state management
│       │   └── filter_service.py    # Filter parsing & execution
│       │
│       ├── ui/
│       │   ├── __init__.py
│       │   ├── screens/
│       │   │   ├── __init__.py
│       │   │   ├── board.py         # Main kanban board screen
│       │   │   └── help.py          # Help overlay screen
│       │   ├── widgets/
│       │   │   ├── __init__.py
│       │   │   ├── column.py        # Kanban column widget
│       │   │   ├── task_card.py     # Task card widget
│       │   │   ├── filter_bar.py    # Filter input widget
│       │   │   └── command_bar.py   # Command mode widget
│       │   └── styles.py            # CSS/styling constants
│       │
│       └── utils/
│           ├── __init__.py
│           ├── slug.py              # Filename generation
│           └── datetime.py          # ISO datetime helpers
│
└── tests/
    ├── conftest.py
    ├── test_models/
    ├── test_repositories/
    ├── test_services/
    └── test_ui/
```

### 5.3 Architecture Pattern

The application follows a **Repository + Service** pattern to separate concerns and enable future backend integrations:

```
┌─────────────────────────────────────────────────────────────────┐
│                        TUI Layer (Textual)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │
│  │ BoardScreen │  │ HelpScreen  │  │  Widgets    │              │
│  └──────┬──────┘  └─────────────┘  └─────────────┘              │
└─────────┼───────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                       Service Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐          │
│  │ TaskService  │  │ BoardService │  │ FilterService │          │
│  └──────┬───────┘  └──────┬───────┘  └───────────────┘          │
└─────────┼─────────────────┼─────────────────────────────────────┘
          │                 │
┌─────────▼─────────────────▼─────────────────────────────────────┐
│                     Repository Layer                             │
│  ┌────────────────────────────────────────────────────────┐     │
│  │              TaskRepository (Abstract)                  │     │
│  │  - get_all() -> list[Task]                             │     │
│  │  - get_by_id(id) -> Task                               │     │
│  │  - save(task) -> Task                                  │     │
│  │  - delete(id) -> None                                  │     │
│  │  - get_board_order() -> BoardOrder                     │     │
│  │  - save_board_order(order) -> None                     │     │
│  └────────────────────────────────────────────────────────┘     │
│         ▲                    ▲                    ▲              │
│         │                    │                    │              │
│  ┌──────┴──────┐  ┌─────────┴────────┐  ┌───────┴───────┐      │
│  │ Filesystem  │  │  GitHub Projects │  │     Jira      │      │
│  │   (MVP)     │  │    (future)      │  │   (future)    │      │
│  └─────────────┘  └──────────────────┘  └───────────────┘      │
└─────────────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                       Storage Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐                       │
│  │  .tasks/*.md    │  │   tasks.yaml    │                       │
│  │  (task files)   │  │   (ordering)    │                       │
│  └─────────────────┘  └─────────────────┘                       │
└─────────────────────────────────────────────────────────────────┘
```

**Layer Responsibilities:**

| Layer | Responsibility |
|-------|----------------|
| **TUI** | User interaction, display, keyboard handling |
| **Services** | Business logic, validation, orchestration |
| **Repositories** | Data access abstraction, CRUD operations |
| **Storage** | Actual persistence (files, APIs, databases) |

### 5.4 Key Abstractions

**Abstract Repository Interface:**

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from .models import Task, BoardOrder

class TaskRepository(ABC):
    """Abstract interface for task storage backends."""
    
    @abstractmethod
    def get_all(self) -> List[Task]:
        """Retrieve all tasks."""
        ...
    
    @abstractmethod
    def get_by_id(self, task_id: str) -> Optional[Task]:
        """Retrieve a single task by ID."""
        ...
    
    @abstractmethod
    def save(self, task: Task) -> Task:
        """Create or update a task."""
        ...
    
    @abstractmethod
    def delete(self, task_id: str) -> None:
        """Delete a task."""
        ...
    
    @abstractmethod
    def get_board_order(self) -> BoardOrder:
        """Get the ordering of tasks within columns."""
        ...
    
    @abstractmethod
    def save_board_order(self, order: BoardOrder) -> None:
        """Persist the ordering of tasks within columns."""
        ...
```

**Pydantic Settings:**

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    """Application configuration via environment or CLI."""
    
    task_root: Path = Field(
        default=Path(".tasks"),
        description="Path to tasks directory"
    )
    editor: str = Field(
        default_factory=lambda: os.environ.get("EDITOR", "vim"),
        description="Editor for task editing"
    )
    
    class Config:
        env_prefix = "SLTASKS_"
```

### 5.5 Data Flow

```
                    ┌─────────────────┐
                    │  .tasks/*.md    │  ← Source of truth
                    │   (task files)  │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ FileRepository  │  ← Parses YAML front matter
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ tasks.yaml  │ ←── │  Services   │ ──► │   TUI View  │
│  (ordering) │     │  (in memory)│     │  (display)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 5.6 Sync Behavior

On startup:
1. Scan `.tasks/` for all `.md` files
2. Parse each file's front matter
3. Load `tasks.yaml` for ordering
4. Reconcile: files are truth, yaml provides order
5. Write updated `tasks.yaml` if changes detected

On task move (in TUI):
1. Update task file's `state` field
2. Update task file's `updated` timestamp
3. Update `tasks.yaml` ordering
4. Refresh display

On external file change (future):
1. Detect via file watcher
2. Reload affected task
3. Update yaml if needed
4. Refresh display

---

## 6. Future Enhancements (Post-MVP)

### 6.1 Near-term

- **Undo/redo** – Track recent actions, allow reversal
- **Sorting options** – By date, priority, title (via filter/command)
- **Custom columns** – User-defined states beyond the default four
- **Multi-select** – Batch operations on multiple tasks
- **Safe delete** – Move to trash instead of permanent delete
- **File watching** – Auto-reload on external changes

### 6.2 Medium-term

- **Project switching** – Quick switch between different task roots
- **Templates** – Create tasks from predefined templates
- **Task duplication** – Clone existing tasks
- **Statistics panel** – Task counts, completion rates
- **Progress indicators** – Visual progress bars
- **WIP limits** – Max tasks per column

### 6.3 Long-term

- **Due dates** – `due:` field with overdue highlighting
- **Dependencies** – `blocked_by:` field linking tasks
- **Time tracking** – `estimate:` and `time_spent:` fields
- **Auto-archive** – Time-based workflow automation
- **Nested boards** – Sub-projects, meta-boards
- **Custom keybindings** – Full keyboard customization
- **Conflict resolution** – Handle concurrent edits gracefully

---

## 7. Non-Goals (MVP)

- LLM integration within the TUI
- GitHub/Jira sync
- Collaboration features
- Web UI
- Mobile app
- Database backend

---

## 8. Success Criteria

MVP is successful when:

1. User can view tasks in a 3-column kanban layout
2. User can navigate and move tasks between columns
3. User can create new tasks from TUI
4. User can edit tasks via `$EDITOR`
5. User can filter tasks by tag, state, priority, or text
6. User can archive tasks (hidden from default view)
7. External task file edits are reflected on TUI reload
8. Help screen documents all keybindings
9. Command mode provides alternative interaction method

---

## Appendix A: Example Task Files

### Bug Report

```yaml
---
title: "Login timeout on peak hours"
state: in_progress
priority: high
tags: [bug, auth, backend, production]
created: 2025-01-10T09:00:00Z
updated: 2025-01-14T16:30:00Z
---

## Problem

Users report ERR_TIMEOUT when logging in between 9-11am EST.

## Investigation

- [ ] Check connection pool settings
- [x] Review recent auth service changes
- [ ] Analyze peak hour metrics

## Root Cause

TBD

## Solution

TBD
```

### Feature Plan

```yaml
---
title: "Q2 API redesign plan"
state: todo
priority: medium
tags: [plan, api, q2]
created: 2025-01-08T14:00:00Z
updated: 2025-01-08T14:00:00Z
---

## Objective

Modernize API to support new mobile client requirements.

## Key Deliverables

1. OpenAPI 3.1 spec
2. Breaking change migration guide
3. Performance benchmarks

## Timeline

- Week 1-2: Design review
- Week 3-4: Implementation
- Week 5: Testing & documentation
```

### Minimal Task (No Front Matter)

```markdown
# Quick note

Remember to update the README with new CLI flags.
```

This file would load with:
- Title: "quick-note" (from filename)
- State: todo (default)
- Priority: medium (default)
- Tags: [] (default)
