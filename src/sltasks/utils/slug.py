"""Utilities for generating filesystem-safe slugs."""

import re
import unicodedata


def slugify(text: str) -> str:
    """
    Convert text to a filesystem-safe slug.

    Example: "Fix Login Bug!" -> "fix-login-bug"
    """
    # Normalize unicode characters
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    text = text.lower()

    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)

    # Remove any character that isn't alphanumeric or hyphen
    text = re.sub(r"[^a-z0-9\-]", "", text)

    # Remove leading/trailing hyphens and collapse multiple hyphens
    text = re.sub(r"-+", "-", text).strip("-")

    return text


def generate_filename(title: str) -> str:
    """Generate a .md filename from a title."""
    slug = slugify(title)
    if not slug:
        slug = "untitled"
    return f"{slug}.md"


def slugify_column_id(name: str) -> str:
    """
    Convert a GitHub Status option name to a valid sltasks column ID.

    Column IDs must be lowercase alphanumeric with underscores, and must
    start with a letter. This function converts GitHub Status names like
    "In Progress" or "In review" to valid IDs like "in_progress" or "in_review".

    Rules:
    - Lowercase
    - Spaces/hyphens become underscores
    - Remove non-alphanumeric characters (except underscores)
    - Must start with a letter (prefix with 'col_' if not)

    Examples:
        "In progress" -> "in_progress"
        "Ready" -> "ready"
        "In Review" -> "in_review"
        "Done ✓" -> "done"
        "123 Numbers" -> "col_123_numbers"
    """
    # Normalize unicode characters
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")

    # Convert to lowercase
    name = name.lower()

    # Replace spaces and hyphens with underscores
    name = re.sub(r"[\s\-]+", "_", name)

    # Remove any character that isn't alphanumeric or underscore
    name = re.sub(r"[^a-z0-9_]", "", name)

    # Remove leading/trailing underscores and collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")

    # Must start with a letter - prefix with 'col_' if it starts with a digit
    if name and name[0].isdigit():
        name = f"col_{name}"

    # Handle empty result
    if not name:
        name = "unknown"

    return name
