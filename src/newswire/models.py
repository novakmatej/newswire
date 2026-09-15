"""Normalised data model shared by sources and notifiers.

Sources emit :class:`Section` objects made of :class:`Item` objects; notifiers
render them per channel. The ``kind`` field selects one of three render shapes:

- ``cards`` - one rich card per item (GitHub releases: parsed body, tag, date)
- ``links`` - a titled bullet list of ``[title](url)`` links
- ``notes`` - a titled bullet list of markdown text lines with an optional
  subtitle and a "view all" footer link (release-notes pages)
"""

from __future__ import annotations

from dataclasses import dataclass, field

CARDS = "cards"
LINKS = "links"
NOTES = "notes"


@dataclass(frozen=True)
class Item:
    """One news item. ``title`` may contain markdown links for ``notes`` items."""

    title: str
    url: str | None = None
    body: str | None = None
    date: str | None = None
    tag: str | None = None


@dataclass(frozen=True)
class Section:
    """What one source contributes to a digest."""

    source_id: str
    title: str
    kind: str
    items: tuple[Item, ...]
    emoji: str | None = None
    subtitle: str | None = None
    link: str | None = None


@dataclass(frozen=True)
class Digest:
    """Channel-agnostic digest metadata plus the ordered sections."""

    title: str
    intro: str
    sections: tuple[Section, ...] = field(default_factory=tuple)
