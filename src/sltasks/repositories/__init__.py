"""Repository layer for data access."""

from .filesystem import FilesystemRepository
from .github_projects import GitHubProjectsRepository
from .protocol import RepositoryProtocol

__all__ = [
    "FilesystemRepository",
    "GitHubProjectsRepository",
    "RepositoryProtocol",
]
