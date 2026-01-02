# File Provider

The File Provider stores tasks as individual markdown files in your project directory. This is the default provider and requires no external services.

## Overview

- **Storage:** Local markdown files with YAML frontmatter
- **Location:** `.tasks/` directory (configurable)
- **Ordering:** `tasks.yaml` file tracks task positions
- **Version control:** Git-friendly plain text files

## Setup

The File Provider works out of the box with no configuration. To generate a starter config:

```bash
sltasks --generate
```

This creates:

- `sltasks.yml` - Board configuration
- `.tasks/` - Task directory
- `.tasks/templates/` - Task templates for each type

You can also just run `sltasks` without any config file to use defaults.

## Directory Structure

```
project-root/
├── sltasks.yml              # Board configuration
└── .tasks/
    ├── tasks.yaml           # Task ordering (auto-managed)
    ├── templates/           # Task templates
    │   ├── feature.md
    │   ├── bug.md
    │   └── task.md
    ├── my-first-task.md     # Task files
    └── another-task.md
```

## Task File Format

Each task is a markdown file with YAML frontmatter:

```markdown
---
title: Fix login bug
state: todo
priority: high
type: bug
tags:
  - auth
  - urgent
created: '2025-01-15T10:30:00+00:00'
updated: '2025-01-15T14:22:00+00:00'
---

## Description

Users cannot log in when using special characters in passwords.

## Steps to Reproduce

1. Go to login page
2. Enter password with special characters
3. Click submit

## Expected Behavior

User should be logged in successfully.
```

### Frontmatter Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `title` | No | Filename | Task title displayed in the TUI |
| `state` | No | First column | Column ID (e.g., `todo`, `in_progress`, `done`) |
| `priority` | No | `medium` | Priority ID (e.g., `low`, `medium`, `high`, `critical`) |
| `type` | No | None | Type ID (e.g., `feature`, `bug`, `task`) |
| `tags` | No | `[]` | List of tag strings |
| `created` | Auto | Current time | ISO 8601 timestamp |
| `updated` | Auto | Current time | ISO 8601 timestamp |

## Configuration

### Basic Configuration

```yaml
version: 1
provider: file          # Optional, file is default
task_root: .tasks       # Task directory path

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
    - id: task
      color: white
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
    - id: critical
      label: Critical
      color: red
```

### Status Aliases

Map alternative status values to column IDs:

```yaml
columns:
  - id: done
    title: Done
    status_alias:
      - completed
      - finished
      - closed
```

When a task has `state: completed`, it appears in the `done` column.

### Type Aliases

Map alternative type names:

```yaml
types:
  - id: bug
    color: red
    type_alias:
      - defect
      - issue
```

### Priority Aliases

Map alternative priority names:

```yaml
priorities:
  - id: critical
    label: Critical
    color: red
    priority_alias:
      - blocker
      - urgent
```

## Templates

Templates provide default content when creating new tasks. Store them in `{task_root}/templates/`.

**Example: `templates/bug.md`**

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

When you create a new task with type `bug`, this template's body is used and `priority: high` becomes the default.

## Task Ordering

The `tasks.yaml` file tracks task positions within columns:

```yaml
todo:
  - fix-login-bug.md
  - add-dark-mode.md
in_progress:
  - refactor-api.md
done:
  - update-readme.md
```

This file is automatically managed by sltasks. You generally don't need to edit it manually.

## Git Integration

The File Provider is designed for git-tracked projects:

- All files are plain text (markdown + YAML)
- Easy to diff, merge, and review changes
- Works offline with full functionality
- Commit task changes alongside code changes

**Recommended `.gitignore` entries:**

```
# None needed - all sltasks files should be tracked
```

## External Editing

You can create and edit task files directly with any text editor:

1. Create a new `.md` file in `.tasks/`
2. Add YAML frontmatter with at least `title` and `state`
3. sltasks will pick up the changes on next load

The TUI automatically detects file changes and reloads.

## Technical Details

For implementation details and the repository protocol, see the [Repository Protocol Design](../design/repository-protocol.md).
