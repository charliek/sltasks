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

See [Configuration - GitHub Provider](configuration.md#github-provider) for details.

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
