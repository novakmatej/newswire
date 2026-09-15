"""State backend protocol: one JSON document keyed by source id."""

from __future__ import annotations

from typing import Any, Protocol


class StateError(RuntimeError):
    """Raised when state operations fail."""


class StateBackend(Protocol):
    def load(self) -> dict[str, Any]:
        """Return the state document ({} when none exists yet)."""
        ...

    def save(self, state: dict[str, Any]) -> None:
        """Persist the state document."""
        ...
