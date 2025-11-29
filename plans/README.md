# Kosmos - Implementation Plans

> **kosmos** (κόσμος) – from Greek, meaning "order, harmony" (opposite of chaos)

## Project Overview

Kosmos is a terminal-based Kanban TUI for managing tasks stored as Markdown files with YAML front matter. It provides lightweight, structured task management for personal projects without the overhead of solutions like Jira or GitHub Projects.

### Core Principles

- **Markdown files are the single source of truth** – Users or LLMs can create/edit task files directly; the TUI adapts automatically
- **Terminal-first** – Fast, keyboard-driven interface
- **Git-friendly** – All data is plain text, version controllable
- **Minimal configuration** – Works out of the box with sensible defaults

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        TUI Layer (Textual)                       │
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
│  │           FilesystemRepository                          │     │
│  │  - get_all() / get_by_id() / save() / delete()         │     │
│  │  - get_board_order() / save_board_order() / reload()   │     │
│  └────────────────────────────────────────────────────────┘     │
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

### Layer Responsibilities

| Layer | Responsibility |
|-------|----------------|
| **TUI** | User interaction, display, keyboard handling |
| **Services** | Business logic, validation, orchestration |
| **Repository** | Data access, file I/O operations |
| **Storage** | Actual persistence (markdown files, YAML) |

## Technology Stack

- **Python 3.13**
- **Textual** - TUI framework
- **Pydantic / Pydantic Settings** - Models and configuration
- **python-frontmatter** - Markdown with YAML front matter parsing
- **pytest** - Testing (integration-focused)

## Project Structure

```
kosmos/
├── pyproject.toml
├── README.md
├── plans/                    # Implementation documentation (this directory)
│   ├── README.md            # This file (project summary)
│   ├── phase-1-setup.md     # Project scaffolding
│   ├── phase-2-models.md    # Pydantic models
│   ├── phase-3-repository.md # Filesystem repository
│   ├── phase-4-services.md  # Business logic services
│   ├── phase-5-basic-tui.md # Initial Textual app
│   ├── phase-6-task-cards.md # Task card widget
│   ├── phase-7-navigation.md # Keyboard navigation
│   ├── phase-8-actions.md   # Task CRUD actions
│   ├── phase-9-filter-command.md # Filter bar
│   ├── phase-10-help-screen.md # Help modal
│   ├── phase-11-task-preview.md # Preview modal
│   └── phase-12-tests.md    # Test coverage
├── src/
│   └── kosmos/
│       ├── __init__.py
│       ├── __main__.py      # CLI entry point
│       ├── app.py           # Textual application
│       ├── config/
│       │   └── settings.py  # Pydantic Settings
│       ├── models/
│       │   ├── task.py      # Task domain model
│       │   ├── board.py     # Board state model
│       │   └── enums.py     # TaskState, Priority enums
│       ├── repositories/
│       │   └── filesystem.py
│       ├── services/
│       │   ├── task_service.py
│       │   ├── board_service.py
│       │   └── filter_service.py
│       ├── ui/
│       │   ├── screens/
│       │   │   ├── board.py
│       │   │   └── help.py
│       │   ├── widgets/
│       │   │   ├── column.py
│       │   │   ├── task_card.py
│       │   │   ├── filter_bar.py
│       │   │   └── command_bar.py
│       │   └── styles.py
│       └── utils/
│           ├── slug.py
│           └── datetime.py
└── tests/
```

## Implementation Phases

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | [Project Setup](./phase-1-setup.md) | **Complete** |
| 2 | [Models & Data Layer](./phase-2-models.md) | **Complete** |
| 3 | [Repository Layer](./phase-3-repository.md) | **Complete** |
| 4 | [Service Layer](./phase-4-services.md) | **Complete** |
| 5 | [Basic TUI](./phase-5-basic-tui.md) | **Complete** |
| 6 | [Task Cards Enhancement](./phase-6-task-cards.md) | **Complete** |
| 7 | [Keyboard Navigation](./phase-7-navigation.md) | **Complete** |
| 8 | [Task Actions](./phase-8-actions.md) | **Complete** |
| 9 | [Filter & Command Bar](./phase-9-filter-command.md) | **Complete** |
| 10 | [Help Screen](./phase-10-help-screen.md) | **Complete** |
| 11 | [Task Preview Modal](./phase-11-task-preview.md) | **Complete** |
| 12 | [Test Coverage](./phase-12-tests.md) | **Complete** |

## Deferred Features

The following features were identified during implementation but deferred for simplicity or lower priority:

### UI Enhancements
| Feature | Phase | Reason |
|---------|-------|--------|
| Timestamp display on task cards | 6 | Adds visual clutter; timestamps visible in preview modal |
| Filtered/total counts in headers (e.g., "To Do 2/5") | 9 | Complexity vs. value tradeoff |
| Filter autocomplete (tag:, state:, priority:) | 9 | Can add as future enhancement |
| Dynamic binding collection for help | 10 | Manual approach is more readable |

### Interaction
| Feature | Phase | Reason |
|---------|-------|--------|
| Move mode (`m` key) | 8 | Direct H/L/J/K bindings are sufficient |

### Infrastructure
| Feature | Phase | Reason |
|---------|-------|--------|
| File watching (auto-reload) | - | Post-MVP; `reload()` method ready |
| Abstract repository interface | - | YAGNI until multiple backends needed |

## Key Architectural Insights

Lessons learned across all implementation phases:

### Data Flow
- **File state is truth**: The task file's `state` field always wins over YAML column placement
- **Filename is the stable identifier**: Titles can change; filename is the key
- **YAML provides ordering only**: `tasks.yaml` tracks position within columns, not state

### Service Layer
- **Services own business logic**: Repository handles only I/O operations
- **Archived tasks are special**: Excluded from normal state flow (TODO → IN_PROGRESS → DONE)
- **FilterService is stateless**: No repository dependency needed

### Textual Patterns
- Use `App.suspend()` for external editor integration
- Access services via `self.app.service_name` pattern
- Styles can be in `.tcss` files or `DEFAULT_CSS` in widgets
- Use built-in CSS variables (`$primary`, `$surface`, etc.)

### Testing
- Integration tests at service layer catch regressions without UI brittleness
- Use real filesystem via `tmp_path` fixture (no mocking)
- 93 tests total: repository, services, models, filters, slugs

## Suggested Next Steps

Based on the PRD's future enhancements, prioritized by implementation readiness:

### High Value / Lower Effort
1. **File watching** - Repository already has `reload()` method; add watchdog integration
2. **Sorting options** - Extend FilterService with `sort:priority`, `sort:date` syntax
3. **Task duplication** - TaskService.create_task() infrastructure exists

### Medium Value / Medium Effort
4. **Due dates** - Add `due` field to Task model + filter support + overdue styling
5. **Templates** - Task creation with predefined content from `.tasks/templates/`
6. **Statistics panel** - Board model already groups tasks; add counts widget

### Larger Efforts
7. **Undo/redo** - Requires action history tracking
8. **Custom columns** - Significant refactor of TaskState enum
9. **Multi-select** - UI complexity for batch operations

### Non-Goals (from PRD)
- LLM integration within TUI
- GitHub/Jira sync
- Web UI / Mobile app
- Database backend

## Design Decisions

### No Abstract Base Classes (for now)
We've chosen to implement the repository layer directly without ABC interfaces. This avoids over-engineering at this stage. If we need to support multiple backends later (GitHub Projects, Jira, etc.), we can extract an interface then.

### Integration Tests Over Unit Tests
We prefer testing key outcomes over detailed unit tests with extensive mocking. Unit tests are reserved for complex logic (filter parsing, slug generation).

### File Watching Deferred
Auto-reload on external file changes is deferred to post-MVP. The repository includes a `reload()` method to support this feature later.

### Types Without Enforcement
We use type hints throughout the codebase and prefer Pydantic models over raw dicts/lists. However, we're not enforcing types with mypy initially.

## Data Model

### Task File Format

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

Users are experiencing timeout errors when logging in.

## Acceptance Criteria

- [ ] Identify root cause
- [ ] Implement fix
```

All fields are optional. Files without front matter are loaded with defaults.

### Board Order File (tasks.yaml)

```yaml
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

This file is system-managed and provides custom ordering within columns. Task files are the source of truth for state.

## PRD Reference

The full product requirements document is available at `docs/kosmos_prd.md`.
