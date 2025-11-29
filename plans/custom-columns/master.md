---
state: done
priority: medium
updated: '2025-11-29T19:29:52.448069+00:00'
---

# Custom Board Columns - Implementation Plans

## Feature Overview

This feature allows users to define custom kanban board columns via a `.tasks/sltasks.yml` configuration file, replacing the hardcoded 3-column layout (To Do, In Progress, Done) with a flexible 2-6 column structure supporting custom status values.

### Core Principles

- **User-defined columns** – Users specify column names and status IDs in `sltasks.yml`
- **Backwards compatible** – Existing task files continue to work; missing config falls back to default 3-column layout
- **Prepares for future** – `sltasks.yml` structure allows adding backend configs (Jira, GitHub) later
- **Archive remains special** – The `archived` status is always available but never shown as a column

## Configuration Schema

```yaml
# .tasks/sltasks.yml
version: 1

board:
  columns:
    - id: backlog
      title: "Backlog"
    - id: todo
      title: "To Do"
    - id: in_progress
      title: "In Progress"
    - id: review
      title: "Code Review"
    - id: done
      title: "Done"
```

### Default Configuration (when no sltasks.yml exists)

```yaml
version: 1
board:
  columns:
    - id: todo
      title: "To Do"
    - id: in_progress
      title: "In Progress"
    - id: done
      title: "Done"
```

## Architecture Changes

### Key Architectural Decision

**Replace `TaskState` enum with string-based statuses**

Python enums cannot be dynamically extended, so custom status values require switching from:
```python
state: TaskState = TaskState.TODO
```
to:
```python
state: str = "todo"
```

Validation moves from compile-time (enum) to runtime (config-based).

### Layer Changes

```
┌─────────────────────────────────────────────────────────────────┐
│                        TUI Layer (Textual)                       │
│  BoardScreen now generates columns dynamically from config       │
└─────────────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                       Service Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐          │
│  │ TaskService  │  │ BoardService │  │ ConfigService │ ◄─ NEW   │
│  └──────────────┘  └──────┬───────┘  └───────────────┘          │
│                           │ uses config for column order         │
└───────────────────────────┼─────────────────────────────────────┘
          │                 │
┌─────────▼─────────────────▼─────────────────────────────────────┐
│                     Repository Layer                             │
│  FilesystemRepository handles dynamic column ordering            │
└─────────────────────────────────────────────────────────────────┘
          │
┌─────────▼───────────────────────────────────────────────────────┐
│                       Storage Layer                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐     │
│  │  .tasks/*.md    │  │   tasks.yaml    │  │ sltasks.yml  │◄NEW │
│  │  (task files)   │  │   (ordering)    │  │   (config)   │     │
│  └─────────────────┘  └─────────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Phases

| Phase | Description | Risk | Status |
|-------|-------------|------|--------|
| 1 | [Config Model & Service](./phase-1-config-model.md) | Low | **Complete** |
| 2 | [Task State Migration](./phase-2-task-state-migration.md) | Medium | **Complete** |
| 3 | [Board Model Refactor](./phase-3-board-model.md) | Medium | **Complete** |
| 4 | [Service Layer Updates](./phase-4-service-layer.md) | Medium | **Complete** |
| 5 | [Dynamic UI Generation](./phase-5-dynamic-ui.md) | High | **Complete** |
| 6 | [Polish & Edge Cases](./phase-6-polish.md) | Low | **Complete** |
| 7 | [Generate Config Command](./phase-7-generate-command.md) | Low | **Complete** |

### Phase Summary

- **Phase 1**: Create `SltasksConfig`, `BoardConfig`, `ColumnConfig` models and `ConfigService`. No breaking changes.
- **Phase 2**: Change `Task.state` from `TaskState` enum to `str`. Backwards compatible.
- **Phase 3**: Refactor `Board` to use `dict[str, list[Task]]`. Update `BoardOrder` and repository.
- **Phase 4**: Update `BoardService` navigation and `FilterService` for string states.
- **Phase 5**: Generate UI columns dynamically from config. Most user-visible change.
- **Phase 6**: Error handling, edge cases, documentation, comprehensive tests.
- **Phase 7**: Add `--generate` CLI command to create default `sltasks.yml` config file.

## Files Overview

### New Files
| File | Purpose |
|------|---------|
| `models/sltasks_config.py` | `SltasksConfig`, `BoardConfig`, `ColumnConfig` models |
| `services/config_service.py` | Load/cache `sltasks.yml` configuration |
| `cli/__init__.py` | CLI module exports |
| `cli/generate.py` | `--generate` command implementation |
| `cli/output.py` | Colorful terminal output helpers |

### Modified Files
| File | Phase | Changes |
|------|-------|---------|
| `models/task.py` | 2 | `state: TaskState` → `state: str` |
| `models/board.py` | 3, 6 | Fixed columns → `dict[str, list[Task]]`, remove compat properties |
| `models/enums.py` | 6 | Remove `TaskState` enum |
| `services/board_service.py` | 4 | Use config for column navigation |
| `services/filter_service.py` | 4 | String-based state filtering |
| `repositories/filesystem.py` | 3 | Dynamic column ordering |
| `ui/screens/board.py` | 5 | Generate columns from config |
| `ui/widgets/column.py` | 5 | Accept string state |
| `app.py` | 4, 5 | Wire ConfigService to all services |
| `__main__.py` | 7 | Add `--generate` argument |

## Constraints

- **Minimum 2 columns, maximum 6 columns**
- **Column IDs must be unique**
- **`archived` is reserved** – cannot be used as a column ID (always available as hidden status)
- **1:1 status mapping** – each status maps to exactly one column
- **No backwards compatibility code** – this is an early project, remove deprecated code in Phase 6 rather than maintaining it

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking existing task files | String states are backwards compatible with enum values |
| Invalid sltasks.yml crashes app | Try/catch with fallback to default config |
| Unknown status in task file | Silently place in first column |
| Column ID = "archived" | Validator rejects reserved IDs |

## Future Enhancements (Not in Scope)

- Column colors
- WIP limits per column
- Column descriptions/tooltips
- Warning notification for invalid task states
- Backend configuration (Jira, GitHub Projects)