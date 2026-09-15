"""Config loading: one YAML file or a config directory, one merged result.

Layout rules (documented in docs/config-layout.md):

- ``--config`` points at a file or a directory.
- In a directory, the file name is the top-level key it contributes:
  ``sources.yml`` -> the ``sources`` list, ``state.yml`` -> the ``state``
  mapping, ... ``config.yml`` may carry any top-level key.
- A ``<key>.d/`` directory contributes fragments (``*.yml`` / ``*.yaml``)
  to that same key.
- Load order is lexicographic by path. Lists concatenate in load order;
  mappings merge key-by-key (recursively), later wins.
- A duplicate ``id`` is an error naming both files. An unknown file name in a
  config directory is an error. Dotfiles are ignored.
- ``${ENV_VAR}`` interpolation applies to every string value of an *enabled*
  entry (and to ``state``/``defaults``/``digest``); a referenced-but-unset
  variable fails naming the variable and the config path.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KNOWN_TOP_KEYS = ("defaults", "digest", "state", "sources", "notifiers")
_LIST_KEYS = {"sources", "notifiers"}
_YAML_SUFFIXES = {".yml", ".yaml"}
_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(RuntimeError):
    """Raised on an invalid or unloadable config; message names the offender."""


@dataclass(frozen=True)
class SourceConfig:
    id: str
    type: str
    enabled: bool = True
    title: str = ""
    emoji: str | None = None
    notify: tuple[str, ...] | None = None
    options: dict[str, Any] = field(default_factory=dict)
    origin: str = ""


@dataclass(frozen=True)
class NotifierConfig:
    id: str
    type: str
    enabled: bool = True
    send_no_news: bool = True
    options: dict[str, Any] = field(default_factory=dict)
    origin: str = ""


@dataclass(frozen=True)
class StateConfig:
    backend: str
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DigestConfig:
    title: str = "News"
    intro: str = "Here's what's been happening:"


@dataclass(frozen=True)
class Config:
    state: StateConfig
    digest: DigestConfig = field(default_factory=DigestConfig)
    sources: tuple[SourceConfig, ...] = ()
    notifiers: tuple[NotifierConfig, ...] = ()

    def enabled_sources(self) -> tuple[SourceConfig, ...]:
        return tuple(s for s in self.sources if s.enabled)

    def enabled_notifiers(self) -> tuple[NotifierConfig, ...]:
        return tuple(n for n in self.notifiers if n.enabled)


# --------------------------------------------------------------------------
# raw loading / merging


def _read_yaml(path: Path) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ConfigError(f"{path}: invalid YAML: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"{path}: cannot read config file: {exc}") from exc


def _unwrap_fragment(path: Path, key: str, data: Any) -> Any:
    """Accept both a bare list/mapping and one wrapped under its key."""
    if isinstance(data, dict) and set(data) == {key}:
        data = data[key]
    if key in _LIST_KEYS:
        if not isinstance(data, list):
            raise ConfigError(f"{path}: '{key}' must be a list, got {type(data).__name__}")
    elif not isinstance(data, dict):
        raise ConfigError(f"{path}: '{key}' must be a mapping, got {type(data).__name__}")
    return data


def _merge_mapping(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_mapping(merged[key], value)
        else:
            merged[key] = value
    return merged


def _contribute(raw: dict[str, Any], key: str, value: Any, origin: Path) -> None:
    """Merge one top-level contribution into the accumulating raw config.

    List entries are tagged with their origin file so later errors
    (duplicate id, invalid entry) can name it.
    """
    if key in _LIST_KEYS:
        entries = raw.setdefault(key, [])
        for entry in value:
            entries.append((str(origin), entry))
    else:
        if not isinstance(value, dict):
            raise ConfigError(f"{origin}: '{key}' must be a mapping, got {type(value).__name__}")
        raw[key] = _merge_mapping(raw.get(key, {}), value)


def _contribute_file(raw: dict[str, Any], path: Path) -> None:
    """One whole config file: mapping of known top-level keys."""
    data = _read_yaml(path)
    if data is None:
        return
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping of config keys")
    for key, value in data.items():
        if key not in KNOWN_TOP_KEYS:
            raise ConfigError(
                f"{path}: unknown top-level key '{key}' (known: {', '.join(KNOWN_TOP_KEYS)})"
            )
        _contribute(raw, key, value, path)


def _collect_dir_files(directory: Path) -> list[tuple[Path, str | None]]:
    """All contributing files as (path, key); key None means a full config file.

    Every visible file must match the naming convention; anything else is an
    error so a typo'd ``sources.yaml.bak`` cannot be silently ignored.
    """
    files: list[tuple[Path, str | None]] = []
    for child in directory.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_dir():
            stem, suffix = child.name.rsplit(".", 1) if "." in child.name else (child.name, "")
            if suffix != "d" or stem not in KNOWN_TOP_KEYS:
                raise ConfigError(
                    f"{child}: unexpected directory in config directory "
                    f"(expected one of: {', '.join(k + '.d' for k in KNOWN_TOP_KEYS)})"
                )
            for fragment in child.iterdir():
                if fragment.name.startswith("."):
                    continue
                if fragment.is_dir() or fragment.suffix not in _YAML_SUFFIXES:
                    raise ConfigError(
                        f"{fragment}: unexpected file in {child.name}/ "
                        "(only .yml/.yaml fragments are loaded)"
                    )
                files.append((fragment, stem))
            continue
        if child.suffix not in _YAML_SUFFIXES:
            raise ConfigError(
                f"{child}: unexpected file in config directory (only .yml/.yaml are loaded)"
            )
        stem = child.stem
        if stem == "config":
            files.append((child, None))
        elif stem in KNOWN_TOP_KEYS:
            files.append((child, stem))
        else:
            raise ConfigError(
                f"{child}: unknown config file name (expected config.yml or one of: "
                f"{', '.join(k + '.yml' for k in KNOWN_TOP_KEYS)}, or a <key>.d/ directory)"
            )
    files.sort(key=lambda pair: str(pair[0]))
    return files


def _load_raw(path: Path) -> dict[str, Any]:
    raw: dict[str, Any] = {}
    if path.is_dir():
        for file_path, key in _collect_dir_files(path):
            if key is None:
                _contribute_file(raw, file_path)
            else:
                data = _read_yaml(file_path)
                if data is None:
                    continue
                _contribute(raw, key, _unwrap_fragment(file_path, key, data), file_path)
    elif path.is_file():
        _contribute_file(raw, path)
    else:
        raise ConfigError(f"{path}: config file or directory not found")
    return raw


# --------------------------------------------------------------------------
# ${ENV_VAR} interpolation


def _interpolate(value: Any, path: str) -> Any:
    if isinstance(value, str):

        def _replace(match: re.Match[str]) -> str:
            name = match.group(1)
            resolved = os.getenv(name)
            if not resolved:
                raise ConfigError(f"{path}: environment variable {name} is not set")
            return resolved

        return _ENV_RE.sub(_replace, value)
    if isinstance(value, dict):
        return {key: _interpolate(val, f"{path}.{key}") for key, val in value.items()}
    if isinstance(value, list):
        return [_interpolate(val, f"{path}[{index}]") for index, val in enumerate(value)]
    return value


# --------------------------------------------------------------------------
# validation / building


def _require_str(data: dict[str, Any], key: str, where: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{where}: '{key}' is required and must be a non-empty string")
    return value


def _optional_bool(data: dict[str, Any], key: str, where: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{where}: '{key}' must be true or false")
    return value


def _options(data: dict[str, Any], where: str, timeout: float) -> dict[str, Any]:
    options = data.get("options", {})
    if not isinstance(options, dict):
        raise ConfigError(f"{where}: 'options' must be a mapping")
    options = dict(options)
    options.setdefault("timeout", timeout)
    return options


def _check_keys(data: dict[str, Any], allowed: set[str], where: str) -> None:
    for key in data:
        if key not in allowed:
            raise ConfigError(
                f"{where}: unknown key '{key}' (allowed: {', '.join(sorted(allowed))})"
            )


def _build_entries(
    raw_entries: list[tuple[str, Any]],
    what: str,
    timeout: float,
    builder: Any,
) -> list[Any]:
    entries = []
    seen_ids: dict[str, str] = {}
    for index, (origin, data) in enumerate(raw_entries):
        where = f"{origin}: {what}[{index}]"
        if not isinstance(data, dict):
            raise ConfigError(f"{where}: entry must be a mapping")
        entry_id = _require_str(data, "id", where)
        where = f"{origin}: {what} '{entry_id}'"
        if entry_id in seen_ids:
            raise ConfigError(
                f"duplicate {what} id '{entry_id}' in {seen_ids[entry_id]} and {origin}"
            )
        seen_ids[entry_id] = origin
        entry_type = _require_str(data, "type", where)
        enabled = _optional_bool(data, "enabled", where, True)
        if enabled:
            data = _interpolate(data, where)
        entries.append(builder(data, entry_id, entry_type, enabled, where, origin, timeout))
    return entries


def _build_source(
    data: dict[str, Any],
    entry_id: str,
    entry_type: str,
    enabled: bool,
    where: str,
    origin: str,
    timeout: float,
) -> SourceConfig:
    _check_keys(data, {"id", "type", "enabled", "title", "emoji", "notify", "options"}, where)
    notify = data.get("notify")
    if notify is not None:
        if not isinstance(notify, list) or not all(isinstance(n, str) for n in notify):
            raise ConfigError(f"{where}: 'notify' must be a list of notifier ids")
        notify = tuple(notify)
    title = data.get("title", entry_id)
    if not isinstance(title, str):
        raise ConfigError(f"{where}: 'title' must be a string")
    emoji = data.get("emoji")
    if emoji is not None and not isinstance(emoji, str):
        raise ConfigError(f"{where}: 'emoji' must be a string")
    return SourceConfig(
        id=entry_id,
        type=entry_type,
        enabled=enabled,
        title=title,
        emoji=emoji,
        notify=notify,
        options=_options(data, where, timeout),
        origin=origin,
    )


def _build_notifier(
    data: dict[str, Any],
    entry_id: str,
    entry_type: str,
    enabled: bool,
    where: str,
    origin: str,
    timeout: float,
) -> NotifierConfig:
    _check_keys(data, {"id", "type", "enabled", "send_no_news", "options"}, where)
    return NotifierConfig(
        id=entry_id,
        type=entry_type,
        enabled=enabled,
        send_no_news=_optional_bool(data, "send_no_news", where, True),
        options=_options(data, where, timeout),
        origin=origin,
    )


def load_config(path: str | Path) -> Config:
    """Load and validate a config file or directory.

    Raises:
        ConfigError: with a message naming the offending file/key.
    """
    path = Path(path)
    raw = _load_raw(path)

    defaults = raw.get("defaults", {})
    _check_keys(defaults, {"timeout"}, f"{path}: defaults")
    timeout = defaults.get("timeout", 10)
    if not isinstance(timeout, (int, float)) or timeout <= 0:
        raise ConfigError(f"{path}: defaults.timeout must be a positive number")

    digest_raw = _interpolate(raw.get("digest", {}), f"{path}: digest")
    _check_keys(digest_raw, {"title", "intro"}, f"{path}: digest")
    digest = DigestConfig(
        title=digest_raw.get("title", DigestConfig.title),
        intro=digest_raw.get("intro", DigestConfig.intro),
    )

    if "state" not in raw:
        raise ConfigError(
            f"{path}: a 'state' block is required (backend + options); "
            "without persisted state every run would re-notify everything"
        )
    state_raw = _interpolate(raw["state"], f"{path}: state")
    _check_keys(state_raw, {"backend", "options"}, f"{path}: state")
    state = StateConfig(
        backend=_require_str(state_raw, "backend", f"{path}: state"),
        options=_options(state_raw, f"{path}: state", timeout),
    )

    sources = _build_entries(raw.get("sources", []), "source", timeout, _build_source)
    notifiers = _build_entries(raw.get("notifiers", []), "notifier", timeout, _build_notifier)

    notifier_ids = {n.id for n in notifiers}
    for source in sources:
        for target in source.notify or ():
            if target not in notifier_ids:
                raise ConfigError(
                    f"{source.origin}: source '{source.id}' routes to unknown "
                    f"notifier id '{target}'"
                )

    return Config(state=state, digest=digest, sources=tuple(sources), notifiers=tuple(notifiers))
