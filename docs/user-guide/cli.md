# CLI

## Usage

```
$ sltasks --help
usage: sltasks [-h] [--task-root TASK_ROOT] [--generate] [--github-setup [URL]]
               [-v] [--log-file LOG_FILE] [--version]

Terminal-based Kanban TUI for markdown task management

options:
  -h, --help            show this help message and exit
  --task-root TASK_ROOT
                        Path to project root containing sltasks.yml (default: current directory)
  --generate            Generate default sltasks.yml config in task directory and exit
  --github-setup [URL]  Interactive setup for GitHub Projects integration
  -v, --verbose         Increase logging verbosity (-v for INFO, -vv for DEBUG)
  --log-file LOG_FILE   Path to write logs to file
  --version             show program's version number and exit
```

## Options

### --task-root

Specify a custom project root directory:

```bash
sltasks --task-root /path/to/project
```

By default, sltasks uses the current directory.

### --generate

Generate the default `sltasks.yml` configuration file:

```bash
sltasks --generate
```

This creates a configuration file with the default columns (To Do, In Progress, Done, Archived).

### --github-setup

Interactive setup for GitHub Projects integration:

```bash
# Interactive mode - prompts for project URL
sltasks --github-setup

# Direct mode - provide project URL as argument
sltasks --github-setup https://github.com/users/USERNAME/projects/1
sltasks --github-setup https://github.com/orgs/ORGNAME/projects/1
```

This command:

1. Authenticates with GitHub (via `GITHUB_TOKEN` env var or `gh` CLI)
2. Fetches project metadata and detects Status columns
3. Prompts for priority field selection (if detected)
4. Prompts for default status and repository
5. Generates and previews the configuration
6. Writes `sltasks.yml` (with backup if exists)

See the [GitHub Provider Guide](../providers/github-provider.md) for details.

### -v, --verbose

Increase logging verbosity:

```bash
sltasks -v      # INFO level logging
sltasks -vv     # DEBUG level logging
```

### --log-file

Write logs to a file:

```bash
sltasks --log-file /path/to/sltasks.log
sltasks -vv --log-file debug.log  # Combine with verbose
```

### --version

Display the current version:

```bash
sltasks --version
```

## Subcommands

### sltasks sync

Sync issues from GitHub to local markdown files. Requires GitHub sync to be enabled in your configuration.

```bash
sltasks sync              # Sync matching issues
sltasks sync --dry-run    # Preview what would sync
sltasks sync --force      # Overwrite local changes
```

| Flag | Description |
|------|-------------|
| `--dry-run` | Show what would be synced without writing files |
| `--force` | Overwrite local changes (resolve conflicts to GitHub version) |

Requires `github.sync.enabled: true` in configuration. See the [GitHub Provider Guide](../providers/github-provider.md#filesystem-sync) for setup.

### sltasks push

Push local tasks to GitHub as new issues:

```bash
sltasks push                    # Push all local-only tasks
sltasks push file1.md file2.md  # Push specific files
sltasks push --dry-run          # Preview without creating issues
sltasks push -y                 # Skip confirmation prompt
sltasks push --delete           # Delete files after pushing
sltasks push --archive          # Archive files after pushing
```

| Flag | Description |
|------|-------------|
| `[files...]` | Specific files to push (default: all local-only tasks) |
| `--dry-run` | Show what would be pushed without creating issues |
| `-y, --yes` | Skip confirmation prompt |
| `--delete` | Delete local files after successful push |
| `--archive` | Archive local files after push (set `archived: true`) |

After pushing, you'll be prompted to choose what to do with the local files (keep, delete, or archive) unless you specify `--delete` or `--archive`.
