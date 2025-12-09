"""Service for parsing and applying filters to tasks."""

import contextlib
import re
from dataclasses import dataclass, field

from ..models import Priority, Task
from ..models.task import STATE_ARCHIVED


@dataclass
class Filter:
    """Represents a parsed filter expression."""

    text: str | None = None  # Free text search
    tags: list[str] = field(default_factory=list)  # tag:value
    exclude_tags: list[str] = field(default_factory=list)  # -tag:value
    states: list[str] = field(default_factory=list)  # state:value (any string)
    priorities: list[Priority] = field(default_factory=list)  # priority:value
    types: list[str] = field(default_factory=list)  # type:value
    show_archived: bool = False  # archived:true


class FilterService:
    """Service for parsing and applying filters to tasks."""

    # Pattern for key:value tokens
    TOKEN_PATTERN = re.compile(r"(-?)(?:(tag|state|priority|archived|type):)?(\S+)")

    def parse(self, expression: str) -> Filter:
        """
        Parse a filter expression string.

        Syntax:
        - Free text: matches title or body
        - tag:value: filter by tag
        - -tag:value: exclude tag
        - state:todo/in_progress/done/archived
        - priority:low/medium/high/critical
        - type:feature/bug/task (or custom type)
        - archived:true - show archived tasks

        Multiple conditions are ANDed together.
        """
        f = Filter()
        text_parts: list[str] = []

        for match in self.TOKEN_PATTERN.finditer(expression):
            negated = match.group(1) == "-"
            key = match.group(2)
            value = match.group(3).lower()

            if key is None:
                # Free text (might be negated, but we ignore that for text)
                if not negated:
                    text_parts.append(match.group(3))

            elif key == "tag":
                if negated:
                    f.exclude_tags.append(value)
                else:
                    f.tags.append(value)

            elif key == "state":
                # Accept any state string (no validation - custom states allowed)
                f.states.append(value)

            elif key == "priority":
                with contextlib.suppress(ValueError):
                    f.priorities.append(Priority(value))

            elif key == "archived":
                f.show_archived = value == "true"

            elif key == "type":
                f.types.append(value)

        if text_parts:
            f.text = " ".join(text_parts)

        return f

    def apply(self, tasks: list[Task], filter_: Filter) -> list[Task]:
        """Apply filter to a list of tasks."""
        result: list[Task] = []

        for task in tasks:
            if self._matches(task, filter_):
                result.append(task)

        return result

    def _matches(self, task: Task, f: Filter) -> bool:
        """Check if a task matches the filter."""
        # Hide archived by default unless explicitly requested
        if task.state == STATE_ARCHIVED and not f.show_archived:
            return False

        # Text search (case-insensitive)
        if f.text:
            search_text = f.text.lower()
            title = task.display_title.lower()
            body = task.body.lower()
            if search_text not in title and search_text not in body:
                return False

        # Tag inclusion (any match)
        if f.tags:
            task_tags = [t.lower() for t in task.tags]
            if not any(tag in task_tags for tag in f.tags):
                return False

        # Tag exclusion (no matches)
        if f.exclude_tags:
            task_tags = [t.lower() for t in task.tags]
            if any(tag in task_tags for tag in f.exclude_tags):
                return False

        # State filter (any match)
        if f.states and task.state not in f.states:
            return False

        # Priority filter (any match)
        if f.priorities and task.priority not in f.priorities:
            return False

        # Type filter (any match)
        if f.types:
            task_type = (task.type or "").lower()
            if task_type not in f.types:
                return False

        return True
