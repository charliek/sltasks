# GitHub Projects Integration (Beta)

sltasks now supports viewing tasks directly from GitHub Projects V2. This feature is currently in **Beta** and is **Read-Only**.

## Setup

### 1. Requirements

-   A GitHub Personal Access Token (classic or fine-grained) with the following scopes:
    -   `read:project` (or `project`)
    -   `repo`
-   The URL to your GitHub Project V2 board.

### 2. Configuration

Edit your `sltasks.yml` configuration file to enable the GitHub backend:

```yaml
version: 1
backend: github  # Switch from 'filesystem' to 'github'

github:
  # The URL to your project (view URLs are supported)
  project_url: "https://github.com/users/yourusername/projects/1"

  # Optional: Filter settings
  include_closed: false
  include_prs: true

# ... rest of your board configuration ...
```

### 3. Authentication

Set the `GITHUB_TOKEN` environment variable before running sltasks:

```bash
export GITHUB_TOKEN=ghp_your_token_here
sltasks
```

## Features

-   **View Tasks**: All issues and pull requests from your project board will appear on the sltasks board.
-   **Status Mapping**: GitHub Statuses are mapped to sltasks columns based on the `status_alias` configuration in `sltasks.yml`.
    -   Example: If your GitHub column is "Backlog" and your sltasks column is "To Do", add "backlog" to the `status_alias` of the "To Do" column.
-   **Read-Only**: In this phase, moving tasks, creating tasks, or editing content is disabled to prevent accidental changes.

## Troubleshooting

-   **404 Errors**: Ensure your token has the correct scopes and you have access to the project.
-   **Missing Tasks**: Check if the task status in GitHub matches a column ID or alias in `sltasks.yml`. Unmapped tasks may not appear.
