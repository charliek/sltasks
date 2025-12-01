# Configuration

## Board configuration

The `sltasks.yml` file defines your board columns. Place it in your project root.

### Column configuration

```yaml
columns:
  - id: backlog
    title: Backlog
  - id: todo
    title: To Do
  - id: in_progress
    title: In Progress
  - id: review
    title: Code Review
  - id: done
    title: Done
```

Each column has:

| Property | Description |
|----------|-------------|
| `id` | Internal identifier used in task `state` field (lowercase, alphanumeric, underscores) |
| `title` | Display name shown in the TUI header |
| `status_alias` | Optional list of alternative status values mapping to this column ID |

### Status Aliases

Aliases allow you to map multiple status values to a single column. This is useful if you have existing files with different state names or if you want to support synonyms.

When a task is loaded with an alias state (e.g., `completed`), it will be placed in the corresponding column (e.g., `done`). When the task is next saved, the state will be normalized to the canonical column ID.

**Default aliases (applied if no config file exists):**
- `todo`: `new`
- `done`: `completed`, `finished`, `complete`

### Constraints

- Minimum 2 columns, maximum 6 columns
- Column `id` must be unique and lowercase
- Aliases must not duplicate column IDs or other aliases

### Example configurations

**Software development:**

```yaml
columns:
  - id: backlog
    title: Backlog
    status_alias:
      - pending
  - id: todo
    title: To Do
  - id: in_progress
    title: In Progress
  - id: review
    title: Code Review
  - id: done
    title: Done
    status_alias:
      - fixed
      - resolved
```

**Simple todo list:**

```yaml
columns:
  - id: todo
    title: To Do
  - id: done
    title: Done
```

**Content creation:**

```yaml
columns:
  - id: ideas
    title: Ideas
  - id: drafting
    title: Drafting
  - id: editing
    title: Editing
  - id: published
    title: Published
```

## Task file format

Tasks are Markdown files with YAML frontmatter stored in the `.tasks/` directory:

```yaml
---
title: "Fix login bug"
state: todo
priority: high
tags: [bug, auth]
---

Task description here.
```

All fields are optional. Missing fields use defaults:

| Field | Default |
|-------|---------|
| `title` | Filename |
| `state` | `todo` |
| `priority` | `medium` |
| `tags` | `[]` |
