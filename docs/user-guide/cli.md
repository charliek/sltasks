# CLI

## Usage

```
$ sltasks --help
usage: sltasks [-h] [--task-root TASK_ROOT] [--generate] [--version]

Terminal-based Kanban TUI for markdown task management

options:
  -h, --help            show this help message and exit
  --task-root TASK_ROOT
                        Path to project root containing sltasks.yml (default: current directory)
  --generate            Generate default sltasks.yml config in task directory and exit
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

### --version

Display the current version:

```bash
sltasks --version
```
