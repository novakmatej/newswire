"""Config loading: single file, directory layout, ${ENV} interpolation, validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from newswire.config import ConfigError, load_config

MINIMAL = """
state:
  backend: local_file
  options:
    path: state.json

sources:
  - id: core
    type: github_releases
    options:
      repo: dbt-labs/dbt-core

notifiers:
  - id: slack
    type: slack
    options:
      webhook_url: ${TEST_WEBHOOK}
"""


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_load_single_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_WEBHOOK", "https://hooks.example.com/x")
    config = load_config(write(tmp_path / "config.yml", MINIMAL))

    assert config.state.backend == "local_file"
    assert config.state.options["path"] == "state.json"
    assert [s.id for s in config.sources] == ["core"]
    assert config.sources[0].title == "core"  # defaults to the id
    assert config.notifiers[0].options["webhook_url"] == "https://hooks.example.com/x"
    assert config.notifiers[0].send_no_news is True
    assert config.digest.title == "News"


def test_unset_env_var_fails_naming_variable_and_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TEST_WEBHOOK", raising=False)
    with pytest.raises(ConfigError, match="TEST_WEBHOOK") as exc:
        load_config(write(tmp_path / "config.yml", MINIMAL))
    assert "slack" in str(exc.value)


def test_disabled_entry_skips_env_interpolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("TEST_WEBHOOK", raising=False)
    content = MINIMAL.replace("- id: slack", "- id: slack\n    enabled: false")
    config = load_config(write(tmp_path / "config.yml", content))
    assert config.notifiers[0].enabled is False
    assert config.enabled_notifiers() == ()


def test_missing_state_block_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="state"):
        load_config(write(tmp_path / "config.yml", "sources: []\nnotifiers: []\n"))


def test_unknown_top_level_key_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="unknown top-level key 'sinks'"):
        load_config(write(tmp_path / "config.yml", MINIMAL + "\nsinks: []\n"))


def test_unknown_entry_key_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_WEBHOOK", "x")
    content = MINIMAL.replace("type: github_releases", "type: github_releases\n    chanel: oops")
    with pytest.raises(ConfigError, match="chanel"):
        load_config(write(tmp_path / "config.yml", content))


def test_duplicate_id_fails_naming_both_files(tmp_path: Path) -> None:
    write(tmp_path / "conf" / "config.yml", "state: {backend: local_file, options: {path: s}}")
    write(
        tmp_path / "conf" / "sources.yml",
        "- {id: core, type: github_releases, options: {repo: a/b}}",
    )
    write(
        tmp_path / "conf" / "sources.d" / "10-more.yml",
        "- {id: core, type: github_releases, options: {repo: c/d}}",
    )
    with pytest.raises(ConfigError, match="duplicate source id 'core'") as exc:
        load_config(tmp_path / "conf")
    assert "sources.yml" in str(exc.value)
    assert "10-more.yml" in str(exc.value)


def test_unknown_file_in_config_dir_fails(tmp_path: Path) -> None:
    write(tmp_path / "conf" / "config.yml", "state: {backend: local_file, options: {path: s}}")
    write(tmp_path / "conf" / "sources.yaml.bak", "- {}")
    with pytest.raises(ConfigError, match="sources.yaml.bak"):
        load_config(tmp_path / "conf")


def test_unknown_yaml_name_in_config_dir_fails(tmp_path: Path) -> None:
    write(tmp_path / "conf" / "config.yml", "state: {backend: local_file, options: {path: s}}")
    write(tmp_path / "conf" / "sourcess.yml", "- {}")
    with pytest.raises(ConfigError, match="sourcess.yml"):
        load_config(tmp_path / "conf")


def test_notify_unknown_notifier_id_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_WEBHOOK", "x")
    content = MINIMAL.replace(
        "type: github_releases", "type: github_releases\n    notify: [nonexistent]"
    )
    with pytest.raises(ConfigError, match="unknown notifier id 'nonexistent'") as exc:
        load_config(write(tmp_path / "config.yml", content))
    assert "core" in str(exc.value)


def test_fragments_accept_bare_and_wrapped(tmp_path: Path) -> None:
    write(tmp_path / "conf" / "config.yml", "state: {backend: local_file, options: {path: s}}")
    write(
        tmp_path / "conf" / "sources.yml",
        "sources:\n  - {id: a, type: github_releases, options: {repo: a/b}}",
    )
    write(
        tmp_path / "conf" / "notifiers.yml",
        "- {id: n, type: slack, enabled: false, options: {}}",
    )
    config = load_config(tmp_path / "conf")
    assert [s.id for s in config.sources] == ["a"]
    assert [n.id for n in config.notifiers] == ["n"]


def test_directory_load_order_is_lexicographic(tmp_path: Path) -> None:
    """sources order (= digest order) follows lexicographic file paths."""
    write(tmp_path / "conf" / "config.yml", "state: {backend: local_file, options: {path: s}}")
    write(
        tmp_path / "conf" / "sources.d" / "20-second.yml",
        "- {id: second, type: github_releases, options: {repo: a/b}}",
    )
    write(
        tmp_path / "conf" / "sources.d" / "10-first.yml",
        "- {id: first, type: github_releases, options: {repo: a/b}}",
    )
    config = load_config(tmp_path / "conf")
    assert [s.id for s in config.sources] == ["first", "second"]


def test_defaults_timeout_flows_into_options(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TEST_WEBHOOK", "x")
    config = load_config(write(tmp_path / "config.yml", "defaults:\n  timeout: 42\n" + MINIMAL))
    assert config.sources[0].options["timeout"] == 42
    assert config.notifiers[0].options["timeout"] == 42
    assert config.state.options["timeout"] == 42


def test_mappings_merge_later_wins(tmp_path: Path) -> None:
    write(tmp_path / "conf" / "config.yml", "state: {backend: local_file, options: {path: s}}")
    write(tmp_path / "conf" / "state.yml", "backend: local_file\noptions: {path: override.json}")
    config = load_config(tmp_path / "conf")
    # config.yml < state.yml lexicographically, so state.yml wins
    assert config.state.options["path"] == "override.json"


def test_missing_config_path_fails(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yml")
