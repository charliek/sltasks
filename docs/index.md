# sltasks

A terminal-based Kanban TUI for markdown task management.

## Overview

**sltasks** is a lightweight, keyboard-driven task management tool that runs in your terminal. Tasks are stored as plain Markdown files with YAML frontmatter, making them easy to edit, version control, and integrate with other tools.

## Key Features

- **Markdown-first** - Tasks are stored as `.md` files that you can edit with any tool
- **Keyboard-driven** - Vim-style navigation for fast task management
- **Git-friendly** - All data is plain text, perfect for version control
- **Zero configuration** - Works out of the box with sensible defaults
- **Custom columns** - Define your own workflow states

## Quick Example

```
┌─────────────────────────────────────────────────────────────────────┐
│  sltasks                                           [Filter: none]   │
├───────────────────┬───────────────────┬───────────────────┬─────────┤
│ TO DO (3)         │ IN PROGRESS (1)   │ DONE (2)          │         │
├───────────────────┼───────────────────┼───────────────────┤         │
│                   │                   │                   │         │
│ ► Fix login bug   │   Refactor API    │   Setup CI        │         │
│   high            │   medium          │   low             │         │
│   bug, auth       │   backend         │   devops          │         │
│                   │                   │                   │         │
└───────────────────┴───────────────────┴───────────────────┴─────────┘
```

## Next Steps

- [Getting Started](getting-started/installation.md) - Installation and quick start guide
- [User Guide](user-guide/configuration.md) - Configuration and usage
