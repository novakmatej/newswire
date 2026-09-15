"""The shipped configs load, and both example layouts produce the same config."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from newswire.config import Config, load_config
from newswire.core import run  # noqa: F401  (imports register all built-in types)
from newswire.registry import NOTIFIER_TYPES, SOURCE_TYPES, STATE_BACKENDS

REPO_ROOT = Path(__file__).parent.parent

ENV_VARS = {
    "GIST_ID": "gist-id",
    "GIST_TOKEN": "gist-token",
    "GITHUB_TOKEN": "gh-token",
    "SLACK_WEBHOOK_URL": "https://hooks.slack.com/services/x",
    "TEAMS_WEBHOOK_URL": "https://example.com/teams",
}


@pytest.fixture(autouse=True)
def example_env(monkeypatch: pytest.MonkeyPatch):
    for name, value in ENV_VARS.items():
        monkeypatch.setenv(name, value)


def _normalize(config: Config) -> Config:
    """Strip file origins so the two layouts compare equal."""
    return dataclasses.replace(
        config,
        sources=tuple(dataclasses.replace(s, origin="") for s in config.sources),
        notifiers=tuple(dataclasses.replace(n, origin="") for n in config.notifiers),
    )


def test_single_file_and_directory_examples_load_equal() -> None:
    single = load_config(REPO_ROOT / "config.example.yml")
    split = load_config(REPO_ROOT / "config.example")
    assert _normalize(single) == _normalize(split)


def test_example_uses_only_registered_types() -> None:
    config = load_config(REPO_ROOT / "config.example.yml")
    assert {s.type for s in config.sources} <= set(SOURCE_TYPES)
    assert {n.type for n in config.notifiers} <= set(NOTIFIER_TYPES)
    assert config.state.backend in STATE_BACKENDS


def test_example_ships_every_source_and_notifier_type() -> None:
    """The example config must show every registered type at least once."""
    config = load_config(REPO_ROOT / "config.example.yml")
    assert {s.type for s in config.sources} == set(SOURCE_TYPES)
    assert {n.type for n in config.notifiers} == set(NOTIFIER_TYPES)


def test_repo_deployment_config_loads() -> None:
    config = load_config(REPO_ROOT / "config")
    # state keys of the pre-rewrite Gist are preserved as source ids
    ids = [s.id for s in config.sources]
    assert ids[0] == "dbt-cloud-releases"
    for legacy_key in (
        "dbt-core-releases",
        "terraform-provider-releases",
        "dbt-charts-releases",
        "dbt-blog",
        "dbt-webinars",
        "dbt-fusion-discussions",
        "dbt-blog-press",
    ):
        assert legacy_key in ids
    assert config.state.options["filename"] == "dbt-news-state.json"
    # digest order contract: cloud -> core -> discussions -> blog -> categories
    # -> webinars -> terraform -> charts
    assert ids.index("dbt-core-releases") < ids.index("dbt-fusion-discussions")
    assert ids.index("dbt-fusion-discussions") < ids.index("dbt-blog")
    assert ids.index("dbt-webinars") < ids.index("terraform-provider-releases")
    assert ids.index("terraform-provider-releases") < ids.index("dbt-charts-releases")
