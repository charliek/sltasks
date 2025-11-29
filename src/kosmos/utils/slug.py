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
