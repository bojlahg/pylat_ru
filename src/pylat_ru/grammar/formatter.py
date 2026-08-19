"""src/pylat_ru/grammar/formatter.py

Message and suggestion template formatter with <match no="..."> resolution
and LanguageTool-compatible capitalization adjustment.
"""

from __future__ import annotations

from typing import List, Sequence, Union

from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import (
    MatchReference,
    MessageTemplate,
    SuggestionTemplate,
)
from pylat_ru.tagging.string_tools import (
    is_all_uppercase,
    is_capitalized_word,
    uppercase_first_char,
)


class TemplateFormatter:
    """Renders structured message and suggestion templates using matched tokens."""

    @staticmethod
    def format_message(
        template: MessageTemplate,
        matched_tokens: Sequence[AnalyzedTokenReadings],
    ) -> str:
        """Format rule message replacing <match no="X"> references."""
        parts: List[str] = []
        for elem in template.elements:
            if isinstance(elem, str):
                parts.append(elem)
            elif isinstance(elem, MatchReference):
                token_idx = elem.no - 1
                if 0 <= token_idx < len(matched_tokens):
                    tok_str = matched_tokens[token_idx].token
                    parts.append(tok_str)
                else:
                    parts.append(f"\\{elem.no}")
        return "".join(parts)

    @staticmethod
    def format_suggestion(
        template: SuggestionTemplate,
        matched_tokens: Sequence[AnalyzedTokenReadings],
        error_tokens: Sequence[AnalyzedTokenReadings],
    ) -> str:
        """Format suggestion replacement string, applying capitalization matching Java LT."""
        parts: List[str] = []
        for elem in template.elements:
            if isinstance(elem, str):
                parts.append(elem)
            elif isinstance(elem, MatchReference):
                token_idx = elem.no - 1
                if 0 <= token_idx < len(matched_tokens):
                    tok_str = matched_tokens[token_idx].token
                    parts.append(tok_str)
                else:
                    parts.append(f"\\{elem.no}")

        res = "".join(parts)
        if not res:
            return res

        # Adjust capitalization if the first error token is capitalized or all-uppercase
        if error_tokens:
            first_err = error_tokens[0].token
            if is_all_uppercase(first_err) and len(first_err) > 1:
                res = res.upper()
            elif is_capitalized_word(first_err):
                res = uppercase_first_char(res)

        return res
