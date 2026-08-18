"""src/pylat_ru/morfologik/errors.py

Project-specific explicit exceptions for Morfologik FSA reading, metadata parsing,
sequence decoding, and dictionary operations.
"""

from __future__ import annotations


class MorfologikError(Exception):
    """Base exception for all Morfologik and dictionary related errors."""


class UnsupportedFSAFormatError(MorfologikError):
    """Raised when an FSA binary file has an unknown magic header or unsupported version."""


class CorruptedFSAError(MorfologikError):
    """Raised when FSA binary data is truncated, out-of-bounds, or structurally invalid."""


class InvalidMetadataError(MorfologikError):
    """Raised when dictionary .info metadata is missing required keys or contains malformed values."""


class UnsupportedEncoderError(MorfologikError):
    """Raised when dictionary metadata specifies an unsupported sequence encoder type."""


class UnsupportedEncodingError(MorfologikError):
    """Raised when dictionary metadata specifies an unsupported text character encoding."""


class MalformedSequenceError(MorfologikError):
    """Raised when an encoded stem/output sequence contains invalid or out-of-bounds trim codes."""
