"""Notifier protocol and the shared, channel-agnostic bits of rendering.

Which sections exist and in what order is decided by config (the ``sources``
list order) and handed to notifiers as :class:`newswire.models.Section` objects.
Each channel keeps its own payload rendering (Block Kit vs Adaptive Card) -
that duplication is deliberate; the shapes genuinely differ.
"""

from __future__ import annotations

import re
from typing import Protocol, Sequence

from newswire.models import Section


class NotificationError(RuntimeError):
    """Base exception for notification errors."""


class Notifier(Protocol):
    """Protocol for notification channels."""

    id: str
    send_no_news_enabled: bool

    def send_digest(self, sections: Sequence[Section]) -> None:
        """Send a digest of the given sections, in the given order.

        Raises:
            NotificationError: If sending fails.
        """
        ...

    def send_section(self, section: Section) -> None:
        """Send a single section without the digest header.

        Raises:
            NotificationError: If sending fails.
        """
        ...

    def send_no_news(self) -> None:
        """Send a "no news" notification.

        Raises:
            NotificationError: If sending fails.
        """
        ...


SECTION_EMOJI = {
    "Features": "✨",
    "Fixes": "🐛",
    "Breaking Changes": "⚠️",
    "Dependencies": "📦",
    "Under the Hood": "🔧",
    "Documentation": "📚",
    "Behind the scenes": "🔧",
}

# Leading tags in release-notes bullets that get bolded (e.g. "New: ...").
NOTE_TAGS = ("New", "Enhancement", "Fix", "Behavior change")

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^\)]+)\)")


def parse_release_sections(body: str) -> dict[str, list[str]]:
    """Parse release-notes markdown into sections (Features, Fixes, etc.).

    Handles both ## and ### headings, and both - and * bullets. Bullet text is
    kept verbatim so markdown links survive for the per-channel formatters.
    """
    sections: dict[str, list[str]] = {}
    current_section = "Other"
    current_items: list[str] = []

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("##"):
            if current_items:
                sections[current_section] = current_items
            current_section = line.lstrip("#").strip()
            current_items = []
        elif line.startswith("-") or line.startswith("*"):
            current_items.append(line.lstrip("-* ").strip())

    if current_items:
        sections[current_section] = current_items

    return sections


def convert_markdown_links(text: str, template: str) -> str:
    r"""Convert ``[text](url)`` links using a template with ``\1`` (text) and ``\2`` (url)."""
    return _MD_LINK_RE.sub(template, text)


def bold_leading_tag(item: str, bold: str) -> str:
    """Wrap a leading NOTE_TAGS tag in the channel's bold markers."""
    for tag in NOTE_TAGS:
        if item.startswith(f"{tag}:"):
            return item.replace(f"{tag}:", f"{bold}{tag}:{bold}", 1)
        if item.startswith(f"{tag} "):
            return item.replace(f"{tag} ", f"{bold}{tag}{bold} ", 1)
    return item


def heading_text(section: Section) -> str:
    """Section heading: emoji + title when an emoji is configured."""
    return f"{section.emoji} {section.title}" if section.emoji else section.title
