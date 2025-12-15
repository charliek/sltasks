# Configuration

The `sltasks.yml` file defines your board configuration. Place it in your project root.

## Full Configuration Reference

```yaml
version: 1
provider: file       # Storage backend: file (default), github, github-prs, jira
task_root: .tasks    # Directory for task files

board:
  columns:
    # ... column definitions
  types:
    # ... type definitions
  priorities:
    # ... priority definitions
```

> **Note:** GitHub Projects is supported. Jira integration is planned for a future release.

## Board configuration

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

## Priorities

Priorities are configurable levels of importance for tasks, with customizable colors, symbols, and ordering.

### Priority configuration

```yaml
board:
  columns:
    # ... columns
  priorities:  # Ordered lowest to highest
    - id: low
      label: Low
      color: green
      symbol: ●
      priority_alias:
        - trivial
        - minor
    - id: medium
      label: Medium
      color: yellow
    - id: high
      label: High
      color: orange1
      priority_alias:
        - important
    - id: critical
      label: Critical
      color: red
      priority_alias:
        - blocker
        - urgent
```

Each priority has:

| Property | Description |
|----------|-------------|
| `id` | Internal identifier used in task `priority` field (lowercase, alphanumeric, underscores) |
| `label` | Display name shown in the TUI |
| `color` | Display color - named color or hex code |
| `symbol` | Display symbol (defaults to ●) |
| `priority_alias` | Optional list of alternative priority values mapping to this priority ID |

### Priority Ordering

The order in the configuration determines priority rank. First in list = lowest priority, last = highest. This enables meaningful sorting and comparison.

### Priority Aliases

Priority aliases work like status and type aliases - they map alternative names to canonical priority IDs. This is useful when:
- You have existing files with different priority names
- You want to support synonyms (e.g., `urgent` → `critical`, `trivial` → `low`)

### Default Priorities

If no priorities are configured, these defaults are used (ordered lowest to highest):

- `low` (green)
- `medium` (yellow)
- `high` (orange)
- `critical` (red)

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
| `state` | `todo` (first configured column) |
| `priority` | `medium` (configurable, see Priorities section) |
| `type` | (none) |
| `tags` | `[]` |

## GitHub Provider

Use GitHub Projects as your task backend instead of local markdown files.

### Quick Setup

Run the interactive setup command:

```bash
sltasks --github-setup
# Or provide the project URL directly:
sltasks --github-setup https://github.com/users/USERNAME/projects/1
```

This auto-detects your project's Status columns and generates a complete configuration.

### GitHub Configuration Reference

```yaml
provider: github
task_root: .tasks    # Still used for local cache/templates

github:
  project_url: https://github.com/users/USERNAME/projects/1
  default_repo: username/repository   # Repository for new issues
  default_status: To Do               # Optional: status for new items
  priority_field: Priority            # Optional: project field for priority

board:
  columns:
    # Auto-generated from GitHub Status field
    - id: to_do
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
  priorities:
    - id: low
      label: Low
      color: green
    - id: medium
      label: Medium
      color: yellow
    - id: high
      label: High
      color: orange1
```

### GitHub Configuration Options

| Property | Required | Description |
|----------|----------|-------------|
| `project_url` | Yes | GitHub project URL (user or org format) |
| `default_repo` | Yes | Repository for creating new issues (`owner/repo`) |
| `default_status` | No | Status to assign to new items |
| `priority_field` | No | Single-select project field for priority |

### Column Auto-Detection

Columns are automatically derived from your GitHub project's Status field using slugification:

| GitHub Status | Column ID |
|---------------|-----------|
| "To Do" | `to_do` |
| "In Progress" | `in_progress` |
| "Done" | `done` |
| "In Review" | `in_review` |

### Priority from Project Fields

If your project has a single-select field like "Priority" or "Severity", you can map it:

```yaml
github:
  priority_field: Priority  # Name of the field in your project
```

Priority options are mapped by position: first option = lowest priority.

If no `priority_field` is configured, priority is read from issue labels instead.

### Authentication

The GitHub provider authenticates via:

1. `GITHUB_TOKEN` environment variable, or
2. `gh` CLI (if authenticated via `gh auth login`)

**Required token scopes:** `read:project`, `project`, `repo`

### Type and Priority Labels

When creating or updating issues, types and priorities can be synced to GitHub labels using the `canonical_alias` field:

```yaml
board:
  types:
    - id: bug
      color: red
      canonical_alias: bug        # Label name in GitHub
  priorities:
    - id: high
      label: High
      color: orange1
      canonical_alias: priority:high  # Label name in GitHub
```
