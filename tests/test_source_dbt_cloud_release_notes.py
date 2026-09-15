"""dbt_cloud_release_notes source: scraping, link markdown, section compare via check()."""

from __future__ import annotations

import pytest
from requests import RequestException

from newswire.sources.base import SourceError
from newswire.sources.dbt_cloud_release_notes import (
    DbtCloudReleaseNotesSource,
    scrape_release_sections,
)
from tests.helpers import StubResponse

HTML = """
<html>
<body>
    <h2 class="anchor" id="november-2025">November 2025</h2>
    <ul>
        <li><strong>New</strong>: Feature 1 added</li>
        <li><strong>New</strong>: Feature 2 added</li>
        <li><strong>Fix</strong>: Bug fixed</li>
    </ul>
    <h2 class="anchor" id="october-2025">October 2025</h2>
    <ul>
        <li><strong>Enhancement</strong>: Performance improved</li>
    </ul>
</body>
</html>
"""

HTML_WITH_LINKS = (
    "<html><body>"
    '<h2 class="anchor" id="november-2025">November 2025</h2>'
    "<ul>"
    "<li><strong>New</strong>: The Snowflake adapter now supports basic table "
    "materialization on Iceberg tables registered in a Glue catalog through a "
    '<a href="https://docs.snowflake.com/en/user-guide/tables-iceberg-catalog-linked-database'
    '#label-catalog-linked-db-create" target="_blank" rel="noopener noreferrer">'
    "catalog-linked database</a>. "
    "For more information, see "
    '<a href="/docs/mesh/iceberg/snowflake-iceberg-support#external-catalogs">'
    "Glue Data Catalog</a>.</li>"
    "</ul>"
    "</body></html>"
)

URL = "https://docs.getdbt.com/docs/dbt-versions/release-notes/cloud"


def _stub_get(monkeypatch: pytest.MonkeyPatch, html: str) -> None:
    monkeypatch.setattr(
        "newswire.sources.dbt_cloud_release_notes.requests.get",
        lambda url, timeout=None: StubResponse(content=html.encode("utf-8")),
    )


def test_scrape_release_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_get(monkeypatch, HTML)
    sections = scrape_release_sections(URL)

    assert len(sections) == 2
    heading, items = sections[0]
    assert heading == "November 2025"
    assert len(items) == 3
    assert "Feature 1 added" in items[0]
    assert sections[1][0] == "October 2025"


def test_scrape_keeps_links_as_markdown(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_get(monkeypatch, HTML_WITH_LINKS)
    sections = scrape_release_sections(URL)

    assert len(sections) == 1
    item = sections[0][1][0]
    assert "[catalog-linked database]" in item
    assert "docs.snowflake.com" in item
    assert "[Glue Data Catalog]" in item
    assert "Snowflake adapter" in item
    # relative link resolved against the page URL
    assert "https://docs.getdbt.com/docs/mesh/iceberg" in item


def test_scrape_request_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "newswire.sources.dbt_cloud_release_notes.requests.get",
        lambda *a, **k: (_ for _ in ()).throw(RequestException("network error")),
    )
    with pytest.raises(SourceError):
        scrape_release_sections(URL)


def test_check_keeps_pre_rewrite_state_shape(monkeypatch: pytest.MonkeyPatch, source_cfg) -> None:
    _stub_get(monkeypatch, HTML)
    source = DbtCloudReleaseNotesSource(source_cfg("cloud", options={"url": URL}))

    # First run: whole newest section is new; state keeps current_h2 + items
    section, next_entry = source.check(None)
    assert section is not None
    assert section.subtitle == "November 2025"
    assert section.kind == "notes"
    assert section.link == URL
    assert len(section.items) == 3
    assert next_entry["current_h2"] == "November 2025"
    assert len(next_entry["items"]) == 3

    # Same heading, one stored bullet -> only the others are new
    section, next_entry = source.check(
        {"current_h2": "November 2025", "items": ["New: Feature 1 added"]}
    )
    assert section is not None
    assert len(section.items) == 2
    assert next_entry["current_h2"] == "November 2025"

    # Identical state -> nothing new, entry refreshed (same heading)
    section, next_entry = source.check(
        {
            "current_h2": "November 2025",
            "items": ["New: Feature 1 added", "New: Feature 2 added", "Fix: Bug fixed"],
        }
    )
    assert section is None
    assert next_entry is not None

    # Different stored heading with changes -> new section reported
    section, _ = source.check({"current_h2": "October 2025", "items": ["old"]})
    assert section is not None
    assert section.subtitle == "November 2025"
