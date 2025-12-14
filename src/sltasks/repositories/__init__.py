"""Repository layer for data access."""

from .filesystem import FilesystemRepository
from .protocol import RepositoryProtocol

__all__ = [
    "FilesystemRepository",
    "RepositoryProtocol",
]
