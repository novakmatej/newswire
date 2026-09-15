"""Plugin registries: ``type:`` in the config resolves through these dicts.

Adding a source/notifier/state-backend type is: write one module implementing
the protocol, decorate its factory with ``@source_type("name")`` (or
``@notifier_type`` / ``@state_backend``), import the module from the package
``__init__`` so registration runs. No orchestration edits.
"""

from __future__ import annotations

from typing import Any, Callable

from newswire.config import ConfigError

SOURCE_TYPES: dict[str, Callable[..., Any]] = {}
NOTIFIER_TYPES: dict[str, Callable[..., Any]] = {}
STATE_BACKENDS: dict[str, Callable[..., Any]] = {}


def _register(registry: dict[str, Callable[..., Any]], name: str) -> Callable[..., Any]:
    def decorator(factory: Callable[..., Any]) -> Callable[..., Any]:
        registry[name] = factory
        return factory

    return decorator


def source_type(name: str) -> Callable[..., Any]:
    return _register(SOURCE_TYPES, name)


def notifier_type(name: str) -> Callable[..., Any]:
    return _register(NOTIFIER_TYPES, name)


def state_backend(name: str) -> Callable[..., Any]:
    return _register(STATE_BACKENDS, name)


def resolve(registry: dict[str, Callable[..., Any]], name: str, what: str) -> Callable[..., Any]:
    try:
        return registry[name]
    except KeyError:
        known = ", ".join(sorted(registry)) or "none registered"
        raise ConfigError(f"unknown {what} type '{name}' (known: {known})") from None
