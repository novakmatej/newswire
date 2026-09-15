"""State backends. Importing this package registers every built-in backend."""

from newswire.state import github_gist, local_file  # noqa: F401  (registrations)
from newswire.state.base import StateBackend, StateError

__all__ = ["StateBackend", "StateError"]
