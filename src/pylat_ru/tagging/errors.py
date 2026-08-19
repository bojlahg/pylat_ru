"""Error classes for the tagging subsystem."""

from __future__ import annotations


class TaggerError(Exception):
    """Base exception for all tagging subsystem errors."""


class TaggerResourceError(TaggerError):
    """Raised when a required tagger resource is missing, unreadable, or corrupted."""


class ManualTaggerFormatError(TaggerError):
    """Raised when a manual dictionary file (added.txt, removed.txt) has invalid format or characters."""


class TaggerCompatibilityError(TaggerError):
    """Raised when an unsupported tagger feature or incompatible behavior is encountered."""
