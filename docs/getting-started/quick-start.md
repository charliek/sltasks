# Quick Start

## Choose Your Provider

sltasks supports two storage backends:

- **File Provider** (default) - Store tasks as local markdown files. Great for personal projects and git-tracked task management.
- **GitHub Provider** - Sync with GitHub Projects V2. Ideal for team projects using GitHub Issues.

See [Providers](../providers/index.md) for a detailed comparison.

## File Provider Setup

Bootstrap a new sltasks project with local file storage:

```bash
sltasks --generate
```

This creates a `sltasks.yml` file in your current directory with the default board configuration.

## Default configuration

The generated `sltasks.yml` contains:

```yaml
columns:
  - id: todo
    title: To Do
  - id: in_progress
    title: In Progress
  - id: done
    title: Done
  - id: archived
    title: Archived
```

See [Configuration](../user-guide/configuration.md) for customization options.

## Directory structure

After launching sltasks and creating tasks, your project will have:

```
project-root/
├── sltasks.yml              # Board configuration
└── .tasks/
    ├── tasks.yaml           # System-managed task ordering
    ├── my-first-task.md     # Task files
    └── another-task.md
```

- `sltasks.yml` - Your board configuration (columns, settings)
- `.tasks/` - Directory containing all task files
- `.tasks/tasks.yaml` - Automatically managed file tracking task order in columns
- `.tasks/*.md` - Individual task files with YAML frontmatter

## Launch the board

Start the terminal interface:

```bash
uv run sltasks
```

You'll see a kanban board with your configured columns.

## GitHub Provider Setup

Want to use GitHub Projects instead of local files? Run the interactive setup:

```bash
sltasks --github-setup https://github.com/users/USERNAME/projects/1
```

This auto-detects your project's columns and generates the configuration.

!!! note "First-time setup"
    You'll need to set up authentication and create labels in your repository. See the [GitHub Provider Guide](../providers/github-provider.md) for complete setup instructions.

## Next steps

See the [Navigation](../user-guide/navigation.md) guide to learn how to navigate, create, and manage tasks.
