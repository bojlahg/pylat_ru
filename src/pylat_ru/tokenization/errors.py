"""src/pylat_ru/tokenization/errors.py

Explicit error hierarchy for tokenization, SRX parsing, and offset accounting.
"""

from __future__ import annotations


class TokenizationError(Exception):
    """Base exception for all tokenization-related errors in pylat_ru."""


class SRXFormatError(TokenizationError):
    """Raised when an SRX resource or document is malformed or invalid."""


class SRXRuleCompilationError(TokenizationError):
    """Raised when an SRX regular expression pattern fails to compile."""


class UnsupportedSRXFeatureError(TokenizationError):
    """Raised when an unsupported SRX construct or extension is encountered."""


class WordTokenizationError(TokenizationError):
    """Raised when word tokenization encounters an invalid state or invariant failure."""
