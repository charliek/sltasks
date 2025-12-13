# GitHub Projects Integration (Beta)

sltasks now supports viewing tasks directly from GitHub Projects V2. This feature is currently in **Beta** and is **Read-Only**.

## Setup

### 1. Requirements

You will need a GitHub Personal Access Token (PAT) to access your projects.

1.  Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens).
2.  Generate a new **Classic Token** (recommended for simplicity) or a **Fine-grained Token**.
3.  Select the following scopes:
    -   `read:project` (Required to fetch project items).
        -   *Note: For future write support (Phase 2), you will need `project` scope.*
    -   `repo` (Required to read issue titles and body content).
4.  Copy the generated token.

You also need the full URL to your GitHub Project V2 board (e.g., `https://github.com/users/yourusername/projects/1`).

### 2. Configuration

Edit your `sltasks.yml` configuration file to enable the GitHub backend.

**Note on Feature Support:**
Unlike the default `filesystem` backend, the GitHub backend is currently **Read-Only**.
-   ✅ **Supported**: Viewing tasks, filtering, refreshing.
-   ❌ **Not Supported (yet)**: Creating tasks, editing tasks, moving tasks between columns, archiving, deleting.

```yaml
version: 1
backend: github  # Switch from 'filesystem' to 'github'

github:
  # The URL to your project (view URLs are supported)
  project_url: "https://github.com/users/yourusername/projects/1"

  # Optional: Filter settings
  include_closed: false  # Show closed issues? (Default: false)
  include_prs: true      # Show Pull Requests? (Default: true)

# ... rest of your board configuration ...
```

### 3. Authentication

Set the `GITHUB_TOKEN` environment variable before running sltasks. This is secure and prevents hardcoding credentials in your config file.

```bash
export GITHUB_TOKEN=ghp_your_token_here
sltasks
```

## Status Mapping

GitHub Projects allow custom statuses (e.g., "Backlog", "In Review"). You must map these to your `sltasks` columns using the `status_alias` feature in `sltasks.yml`.

**How it works:**
1.  sltasks fetches an issue from GitHub and sees its status is "In Review".
2.  It looks at your `sltasks.yml` columns.
3.  If a column has `id: in_review`, it matches.
4.  If a column has `status_alias: ["in review"]`, it matches.
5.  If no match is found, the task may not appear on the board.

**Example Configuration:**

```yaml
board:
  columns:
    - id: todo
      title: "To Do"
      status_alias:
        - "new"
        - "backlog"       # Maps GitHub 'Backlog' status to this column
        - "no status"     # Maps items with no status
    - id: in_progress
      title: "In Progress"
      status_alias:
        - "in review"     # Maps GitHub 'In Review' status here
    - id: done
      title: "Done"
```

## Troubleshooting

-   **404 Errors**: Ensure your token has the correct scopes and you have access to the project.
-   **Missing Tasks**: Check if the task status in GitHub matches a column ID or alias in `sltasks.yml`. Use the example above to ensure all your GitHub statuses are mapped to a column.
