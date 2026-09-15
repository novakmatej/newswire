"""GitHub releases source: REST ``/repos/{repo}/releases``, cursor diff on tag.

Options: ``repo`` (required, ``owner/name``), ``token``, ``per_page`` (30),
``timeout``. Renders as ``cards``.
"""

from __future__ import annotations

from typing import Any, Mapping

import requests

from newswire.config import ConfigError, SourceConfig
from newswire.models import CARDS, Item, Section
from newswire.registry import source_type
from newswire.sources.base import SourceError, new_by_cursor, read_cursor

GITHUB_API_URL = "https://api.github.com"


def build_headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_releases(
    repo: str, token: str | None = None, per_page: int = 30, timeout: float = 10.0
) -> list[Item]:
    """Fetch releases (newest first) as normalised items; ``tag`` holds the tag name."""
    url = f"{GITHUB_API_URL}/repos/{repo}/releases"
    params = {"per_page": min(per_page, 100), "page": 1}

    try:
        response = requests.get(url, headers=build_headers(token), params=params, timeout=timeout)
        response.raise_for_status()
        data_list = response.json()
    except requests.RequestException as exc:
        raise SourceError(f"Failed to fetch releases for {repo}: {exc}") from exc

    if not isinstance(data_list, list):
        raise SourceError(f"Unexpected response payload from GitHub API for {repo}")

    items = []
    for data in data_list:
        if not isinstance(data, Mapping):
            continue
        try:
            tag_name = str(data["tag_name"])
            html_url = str(data["html_url"])
        except KeyError:
            continue  # Skip releases missing required fields

        body = data.get("body")
        if body is not None:
            body = str(body).strip() or None
        name = data.get("name")
        published_at = data.get("published_at")

        items.append(
            Item(
                title=str(name) if name else tag_name,
                url=html_url,
                body=body,
                date=str(published_at) if published_at else None,
                tag=tag_name,
            )
        )
    return items


@source_type("github_releases")
class GithubReleasesSource:
    def __init__(self, cfg: SourceConfig):
        self.id = cfg.id
        self.title = cfg.title
        self.emoji = cfg.emoji
        options = cfg.options
        self.repo = options.get("repo")
        if not self.repo:
            raise ConfigError(f"source '{cfg.id}': github_releases requires option 'repo'")
        self.token = options.get("token")
        self.per_page = int(options.get("per_page", 30))
        self.timeout = float(options.get("timeout", 10))

    def check(self, entry: dict[str, Any] | None) -> tuple[Section | None, dict[str, Any] | None]:
        releases = fetch_releases(self.repo, self.token, self.per_page, self.timeout)
        count = new_by_cursor([item.tag or "" for item in releases], read_cursor(entry))
        new = releases[:count]
        if not new:
            return None, None
        section = Section(
            source_id=self.id, title=self.title, kind=CARDS, items=tuple(new), emoji=self.emoji
        )
        next_entry = {"cursor": releases[0].tag, "last_check": releases[0].date or ""}
        return section, next_entry
