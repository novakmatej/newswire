"""Notifier types. Importing this package registers every built-in type."""

from newswire.notifiers import slack, teams  # noqa: F401  (registrations)
from newswire.notifiers.base import NotificationError, Notifier

__all__ = ["NotificationError", "Notifier"]
