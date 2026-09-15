"""dbt Cloud release-notes scraper: h2 month sections with bullet lists, section compare.

Named after its target on purpose - the parsing (h2 + ul/li, headings trimmed
to two words) is coupled to the dbt Cloud release-notes page on
docs.getdbt.com. The newest ``h2`` heading and its bullets are compared
against the stored ones: a new heading reports all its bullets, the same
heading reports only bullets not seen before. Links inside bullets are kept
as markdown.

Options: ``url`` (required), ``timeout``. Scraper - breaks when the page
markup changes. Renders as ``notes``.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

import requests
from bs4 import BeautifulSoup, Tag

from newswire.config import ConfigError, SourceConfig
from newswire.models import NOTES, Item, Section
from newswire.registry import source_type
from newswire.sources.base import SourceError


def _extract_text_with_links(element: Tag, base_url: str = "") -> str:
    """Extract an element's text, converting <a> tags to [text](url) markdown."""
    from urllib.parse import urljoin

    links_info = []
    for link in element.find_all("a", recursive=True):
        href = link.get("href", "")
        link_text = link.get_text(strip=True)
        if href and link_text:
            if not href.startswith(("http://", "https://")) and base_url:
                href = urljoin(base_url, href)
            links_info.append({"link": link, "markdown": f"[{link_text}]({href})"})

    # Replace links with placeholders before text extraction so surrounding
    # whitespace survives, then substitute the markdown back in.
    for i, link_info in enumerate(links_info):
        placeholder = f"__LINK_{i}__"
        link_info["link"].replace_with(placeholder)
        link_info["placeholder"] = placeholder

    text = element.get_text(separator=" ", strip=False)

    for link_info in links_info:
        text = text.replace(link_info["placeholder"], link_info["markdown"])

    def fix_url_spaces(match: re.Match[str]) -> str:
        link_text = match.group(1)
        url = re.sub(r"\s+", "", match.group(2))
        return f"[{link_text}]({url})"

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,:;!?])", r"\1", text)
    text = re.sub(r"([.,:;!?])([a-zA-Z])", r"\1 \2", text)
    # Strip whitespace from link URLs last - the punctuation spacing above
    # would otherwise leave "docs. example. com" inside the URLs (a pre-1.0 bug).
    text = re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", fix_url_spaces, text)

    return text.strip()


def scrape_release_sections(url: str, timeout: float = 10.0) -> list[tuple[str, tuple[str, ...]]]:
    """Scrape (heading, bullet items) pairs, newest first (first h2 is newest)."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "lxml")
        sections = []

        for h2 in soup.find_all("h2"):
            heading_text = h2.get_text(strip=True)
            if not heading_text:
                continue
            # Page headings repeat their text in anchor spans; keep just the
            # first two words (e.g. "November 2025").
            heading_text = heading_text.split("\n")[0].strip()
            parts = heading_text.split()
            if len(parts) >= 2:
                heading_text = " ".join(parts[:2])
            if not heading_text:
                continue

            items = []
            for sibling in h2.next_siblings:
                if sibling.name == "h2":
                    break
                if sibling.name == "ul":
                    for li in sibling.find_all("li", recursive=False):
                        item_text = _extract_text_with_links(li, base_url=url)
                        if item_text:
                            items.append(item_text)
                elif sibling.name == "li":
                    item_text = _extract_text_with_links(sibling, base_url=url)
                    if item_text:
                        items.append(item_text)

            if items:
                sections.append((heading_text, tuple(items)))

        return sections

    except requests.RequestException as exc:
        raise SourceError(f"Failed to scrape release notes {url}: {exc}") from exc
    except Exception as exc:
        raise SourceError(f"Failed to parse release notes HTML from {url}: {exc}") from exc


def find_changes_in_section(
    current_heading: str,
    current_items: Sequence[str],
    previous_heading: str | None,
    previous_items: Sequence[str] | None,
) -> tuple[str, tuple[str, ...], bool] | None:
    """Diff the newest section against the stored one.

    Returns:
        (heading, new items, is_new_section) or None when nothing changed.
    """
    if previous_heading is None or previous_items is None or current_heading != previous_heading:
        if current_items:
            return (current_heading, tuple(current_items), True)
        return None

    new_items = set(current_items) - set(previous_items)
    if new_items:
        return (current_heading, tuple(new_items), False)
    return None


@source_type("dbt_cloud_release_notes")
class DbtCloudReleaseNotesSource:
    def __init__(self, cfg: SourceConfig):
        self.id = cfg.id
        self.title = cfg.title
        self.emoji = cfg.emoji
        self.url = cfg.options.get("url")
        if not self.url:
            raise ConfigError(f"source '{cfg.id}': dbt_cloud_release_notes requires option 'url'")
        self.timeout = float(cfg.options.get("timeout", 10))

    def check(self, entry: dict[str, Any] | None) -> tuple[Section | None, dict[str, Any] | None]:
        sections = scrape_release_sections(self.url, self.timeout)
        if not sections:
            return None, None

        heading, items = sections[0]
        entry = entry or {}
        changes = find_changes_in_section(
            current_heading=heading,
            current_items=items,
            previous_heading=entry.get("current_h2"),
            previous_items=entry.get("items"),
        )

        # State entry keeps the pre-1.0 shape (current_h2 + items). It is
        # advanced on changes, or refreshed when the heading is unchanged;
        # a new heading with no bullets leaves the stored entry alone.
        next_entry = None
        if changes or entry.get("current_h2") == heading:
            next_entry = {"current_h2": heading, "items": list(items), "last_check": ""}

        if not changes:
            return None, next_entry

        changed_heading, new_items, _is_new = changes
        section = Section(
            source_id=self.id,
            title=self.title,
            kind=NOTES,
            items=tuple(Item(title=text) for text in new_items),
            emoji=self.emoji,
            subtitle=changed_heading,
            link=self.url,
        )
        return section, next_entry
