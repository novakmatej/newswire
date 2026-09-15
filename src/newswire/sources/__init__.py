"""Source types. Importing this package registers every built-in type."""

from newswire.sources import (  # noqa: F401  (imports run the registrations)
    dbt_cloud_release_notes,
    docusaurus_blog,
    github_discussions,
    github_releases,
    html_list,
)
from newswire.sources.base import Source, SourceError

__all__ = ["Source", "SourceError"]
