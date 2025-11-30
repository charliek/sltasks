# Navigation

## Keyboard shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `↑` / `k` | Move selection up |
| `↓` / `j` | Move selection down |
| `←` / `h` | Move to previous column |
| `→` / `l` | Move to next column |

### Task operations

| Key | Action |
|-----|--------|
| `Enter` | Open task in `$EDITOR` |
| `n` | Create new task |
| `e` | Edit selected task |
| `a` | Archive selected task |
| `d` | Delete selected task |
| `p` | Preview task content |

### Moving tasks

| Key | Action |
|-----|--------|
| `H` / `Shift+←` | Move task to previous column |
| `L` / `Shift+→` | Move task to next column |
| `K` / `Shift+↑` | Move task up within column |
| `J` / `Shift+↓` | Move task down within column |

### Application

| Key | Action |
|-----|--------|
| `/` | Enter filter mode |
| `?` | Show help screen |
| `q` | Quit |

## Filtering

Press `/` to filter tasks:

```
tag:bug           # Tasks with "bug" tag
priority:high     # High priority tasks
state:todo        # Tasks in "to do" state
login             # Text search
-tag:wontfix      # Exclude tasks with tag
```

Combine filters with spaces (AND logic):

```
tag:bug priority:high state:todo
```

Press `Escape` to clear the filter.
