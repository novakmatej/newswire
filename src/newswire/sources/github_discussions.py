"""GitHub discussions source: GraphQL API, seen-set diff on discussion number.

Options: ``repo`` (required), ``category`` (required slug), ``token``
(**required** - the GraphQL API rejects anonymous requests), ``first`` (10),
``timeout``. Renders as ``links``.
"""

from __future__ import annotations

from typing import Any, Mapping

import requests

from newswire.config import ConfigError, SourceConfig
from newswire.models import LINKS, Item, Section
from newswire.registry import source_type
from newswire.sources.base import SourceError, new_by_seen, read_seen
from newswire.sources.github_releases import build_headers

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"


def _graphql(
    query: str, variables: dict[str, Any], token: str, timeout: float
) -> Mapping[str, Any]:
    try:
        response = requests.post(
            GITHUB_GRAPHQL_URL,
            headers=build_headers(token),
            json={"query": query, "variables": variables},
            timeout=timeout,
        )
        response.raise_for_status()
        data: Mapping[str, Any] = response.json()
    except requests.RequestException as exc:
        raise SourceError(f"GitHub GraphQL request failed: {exc}") from exc
    if "errors" in data:
        raise SourceError(f"GraphQL errors: {data['errors']}")
    return data


def _get_repository_id(repo: str, token: str, timeout: float) -> str:
    query = """
    query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
            id
        }
    }
    """
    owner, name = repo.split("/")
    data = _graphql(query, {"owner": owner, "name": name}, token, timeout)
    try:
        repository = data["data"]["repository"]
        if repository is None:
            raise SourceError(f"Repository {repo} not found")
        return str(repository["id"])
    except (KeyError, TypeError) as exc:
        raise SourceError(f"Unexpected response payload: {exc}") from exc


def _get_category_id(repo_id: str, category_slug: str, token: str, timeout: float) -> str:
    query = """
    query($repoId: ID!) {
        node(id: $repoId) {
            ... on Repository {
                discussionCategories(first: 20) {
                    nodes {
                        id
                        slug
                    }
                }
            }
        }
    }
    """
    data = _graphql(query, {"repoId": repo_id}, token, timeout)
    try:
        repository = data["data"]["node"]
        if repository is None:
            raise SourceError("Repository not found")
        categories = repository["discussionCategories"]["nodes"]
        for category in categories:
            if category["slug"] == category_slug:
                return str(category["id"])
        available = ", ".join(cat["slug"] for cat in categories)
        raise SourceError(f"Category '{category_slug}' not found. Available: {available}")
    except (KeyError, TypeError) as exc:
        raise SourceError(f"Unexpected response payload: {exc}") from exc


def fetch_discussions(
    repo: str, category_slug: str, token: str, first: int = 10, timeout: float = 10.0
) -> list[Item]:
    """Fetch open discussions in one category (newest first) as normalised items.

    ``tag`` carries the discussion number as a string.
    """
    repo_id = _get_repository_id(repo, token, timeout)
    category_id = _get_category_id(repo_id, category_slug, token, timeout)

    query = """
    query($repoId: ID!, $categoryId: ID!, $first: Int!) {
        node(id: $repoId) {
            ... on Repository {
                discussions(
                    first: $first
                    categoryId: $categoryId
                    states: [OPEN]
                    orderBy: {field: CREATED_AT, direction: DESC}
                ) {
                    nodes {
                        number
                        title
                        url
                        body
                        createdAt
                        author {
                            login
                        }
                    }
                }
            }
        }
    }
    """
    variables = {"repoId": repo_id, "categoryId": category_id, "first": first}
    data = _graphql(query, variables, token, timeout)
    try:
        repository = data["data"]["node"]
        if repository is None:
            raise SourceError("Repository not found")
        nodes = repository["discussions"]["nodes"]
    except (KeyError, TypeError) as exc:
        raise SourceError(f"Unexpected response payload: {exc}") from exc

    items = []
    for node in nodes:
        try:
            body = node.get("body")
            if body is not None:
                body = str(body).strip() or None
            items.append(
                Item(
                    title=str(node["title"]),
                    url=str(node["url"]),
                    body=body,
                    date=str(node["createdAt"]),
                    tag=str(int(node["number"])),
                )
            )
        except (KeyError, ValueError, TypeError):
            continue  # Skip invalid discussions
    return items


@source_type("github_discussions")
class GithubDiscussionsSource:
    def __init__(self, cfg: SourceConfig):
        self.id = cfg.id
        self.title = cfg.title
        self.emoji = cfg.emoji
        options = cfg.options
        self.repo = options.get("repo")
        if not self.repo:
            raise ConfigError(f"source '{cfg.id}': github_discussions requires option 'repo'")
        self.category = options.get("category")
        if not self.category:
            raise ConfigError(f"source '{cfg.id}': github_discussions requires option 'category'")
        self.token = options.get("token")
        if not self.token:
            raise ConfigError(
                f"source '{cfg.id}': github_discussions requires option 'token' "
                "(the GitHub GraphQL API rejects anonymous requests)"
            )
        self.first = int(options.get("first", 10))
        self.timeout = float(options.get("timeout", 10))

    def check(self, entry: dict[str, Any] | None) -> tuple[Section | None, dict[str, Any] | None]:
        discussions = fetch_discussions(
            self.repo, self.category, self.token, self.first, self.timeout
        )
        if not discussions:
            return None, None
        new_ids = set(new_by_seen([item.tag or "" for item in discussions], read_seen(entry)))
        new = [item for item in discussions if item.tag in new_ids]
        next_entry = {
            "seen": [item.tag for item in discussions],
            "last_check": discussions[0].date or "",
        }
        if not new:
            return None, next_entry
        section = Section(
            source_id=self.id, title=self.title, kind=LINKS, items=tuple(new), emoji=self.emoji
        )
        return section, next_entry
