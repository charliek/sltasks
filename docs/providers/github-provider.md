# GitHub Provider

The GitHub Provider connects sltasks to GitHub Projects V2, letting you manage GitHub issues and pull requests directly from your terminal.

## Overview

- **Storage:** GitHub Projects V2 via GraphQL API
- **Data:** GitHub Issues and Pull Requests
- **Columns:** Mapped from the project's Status field
- **Collaboration:** Native GitHub team features

## Prerequisites

Before setting up the GitHub Provider, you need:

1. A GitHub Projects V2 board (classic projects are not supported)
2. A GitHub account with access to the project
3. Authentication configured (see below)

## Authentication

sltasks needs a GitHub token to access your project. There are two ways to authenticate:

### Option 1: GitHub CLI (Recommended)

If you have the [GitHub CLI](https://cli.github.com/) installed, sltasks will automatically use your authenticated session:

```bash
# Install gh CLI (if not already installed)
# macOS: brew install gh
# Ubuntu: sudo apt install gh

# Authenticate with GitHub
gh auth login
```

Follow the prompts to authenticate. Once complete, sltasks will automatically detect and use your `gh` CLI token.

### Option 2: Personal Access Token

Create a Personal Access Token (PAT) with the required permissions:

1. Go to **GitHub** → **Settings** → **Developer settings** → **Personal access tokens**
2. Choose **Fine-grained tokens** (recommended) or **Tokens (classic)**
3. Create a new token with these permissions:

**For Fine-grained tokens:**

- **Repository permissions:**
  - Issues: Read and write
  - Pull requests: Read and write
- **Account permissions:**
  - Projects: Read and write

**For Classic tokens:**

- `repo` (Full control of private repositories)
- `read:project` (Read access to projects)
- `project` (Full control of projects)

4. Set the token as an environment variable:

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
```

Add this to your shell profile (`.bashrc`, `.zshrc`, etc.) for persistence.

## Setup

Run the interactive setup wizard:

```bash
sltasks --github-setup
```

Or provide the project URL directly:

```bash
sltasks --github-setup https://github.com/users/USERNAME/projects/1
```

The wizard will:

1. Detect your project's Status field options → columns
2. Find any Priority-like fields for priority mapping
3. Detect repositories linked to the project
4. Generate a complete `sltasks.yml` configuration

## Setting Up Labels

sltasks uses GitHub labels to track task type and priority. You should create these labels in your repository before using sltasks.

### Type Labels

Create labels for each task type:

```bash
gh label create "type:feature" --color 0000FF --repo owner/repo
gh label create "type:bug" --color FF0000 --repo owner/repo
gh label create "type:task" --color FFFFFF --repo owner/repo
```

### Priority Labels

If you're **not** using a Priority project field, create priority labels:

```bash
gh label create "priority:low" --color 00FF00 --repo owner/repo
gh label create "priority:medium" --color FFFF00 --repo owner/repo
gh label create "priority:high" --color FFA500 --repo owner/repo
gh label create "priority:critical" --color FF0000 --repo owner/repo
```

!!! tip "Using a Priority field instead"
    If your GitHub Project has a single-select Priority field, configure `priority_field` in your config and skip creating priority labels. The project field takes precedence.

## Configuration

### Basic Configuration

```yaml
provider: github
task_root: .tasks

github:
  project_url: https://github.com/users/USERNAME/projects/1
  default_repo: username/repository
  default_status: Backlog
  priority_field: Priority

board:
  columns:
    - id: backlog
      title: Backlog
    - id: in_progress
      title: In Progress
    - id: done
      title: Done
  types:
    - id: feature
      canonical_alias: "type:feature"
      color: blue
    - id: bug
      canonical_alias: "type:bug"
      color: red
    - id: task
      canonical_alias: "type:task"
      color: white
  priorities:
    - id: low
      label: Low
      color: green
    - id: high
      label: High
      color: orange1
```

### GitHub Settings Reference

| Setting | Required | Description |
|---------|----------|-------------|
| `project_url` | Yes | GitHub project URL (`https://github.com/users/USER/projects/N` or `https://github.com/orgs/ORG/projects/N`) |
| `default_repo` | Yes | Repository for new issues (`owner/repo` format) |
| `default_status` | No | Initial Status field value for new issues |
| `priority_field` | No | Single-select project field to use for priority |
| `featured_labels` | No | Labels shown for quick assignment when editing |
| `base_url` | No | API URL for GitHub Enterprise (default: `api.github.com`) |
| `include_prs` | No | Include pull requests on board (default: `true`) |
| `include_closed` | No | Include closed issues (default: `false`) |
| `include_drafts` | No | Include draft issues (default: `false`) |

### Column Mapping

Columns are derived from your GitHub project's **Status** field. The setup wizard auto-detects these using slugification:

| GitHub Status | Column ID |
|---------------|-----------|
| "Backlog" | `backlog` |
| "To Do" | `to_do` |
| "In Progress" | `in_progress` |
| "In Review" | `in_review` |
| "Done" | `done` |

### Priority Mapping

Priority can come from two sources:

**1. Project Field (recommended for teams)**

Configure a single-select field in your GitHub Project:

```yaml
github:
  priority_field: Priority  # Field name in your project
```

Options are mapped by position: first option = lowest priority.

**2. Issue Labels (default)**

Without `priority_field`, priority is read from issue labels. The labels must match your configured priorities or their aliases.

### Label Configuration

#### `canonical_alias`

The `canonical_alias` specifies what GitHub label to **write** when saving a task:

```yaml
types:
  - id: bug
    canonical_alias: "type:bug"  # Label applied to GitHub issues
    color: red
```

When you change a task's type to `bug`, the label `type:bug` is applied to the issue.

#### `type_alias` / `priority_alias`

Aliases specify what labels to **read** when loading tasks:

```yaml
types:
  - id: bug
    canonical_alias: "type:bug"
    type_alias:
      - defect
      - error
    color: red
```

Issues with labels `type:bug`, `defect`, or `error` are all recognized as type `bug`.

### Featured Labels

Show frequently-used labels for quick assignment:

```yaml
github:
  featured_labels:
    - "needs-review"
    - "blocked"
    - "help wanted"
```

These appear as suggestions when editing tasks.

## Usage Notes

### Creating Issues

When you create a new task in sltasks:

1. A new GitHub Issue is created in `default_repo`
2. The Status field is set to `default_status`
3. Type and priority labels are applied based on `canonical_alias`

### Moving Tasks

Moving a task between columns updates the issue's Status field in GitHub Projects.

### Editing Tasks

Editing a task updates:

- Issue title and body
- Type/priority labels (using `canonical_alias`)
- Tags (as additional labels)

### Pull Requests

With `include_prs: true` (default), pull requests appear as tasks. They're displayed with a PR indicator and link to the PR instead of an issue.

### Archiving

Archiving a task closes the GitHub issue. The closed issue is excluded from the board unless `include_closed: true`.

## Filtering Options

Control what appears on your board:

```yaml
github:
  include_prs: true      # Show pull requests (default: true)
  include_closed: false  # Show closed issues (default: false)
  include_drafts: false  # Show draft issues (default: false)
```

## Filesystem Sync

Enable bidirectional sync between GitHub and local markdown files. This allows you to:

- Work offline with local copies of your issues
- Create issues by writing markdown files locally
- Use LLMs or scripts to generate tasks that sync to GitHub

### Configuration

```yaml
github:
  # ... other settings ...
  sync:
    enabled: true
    task_root: .tasks          # Optional: override global task_root
    filters:
      - "assignee:@me"         # Issues assigned to you
      - "label:urgent"         # Issues with specific label
```

### Filter Syntax

Filters use GitHub search syntax. Multiple filters are OR'd together - an issue syncs if it matches **any** filter.

| Filter | Description |
|--------|-------------|
| `assignee:@me` | Issues assigned to authenticated user |
| `assignee:USER` | Issues assigned to specific user |
| `label:NAME` | Issues with specific label |
| `is:open` | Open issues only |
| `is:closed` | Closed issues only |
| `milestone:NAME` | Issues in milestone |
| `repo:owner/repo` | Issues from specific repository |
| `priority:p1,p2` | Issues with specific priorities |
| `*` | All issues on the project |

### Synced File Format

Synced files use a naming convention that includes the GitHub issue reference:

```
owner-repo#123-fix-login-bug.md
```

They include GitHub metadata in frontmatter:

```yaml
---
title: Fix login bug
state: in_progress
priority: high
type: bug
tags: [auth]

github:
  synced: true
  issue_number: 123
  repository: owner/repo
  project_item_id: PVTI_xxx
  issue_node_id: I_xxx
  last_synced: '2025-01-15T14:00:00Z'

push_changes: false      # Set true to push local edits
close_on_github: false   # Set true to close issue on delete
---

Issue body content here...
```

### Sync Workflow

1. **Pull from GitHub**: Run `sltasks sync`
   - Fetches issues matching your filters
   - Creates/updates local markdown files

2. **Create issues locally**: Write new `.md` files in your task directory (without the `github:` section)

3. **Push to GitHub**: Run `sltasks push`
   - Creates GitHub issues from local-only files
   - Renames files to include the new issue number

4. **Handle conflicts**: When both local and GitHub have changes since last sync:
   - Default: GitHub version wins
   - Use `sltasks sync --force` to overwrite local changes
   - Set `push_changes: true` in frontmatter to push your local version instead

### CLI Commands

```bash
# Pull issues from GitHub
sltasks sync              # Sync matching issues
sltasks sync --dry-run    # Preview what would sync
sltasks sync --force      # Overwrite local changes

# Push local tasks to GitHub
sltasks push              # Push all local-only tasks
sltasks push --dry-run    # Preview without creating
sltasks push -y           # Skip confirmation
```

See [CLI Reference](../user-guide/cli.md#subcommands) for all options.

## GitHub Enterprise

For GitHub Enterprise, set the `base_url`:

```yaml
github:
  base_url: github.mycompany.com
  project_url: https://github.mycompany.com/users/USER/projects/1
  # ... other settings
```

## Troubleshooting

### Authentication Errors

```
Authentication failed. Check your GITHUB_TOKEN.
Required scopes: read:project, project, repo
```

**Solution:** Ensure your token has the required scopes. For fine-grained tokens, check both repository and account permissions.

### Permission Denied

```
Permission denied. Check that your token has the required scopes.
```

**Solution:** Your token may be missing scopes, or you may not have access to the project. Verify project access in GitHub.

### Project Not Found

```
Project not found or not accessible
```

**Solution:** Check the project URL format and ensure you have access. The URL should be:
- User project: `https://github.com/users/USERNAME/projects/N`
- Org project: `https://github.com/orgs/ORGNAME/projects/N`

### Labels Not Applied

If type/priority labels aren't being applied:

1. Ensure labels exist in the repository (create with `gh label create`)
2. Check `canonical_alias` matches the exact label name
3. Verify the labels are in the `default_repo`

