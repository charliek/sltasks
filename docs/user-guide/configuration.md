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

## Task Types

Task types allow you to categorize tasks (e.g., feature, bug, task) with associated templates and visual styling.

### Type configuration

```yaml
board:
  columns:
    # ... columns
  types:
    - id: feature
      color: blue
    - id: bug
      color: red
      type_alias:
        - defect
        - issue
    - id: task
      color: white
      type_alias:
        - chore
```

Each type has:

| Property | Description |
|----------|-------------|
| `id` | Internal identifier used in task `type` field (lowercase, alphanumeric, underscores) |
| `template` | Optional template filename (defaults to `{id}.md`) |
| `color` | Display color - named color (blue, red, etc.) or hex code (#ff0000) |
| `type_alias` | Optional list of alternative type values mapping to this type ID |

### Templates

Templates are stored in `{task_root}/templates/` and provide default content for new tasks. When you create a task with a type, the template's body content is used and its frontmatter fields (like `priority` and `tags`) become defaults.

**Example template (`templates/bug.md`):**

```markdown
---
priority: high
tags: []
---

## Description

[What is happening?]

## Steps to Reproduce

1. Step 1
2. Step 2

## Expected Behavior

[What should happen]
```

When creating a new bug task, this template provides the body content and sets priority to `high` by default.

### Type Aliases

Type aliases work like status aliases - they map alternative type names to canonical type IDs. This is useful when:
- You have existing files with different type names
- You want to support synonyms (e.g., `defect` → `bug`)

### Default types

If no config file exists, these default types are used:
- `feature` (blue)
- `bug` (red) - aliases: `defect`, `issue`
- `task` (white) - aliases: `chore`

Running `sltasks --generate` creates default templates in `{task_root}/templates/`.

## Task file format

Tasks are Markdown files with YAML frontmatter stored in the `.tasks/` directory:

```yaml
---
title: "Fix login bug"
state: todo
priority: high
type: bug
tags: [auth]
---

Task description here.
```

All fields are optional. Missing fields use defaults:

| Field | Default |
|-------|---------|
| `title` | Filename |
| `state` | `todo` |
| `priority` | `medium` |
| `type` | (none) |
| `tags` | `[]` |
