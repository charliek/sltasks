"""Service for task CRUD operations."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import frontmatter

from ..models import FileProviderData, GitHubProviderData, Task
from ..repositories import RepositoryProtocol
from ..utils import generate_filename, now_utc

if TYPE_CHECKING:
    from typing import Any

    from .config_service import ConfigService
    from .template_service import TemplateService

logger = logging.getLogger(__name__)


class TaskService:
    """Service for task CRUD operations."""

    def __init__(
        self,
        repository: RepositoryProtocol,
        config_service: ConfigService | None = None,
        template_service: TemplateService | None = None,
    ) -> None:
        self.repository = repository
        self._config_service = config_service
        self._template_service = template_service

    def _get_default_state(self) -> str:
        """Get the default state for new tasks (first column)."""
        if self._config_service:
            config = self._config_service.get_board_config()
            return config.columns[0].id
        return "todo"

    def create_task(
        self,
        title: str,
        state: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        task_type: str | None = None,
    ) -> Task:
        """
        Create a new task with the given title.

        Generates a filename from the title and creates the file.
        If state is not provided, uses first column from config.
        If task_type is provided and a template exists, the template's
        frontmatter provides defaults and body content.
        """
        if state is None:
            state = self._get_default_state()
        elif self._config_service:
            # Resolve alias to canonical ID
            config = self._config_service.get_board_config()
            state = config.resolve_status(state)

        # Resolve type alias to canonical ID
        resolved_type = task_type
        if task_type and self._config_service:
            config = self._config_service.get_board_config()
            resolved_type = config.resolve_type(task_type)

        filename = generate_filename(title)

        # Handle filename collision
        filename = self._unique_filename(filename)

        now = now_utc()

        # Base values (always set)
        final_priority = priority if priority is not None else "medium"
        final_tags = tags if tags is not None else []
        body = ""

        # Apply template if type provided and template service available
        if resolved_type and self._template_service:
            base_fm = {
                "title": title,
                "state": state,
                "created": now.isoformat(),
                "updated": now.isoformat(),
            }
            merged_fm, body = self._template_service.apply_template(resolved_type, base_fm)

            # Use template defaults if not explicitly provided
            if priority is None and "priority" in merged_fm:
                final_priority = merged_fm["priority"]
            if tags is None and "tags" in merged_fm:
                final_tags = merged_fm.get("tags", [])

        task = Task(
            id=filename,
            title=title,
            state=state,
            priority=final_priority,
            tags=final_tags,  # pyrefly: ignore[bad-argument-type]
            type=resolved_type,
            created=now,
            updated=now,
            body=body,
        )

        saved_task = self.repository.save(task)
        logger.info("Task created: %s (state=%s, type=%s)", saved_task.id, state, resolved_type)
        return saved_task

    def update_task(self, task: Task) -> Task:
        """
        Update an existing task.

        Updates the 'updated' timestamp automatically.
        """
        task.updated = now_utc()
        return self.repository.save(task)

    def delete_task(self, task_id: str) -> None:
        """Delete a task by ID."""
        logger.info("Deleting task: %s", task_id)
        self.repository.delete(task_id)

    def rename_task_to_match_title(
        self, task_id: str, task_root: Path | None = None
    ) -> Task | None:
        """
        Rename a task file to match its current title.

        Reads the task, generates a new ID from the title,
        and renames the file if needed. This is a filesystem-specific operation.

        Args:
            task_id: The current task ID (filename)
            task_root: The task root directory (required for filesystem tasks)

        Returns the task with updated ID, or None if task not found.
        """
        task = self.repository.get_by_id(task_id)
        if task is None:
            return None

        # This operation only makes sense for filesystem tasks
        if not isinstance(task.provider_data, FileProviderData):
            return task

        if task_root is None:
            return task

        # Generate filename from current title (use display_title which never returns None)
        new_task_id = generate_filename(task.display_title)

        # If ID would be the same, nothing to do
        if new_task_id == task_id:
            return task

        # Ensure unique ID
        new_task_id = self._unique_filename(new_task_id)

        # Rename the file
        filepath = task_root / task_id
        if filepath.exists():
            new_filepath = task_root / new_task_id
            filepath.rename(new_filepath)

            # Update task with new ID
            old_task_id = task.id
            task.id = new_task_id

            # Update board order to reflect the rename
            self.repository.rename_in_board_order(old_task_id, new_task_id)

        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.repository.get_by_id(task_id)

    def get_all_tasks(self) -> list[Task]:
        """Get all tasks."""
        return self.repository.get_all()

    def open_in_editor(self, task: Task, task_root: Path | None = None) -> bool:
        """
        Open task in the user's editor.

        For filesystem tasks, opens the file directly.
        For GitHub tasks, opens a temp file and pushes changes back.

        Args:
            task: The task to edit
            task_root: The task root directory (required for filesystem tasks)

        Returns True if editor exited successfully and changes were saved.
        """
        logger.debug("Opening task in editor: %s", task.id)
        if isinstance(task.provider_data, GitHubProviderData):
            return self._open_github_issue_in_editor(task)
        elif isinstance(task.provider_data, FileProviderData):
            return self._open_file_in_editor(task, task_root)
        else:
            logger.debug("Unknown provider type, cannot open in editor")
            return False

    def _open_file_in_editor(self, task: Task, task_root: Path | None) -> bool:
        """Open a filesystem task in the editor."""
        if task_root is None:
            return False

        filepath = task_root / task.id
        return self._run_editor(filepath)

    def _open_github_issue_in_editor(self, task: Task) -> bool:
        """Open a GitHub issue in a temp file, then push changes back.

        Creates a temp markdown file with frontmatter containing the title
        and body. After editing, parses changes and updates via API.
        """
        if not isinstance(task.provider_data, GitHubProviderData):
            return False

        logger.debug("Opening GitHub issue #%d in editor", task.provider_data.issue_number)

        # Create temp file with task content
        content = self._format_github_task_for_editing(task)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".md",
            delete=False,
            prefix=f"github-issue-{task.provider_data.issue_number}-",
        ) as f:
            f.write(content)
            temp_path = Path(f.name)

        original_content = content

        try:
            # Open in editor
            if not self._run_editor(temp_path):
                logger.debug("Editor returned non-zero exit code")
                return False

            # Read back edited content
            with temp_path.open() as f:
                edited_content = f.read()

            # Check for changes
            if edited_content == original_content:
                logger.debug("No changes detected after editing")
                return True  # No changes, but editor ran successfully

            # Parse the edited content
            parsed = self._parse_github_task_from_editing(edited_content)

            # Resolve aliases to canonical IDs using board config
            if self._config_service:
                board_config = self._config_service.get_board_config()
                if "priority" in parsed:
                    parsed["priority"] = board_config.resolve_priority(parsed["priority"])
                if parsed.get("type"):
                    parsed["type"] = board_config.resolve_type(parsed["type"])

            # Apply changes to task
            task.title = parsed.get("title", task.title)
            task.body = parsed.get("body", task.body)
            if "priority" in parsed:
                task.priority = parsed["priority"]
            if "type" in parsed:
                task.type = parsed["type"]
            if "tags" in parsed:
                task.tags = parsed["tags"]

            # Save will handle all mutations via repository
            self.repository.save(task)

            logger.info("GitHub issue #%d updated after editing", task.provider_data.issue_number)
            return True

        finally:
            # Clean up temp file
            temp_path.unlink(missing_ok=True)

    def _format_github_task_for_editing(self, task: Task) -> str:
        """Format a GitHub task for editing with YAML frontmatter.

        Includes:
        - Editable fields: title, priority, type, tags (with valid options comments)
        - Read-only fields (commented): state, issue reference, created, updated
        - Body after frontmatter
        """
        # Calculate column width for right-aligned comments
        # Find the longest value line to align comments
        priority_line = f"priority: {task.priority}"
        type_line = f"type: {task.type or ''}"
        tags_line = "tags:"

        # Get comments for each field
        priority_comment = self._get_valid_options_comment("priority")
        type_comment = self._get_valid_options_comment("type")
        tags_comment = self._get_valid_options_comment("tags")

        # Calculate padding to align comments (find max line length)
        lines_with_comments = [
            (priority_line, priority_comment),
            (type_line, type_comment),
            (tags_line, tags_comment),
        ]
        max_line_len = max(len(line) for line, comment in lines_with_comments if comment)
        # Add some padding for readability
        comment_col = max(max_line_len + 2, 25)

        def pad_comment(line: str, comment: str) -> str:
            """Pad a line so the comment aligns to comment_col."""
            if not comment:
                return line
            padding = " " * max(1, comment_col - len(line))
            return f"{line}{padding}{comment}"

        lines = ["---"]

        # Title (no comment needed)
        lines.append(f"title: {task.title or ''}")

        # Priority with aligned comment
        lines.append(pad_comment(priority_line, priority_comment))

        # Type with aligned comment
        lines.append(pad_comment(type_line, type_comment))

        # Tags with aligned comment
        if task.tags:
            lines.append(pad_comment(tags_line, tags_comment))
            for tag in task.tags:
                lines.append(f"  - {tag}")
        else:
            lines.append(pad_comment("tags: []", tags_comment))

        # Empty line before read-only section
        lines.append("")

        # Read-only fields as comments
        lines.append("# Read-only fields (changes will be ignored):")
        lines.append(f"# state: {task.state}")

        if isinstance(task.provider_data, GitHubProviderData):
            issue_ref = f"{task.provider_data.repository}#{task.provider_data.issue_number}"
            lines.append(f"# issue: {issue_ref}")

        if task.created:
            lines.append(f"# created: '{task.created.isoformat()}'")

        if task.updated:
            lines.append(f"# updated: '{task.updated.isoformat()}'")

        lines.append("---")
        lines.append("")
        lines.append(task.body or "")

        return "\n".join(lines)

    def _parse_github_task_from_editing(self, content: str) -> dict[str, Any]:
        """Parse an edited GitHub task file with frontmatter.

        Returns dict with:
        - title: str
        - body: str
        - priority: str (if present)
        - type: str | None (if present)
        - tags: list[str] (if present)

        Read-only fields (state, issue, created, updated) are ignored.
        """
        post = frontmatter.loads(content)

        result: dict[str, Any] = {
            "title": post.get("title", ""),
            "body": post.content,
        }

        # Extract editable fields if present
        if "priority" in post.metadata:
            result["priority"] = post.metadata["priority"]
        if "type" in post.metadata:
            result["type"] = post.metadata["type"] or None
        if "tags" in post.metadata:
            result["tags"] = post.metadata["tags"] or []

        return result

    def _run_editor(self, filepath: Path) -> bool:
        """Run the user's editor on a file."""
        # Try $EDITOR, then common fallbacks
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
        if not editor:
            # Try common editors in order of preference
            for candidate in ["nvim", "vim", "vi", "nano"]:
                if self._command_exists(candidate):
                    editor = candidate
                    break
            else:
                return False

        # Handle editors with arguments (e.g., "zed --wait", "code --wait")
        import shlex

        editor_parts = shlex.split(editor)
        editor_cmd = [*editor_parts, str(filepath.absolute())]

        try:
            result = subprocess.run(
                editor_cmd,
                check=False,
            )
            return result.returncode == 0
        except FileNotFoundError:
            # Editor not found
            return False

    def _command_exists(self, cmd: str) -> bool:
        """Check if a command exists in PATH."""
        import shutil

        return shutil.which(cmd) is not None

    def _unique_filename(self, filename: str) -> str:
        """Ensure filename is unique by appending numbers if needed."""
        base = filename.removesuffix(".md")
        candidate = filename
        counter = 1

        while self.repository.get_by_id(candidate) is not None:
            candidate = f"{base}-{counter}.md"
            counter += 1

        return candidate

    def _get_valid_options_comment(self, field: str, pad_to: int = 0) -> str:
        """Generate a comment showing valid options for a constrained field.

        Args:
            field: The field name ("priority", "type", "tags", "state")
            pad_to: Pad the comment with spaces to align to this column

        Returns:
            Comment string like "  # Valid: low, medium, high" or empty string
        """
        if not self._config_service:
            return ""

        board_config = self._config_service.get_board_config()
        config = self._config_service.get_config()

        options: list[str] = []
        prefix = "Valid"

        if field == "state":
            options = [col.id for col in board_config.columns]
        elif field == "priority":
            options = [p.id for p in board_config.priorities]
        elif field == "type":
            options = [t.id for t in board_config.types]
        elif field == "tags":
            # Use featured_labels from GitHub config
            prefix = "Options"
            if config.github and config.github.featured_labels:
                options = config.github.featured_labels

        if not options:
            return ""

        comment = f"# {prefix}: {', '.join(options)}"
        if pad_to > 0:
            return f"  {comment}"
        return f"  {comment}"
