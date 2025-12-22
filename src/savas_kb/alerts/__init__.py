"""Alerts module for detecting risks and opportunities."""

from .detector import AlertDetector
from .notifier import SlackNotifier

__all__ = ["AlertDetector", "SlackNotifier"]
