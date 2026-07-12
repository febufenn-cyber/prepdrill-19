"""Composed Phase 1 repositories.

The implementation is split to keep each module independently reviewable and safe to publish.
"""
from .repository_base import RepositoryBase
from .repository_import import ImportRepositoryMixin
from .repository_review import ReviewRepositoryMixin
from .repository_public import PublicContentRepository

class ContentRepository(ImportRepositoryMixin, ReviewRepositoryMixin, RepositoryBase):
    """Internal content repository with no learner-facing exposure."""

    pass

__all__ = ["ContentRepository", "PublicContentRepository"]
