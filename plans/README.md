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
│   ├── README.md            # This file
│   ├── phase-1-setup.md
│   ├── phase-2-models.md
│   ├── phase-3-repository.md
│   ├── phase-4-services.md
│   └── phase-5-basic-tui.md
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
| 6 | Task Cards | Planned (docs later) |
| 7 | Navigation | Planned (docs later) |
| 8 | Actions | Planned (docs later) |
| 9 | Filter/Command | Planned (docs later) |
| 10 | Help Screen | Planned (docs later) |
| 11 | Polish | Planned (docs later) |

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
