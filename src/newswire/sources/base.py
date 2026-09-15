"""Source protocol, shared diff idioms, and shared state-entry helpers.

Three diff idioms exist and are not interchangeable:

- cursor: find the stored id in a newest-first list; everything before that
  index is new. Stored id missing -> everything is new. No stored id (first
  run) -> only the newest item counts.
- seen-set: store the full set of ids; new = not in the set. Items that
  disappear are dropped from state silently.
- section compare: newest heading + its bullets vs the stored ones
  (implemented in :mod:`newswire.sources.dbt_cloud_release_notes`).
"""

from __future__ import annotations

from typing import Any, Protocol

from newswire.models import Section


class SourceError(RuntimeError):
    """Raised when fetching or parsing a source fails."""


class Source(Protocol):
    """One configured source instance."""

    id: str

    def check(self, entry: dict[str, Any] | None) -> tuple[Section | None, dict[str, Any] | None]:
        """Fetch and diff against the stored state entry.

        Returns:
            (section with new items or None, next state entry or None).
            A ``None`` next entry means the stored entry must not be touched.

        Raises:
            SourceError: if fetching or parsing fails.
        """
        ...


def new_by_cursor(ids: list[str], last: str | None) -> int:
    """How many leading items of a newest-first list are new (cursor idiom)."""
    if not ids:
        return 0
    if not last:
        return 1
    if last in ids:
        return ids.index(last)
    return len(ids)


def new_by_seen(ids: list[str], seen: set[str]) -> list[str]:
    """Ids not yet in the stored seen-set, in fetch order (seen-set idiom)."""
    return [item_id for item_id in ids if item_id not in seen]


def read_cursor(entry: dict[str, Any] | None) -> str | None:
    """Stored cursor; falls back to the pre-1.0 field names (last_id, last_url)."""
    if not entry:
        return None
    for key in ("cursor", "last_id", "last_url"):
        value = entry.get(key)
        if value:
            return str(value)
    return None


def read_seen(entry: dict[str, Any] | None) -> set[str]:
    """Stored seen-set; falls back to the pre-1.0 field names (last_urls, urls, numbers)."""
    if not entry:
        return set()
    for key in ("seen", "last_urls", "urls", "numbers"):
        value = entry.get(key)
        if isinstance(value, list):
            return {str(item) for item in value}
    return set()
