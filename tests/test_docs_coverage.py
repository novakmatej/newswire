"""Docs-rot guard: every registered type is documented, and vice versa."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from newswire.core import run  # noqa: F401  (imports register all built-in types)
from newswire.registry import NOTIFIER_TYPES, SOURCE_TYPES, STATE_BACKENDS

DOCS = Path(__file__).parent.parent / "docs" / "reference"

# A documented type is a `## `-heading with the type name in backticks.
_HEADING_RE = re.compile(r"^## `([a-z_]+)`", re.MULTILINE)


def _documented(page: str) -> set[str]:
    return set(_HEADING_RE.findall((DOCS / page).read_text(encoding="utf-8")))


@pytest.mark.parametrize(
    ("page", "registry"),
    [
        ("sources.md", SOURCE_TYPES),
        ("notifiers.md", NOTIFIER_TYPES),
        ("state.md", STATE_BACKENDS),
    ],
    ids=["sources", "notifiers", "state-backends"],
)
def test_registry_and_reference_docs_match(page: str, registry: dict) -> None:
    documented = _documented(page)
    registered = set(registry)

    missing_docs = registered - documented
    assert not missing_docs, (
        f"registered types missing from docs/reference/{page}: {sorted(missing_docs)} - "
        "add a '## `<type>`' section with an options table"
    )

    ghost_docs = documented - registered
    assert not ghost_docs, (
        f"docs/reference/{page} documents types that are not registered: {sorted(ghost_docs)}"
    )


def test_every_documented_type_has_an_options_table() -> None:
    for page in ("sources.md", "notifiers.md", "state.md"):
        text = (DOCS / page).read_text(encoding="utf-8")
        for name in _documented(page):
            section = text.split(f"## `{name}`", 1)[1].split("\n## ", 1)[0]
            assert "| Option | Type | Required | Default |" in section, (
                f"docs/reference/{page}: section '{name}' has no options table"
            )
