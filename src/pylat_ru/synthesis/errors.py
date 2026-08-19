"""synthesis/errors.py

Exception classes for LanguageTool synthesis subsystem.
"""

from __future__ import annotations


class SynthesisError(Exception):
    """Base exception for all synthesis errors."""


class ManualSynthesizerFormatError(SynthesisError):
    """Raised when a manual synthesizer resource file has invalid syntax or format."""


class SynthesisResourceError(SynthesisError):
    """Raised when a required synthesis resource file is missing or unreadable."""
