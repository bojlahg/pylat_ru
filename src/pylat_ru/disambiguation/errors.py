"""Exception hierarchy for the Russian disambiguation subsystem."""

from __future__ import annotations


class DisambiguationError(Exception):
    """Base exception for all disambiguation errors in pylat_ru."""


class DisambiguationResourceError(DisambiguationError):
    """Raised when a required disambiguation resource cannot be loaded or is invalid."""


class DisambiguationFormatError(DisambiguationError):
    """Raised when an XML disambiguation rule or multiwords resource has malformed syntax."""


class DisambiguationFilterError(DisambiguationError):
    """Raised when a Java disambiguation filter fails evaluation or is unsupported."""
