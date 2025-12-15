# Cache Mutation Investigation Prompt

Investigate the cache mutation pattern in sltasks repositories and services. This has caused multiple bugs where:
1. A cached object is returned by reference
2. The caller mutates the object
3. Later code tries to compare "old" vs "new" state but both point to the same mutated object

---

## Known Bugs (Fixed)

### Bug 1: Tags not saving when editing GitHub issues
**Root cause**: `get_by_id()` returned the cached Task object by reference. When TaskService mutated it and called `save()`, `_update_issue()` did `old_task = self._tasks.get(task.id)` which returned the same mutated object.

**Fix**: Made `get_by_id()` return `task.model_copy(deep=True)`.

### Bug 2: Tags not saving via UI edit flow
**Root cause**: Even after fixing `get_by_id()`, tasks flowed to the UI through `get_all()` → `Board.from_tasks()` → `Column._tasks`. The `_sorted_tasks()` method returned `list(self._tasks.values())` which are the same object references as the cache.

**Data flow**:
```
get_all() → _sorted_tasks() → list(self._tasks.values()) [SAME REFS]
    → Board.from_tasks() [SAME REFS]
    → column.set_tasks() → column._tasks [SAME REFS]
    → column.get_task() → returns task [SAME REF as cache]
    → user edits task [MUTATES cache indirectly]
    → save() → _update_issue() compares old_task vs task [BOTH MUTATED]
```

**Fix**: Made `_sorted_tasks()` return `[task.model_copy(deep=True) for task in ...]`.

---

## Investigation Checklist

### 1. Find all cache patterns

Search for instance variables that store objects:
```bash
# Search for cache-like instance variables
grep -rn "self\._tasks\s*=" src/sltasks/
grep -rn "self\._cache" src/sltasks/
grep -rn "self\._board_order" src/sltasks/
```

**Known caches in GitHubProjectsRepository**:
- `self._tasks: dict[str, Task]` - Main task cache
- `self._board_order: BoardOrder | None` - Board ordering cache
- `self._repo_labels: dict[str, dict[str, str]]` - Label ID cache

**Known caches in FilesystemRepository**:
- `self._tasks: dict[str, Task]` - Task cache (check if same pattern)
- `self._board_order: BoardOrder | None` - Board ordering

### 2. Find all methods that return cached objects

For each repository, check these methods:
- `get_by_id(task_id)` - Should return copy
- `get_all()` - Should return copies
- `_sorted_tasks()` - Internal, should return copies
- `get_board_order()` - Check if mutations affect cache

**Questions to answer**:
- Does `FilesystemRepository.get_by_id()` return a copy?
- Does `FilesystemRepository.get_all()` return copies?
- Are there other repository implementations?

### 3. Find all mutation sites

Search for places where Task objects are mutated:
```bash
# Direct attribute assignment
grep -rn "task\.\w\+\s*=" src/sltasks/services/
grep -rn "task\.\w\+\s*=" src/sltasks/app.py

# List mutations (append, extend, etc.)
grep -rn "task\.tags\." src/sltasks/
```

**Known mutation sites in TaskService**:
- `_open_github_issue_in_editor()` - Mutates task after parsing edited content:
  ```python
  task.title = parsed.get("title", task.title)
  task.body = parsed.get("body", task.body)
  task.priority = parsed["priority"]
  task.type = parsed["type"]
  task.tags = parsed["tags"]
  ```

- `create_task()` - Creates new Task (not a mutation issue)
- `move_task()` - Check if it mutates or creates new

**Known mutation sites in BoardService**:
- `move_task()` - Does it mutate task.state in place?
- `reorder_task()` - Does it mutate anything?

### 4. Identify affected flows

#### Edit flow (KNOWN AFFECTED)
```
User presses 'e' → app.action_edit_task()
    → screen.get_current_task() [returns ref from column._tasks]
    → task_service.open_in_editor(task)
    → _open_github_issue_in_editor(task)
        → format task to temp file
        → user edits
        → parse edited content
        → MUTATE task in place  ← BUG: mutates cached object
        → repository.save(task)
            → _update_issue(task)
                → old_task = self._tasks.get(task.id)  ← SAME OBJECT
                → _compute_label_changes(task, old_task)  ← NO DIFF DETECTED
```

#### Move flow (CHECK THIS)
```
User presses 'H'/'L' → app.action_move_task_left/right()
    → board_service.move_task(task_id, new_state)
    → Does this mutate task.state in place?
    → Does save() compare old vs new state?
```

#### Reorder flow (CHECK THIS)
```
User presses 'K'/'J' → app.action_reorder_task_up/down()
    → board_service.reorder_task(...)
    → Does this mutate anything on the task?
```

#### Create flow (PROBABLY OK)
```
User presses 'n' → app.action_new_task()
    → task_service.create_task(...)
    → Creates new Task object, no mutation of cached objects
```

### 5. Evaluate solutions

#### Option A: Copy-on-read (CURRENT APPROACH)
Always return deep copies from repository methods.

**Pros**:
- Simple mental model: "repository returns independent copies"
- Callers can mutate freely without worrying about cache
- Already implemented for GitHub repository

**Cons**:
- Performance: Deep copying on every `get_all()` could be expensive
- Memory: Multiple copies of same task in memory
- Inconsistency: Need to apply to ALL repositories

**Implementation**:
```python
def get_by_id(self, task_id: str) -> Task | None:
    task = self._tasks.get(task_id)
    if task:
        return task.model_copy(deep=True)
    return None

def _sorted_tasks(self) -> list[Task]:
    return [task.model_copy(deep=True) for task in self._tasks.values()]
```

#### Option B: Immutable Tasks (Pydantic frozen)
Make Task model immutable, require creating new instances for changes.

**Pros**:
- Type-safe: Mutations cause errors at runtime
- Clear API: Can't accidentally mutate
- No defensive copying needed

**Cons**:
- Major refactor: All mutation sites need to change
- Verbose: `task = task.model_copy(update={"title": "new"})` instead of `task.title = "new"`
- Nested mutations tricky: `task.tags.append()` would fail

**Implementation**:
```python
class Task(BaseModel):
    model_config = ConfigDict(frozen=True)

# Mutation becomes:
task = task.model_copy(update={"tags": task.tags + ["new-tag"]})
```

#### Option C: Explicit old_state parameter
Pass old state explicitly to methods that need comparison.

**Pros**:
- No defensive copying overhead
- Clear at call site that comparison will happen
- Can selectively apply where needed

**Cons**:
- API change for save methods
- Caller must remember to capture old state
- Easy to forget

**Implementation**:
```python
def save(self, task: Task, old_task: Task | None = None) -> Task:
    if old_task:
        labels_to_add, labels_to_remove = self._compute_label_changes(task, old_task)
```

#### Option D: Copy-on-write in cache
When storing in cache, store a copy. Never mutate cache directly.

**Pros**:
- Cache is always pristine
- Can return references safely

**Cons**:
- Still need to copy on write
- Doesn't prevent mutation bugs, just moves them

### 6. Consistency check: FilesystemRepository

**IMPORTANT**: Check if FilesystemRepository has the same pattern:
```bash
# Check get_by_id
grep -A 10 "def get_by_id" src/sltasks/repositories/filesystem.py

# Check get_all
grep -A 10 "def get_all" src/sltasks/repositories/filesystem.py
```

If FilesystemRepository returns references, it could have the same bug (though the edit flow is different for file-based tasks).

---

## Test Coverage Required

### For copy-on-read pattern:

```python
class TestRepositoryReturnsCopies:
    """All repositories should return copies to prevent cache mutation."""

    def test_get_by_id_returns_copy_not_reference(self, repo):
        """get_by_id returns a deep copy."""
        # Setup cache
        repo._tasks = {"id": original_task}

        # Get and mutate
        task = repo.get_by_id("id")
        task.title = "Modified"
        task.tags.append("new")

        # Cache unchanged
        assert repo._tasks["id"].title == "Original"
        assert "new" not in repo._tasks["id"].tags

    def test_get_all_returns_copies_not_references(self, repo):
        """get_all returns deep copies."""
        # Same pattern as above but via get_all()

    def test_mutation_flow_detects_changes(self, repo):
        """Full flow: get task, mutate, save - changes detected."""
        # Simulate the edit flow
        task = repo.get_by_id("id")  # or via get_all flow
        task.tags = ["new-tag"]

        # Compare with cache
        old_task = repo._tasks.get("id")
        labels_to_add, labels_to_remove = repo._compute_label_changes(task, old_task)

        assert "new-tag" in labels_to_add
        assert "old-tag" in labels_to_remove
```

---

## Recommended Refactoring Plan

### Phase 1: Audit (DO THIS FIRST)
1. Run the grep commands above to find all cache patterns
2. Document which methods return references vs copies
3. Identify all mutation sites
4. Map the data flow for each user action

### Phase 2: Consistency
1. Ensure FilesystemRepository follows same pattern as GitHubProjectsRepository
2. Add copy-on-read to any methods that don't have it
3. Add tests for all repositories

### Phase 3: Consider immutable pattern (OPTIONAL)
If copy-on-read proves too expensive or error-prone:
1. Prototype frozen Task model
2. Update all mutation sites
3. Measure performance impact

---

## Key Files to Review

- `src/sltasks/repositories/github_projects.py` - GitHub repository (FIXED)
- `src/sltasks/repositories/filesystem.py` - File repository (CHECK)
- `src/sltasks/repositories/protocol.py` - Repository interface
- `src/sltasks/services/task_service.py` - Task mutation in edit flow
- `src/sltasks/services/board_service.py` - Task mutation in move/reorder
- `src/sltasks/ui/screens/board.py` - How tasks flow to UI
- `src/sltasks/ui/widgets/column.py` - How tasks are stored in UI
- `src/sltasks/app.py` - Action handlers that trigger mutations
