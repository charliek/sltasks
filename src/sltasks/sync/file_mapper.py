"""Utilities for mapping between GitHub issues and local filenames.

Synced files use the naming convention:
    {owner}-{repo}#{issue_number}-{slug}.md

Examples:
    acme-project#123-fix-login-bug.md
    owner-repo#456-add-dark-mode.md

Local-only files use simple slugified names:
    fix-login-bug.md
    add-dark-mode.md
"""

import re
from dataclasses import dataclass

from ..utils.slug import slugify

# Regex pattern for synced filenames: owner-repo#123-slug.md
# Note: owner and repo can contain hyphens, so we use a non-greedy match
# and look for the # separator
SYNCED_FILENAME_PATTERN = re.compile(
    r"^(?P<owner>[a-zA-Z0-9_.-]+)-(?P<repo>[a-zA-Z0-9_.-]+)#(?P<number>\d+)-(?P<slug>.+)\.md$"
)


@dataclass
class ParsedSyncedFilename:
    """Parsed components of a synced filename."""

    owner: str
    repo: str
    issue_number: int
    slug: str

    @property
    def repository(self) -> str:
        """Get the full repository name (owner/repo)."""
        return f"{self.owner}/{self.repo}"

    @property
    def issue_id(self) -> str:
        """Get the issue ID in owner/repo#number format."""
        return f"{self.owner}/{self.repo}#{self.issue_number}"


def generate_synced_filename(
    owner: str,
    repo: str,
    issue_number: int,
    title: str,
) -> str:
    """Generate a synced filename from issue metadata.

    Args:
        owner: Repository owner (e.g., "acme")
        repo: Repository name (e.g., "project")
        issue_number: Issue number (e.g., 123)
        title: Issue title to slugify

    Returns:
        Filename in format: owner-repo#123-slug.md

    Examples:
        >>> generate_synced_filename("acme", "project", 123, "Fix Login Bug!")
        'acme-project#123-fix-login-bug.md'
    """
    slug = slugify(title)
    if not slug:
        slug = "untitled"
    return f"{owner}-{repo}#{issue_number}-{slug}.md"


def parse_synced_filename(filename: str) -> ParsedSyncedFilename | None:
    """Parse a synced filename into its components.

    Args:
        filename: The filename to parse (e.g., "acme-project#123-fix-bug.md")

    Returns:
        ParsedSyncedFilename with owner, repo, issue_number, slug
        or None if filename doesn't match synced format

    Examples:
        >>> result = parse_synced_filename("acme-project#123-fix-bug.md")
        >>> result.owner
        'acme'
        >>> result.repo
        'project'
        >>> result.issue_number
        123
    """
    match = SYNCED_FILENAME_PATTERN.match(filename)
    if not match:
        return None

    return ParsedSyncedFilename(
        owner=match.group("owner"),
        repo=match.group("repo"),
        issue_number=int(match.group("number")),
        slug=match.group("slug"),
    )


def is_synced_filename(filename: str) -> bool:
    """Check if a filename matches the synced format.

    Args:
        filename: The filename to check

    Returns:
        True if filename matches owner-repo#number-slug.md pattern

    Examples:
        >>> is_synced_filename("acme-project#123-fix-bug.md")
        True
        >>> is_synced_filename("fix-bug.md")
        False
    """
    return SYNCED_FILENAME_PATTERN.match(filename) is not None


def is_local_only_filename(filename: str) -> bool:
    """Check if a filename is a local-only task file (not synced).

    Local-only files are .md files that don't match the synced pattern.

    Args:
        filename: The filename to check

    Returns:
        True if filename is .md but not in synced format

    Examples:
        >>> is_local_only_filename("fix-bug.md")
        True
        >>> is_local_only_filename("acme-project#123-fix-bug.md")
        False
        >>> is_local_only_filename("readme.txt")
        False
    """
    if not filename.endswith(".md"):
        return False
    return not is_synced_filename(filename)
