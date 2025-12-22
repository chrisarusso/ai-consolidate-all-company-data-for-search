"""Ingestion module for loading data from various sources."""

from .slack_loader import SlackLoader
from .fathom_loader import FathomLoader

__all__ = ["SlackLoader", "FathomLoader"]
