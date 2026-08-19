"""src/pylat_ru/grammar/errors.py

Exception hierarchy for XML grammar loading, classification, and execution.
"""

from __future__ import annotations


class GrammarError(Exception):
    """Base exception for grammar subsystem errors."""


class GrammarFormatError(GrammarError):
    """Raised when grammar XML is structurally malformed or violates schema."""


class GrammarResourceError(GrammarError):
    """Raised when grammar resource files cannot be located or loaded."""


class UnsupportedGrammarFeatureError(GrammarError):
    """Raised when an unsupported XML feature/construct is encountered in strict mode."""

    def __init__(self, message: str, feature: str = "", rule_id: str = "") -> None:
        super().__init__(message)
        self.feature = feature
        self.rule_id = rule_id


class GrammarRuleDisabledError(GrammarError):
    """Raised when an attempt is made to execute a disabled grammar rule."""
