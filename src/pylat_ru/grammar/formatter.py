"""src/pylat_ru/grammar/formatter.py

Message and suggestion template formatter with <match no="..."> resolution,
regex transformations, and LanguageTool-compatible capitalization adjustment.
"""

from __future__ import annotations

from typing import List, Sequence, Union
import regex

from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import (
    MatchReference,
    MessageTemplate,
    SuggestionTemplate,
)
from pylat_ru.tagging.string_tools import (
    change_first_char_case,
    is_all_uppercase,
    is_all_uppercase_tokens,
    is_capitalized_word,
    uppercase_first_char,
)


def _apply_match_conversions(tok_str: str, ref: MatchReference) -> str:
    """Apply regexp_match/regexp_replace and case_conversion to a token string."""
    res = tok_str
    if ref.regexp_match is not None and ref.regexp_replace is not None:
        try:
            # LanguageTool uses Java regex replacement syntax ($1, $2)
            res = regex.sub(ref.regexp_match, ref.regexp_replace, res)
        except Exception:
            pass

    if ref.case_conversion == "alllower":
        res = res.lower()
    elif ref.case_conversion == "allupper":
        res = res.upper()
    elif ref.case_conversion == "startlower":
        res = change_first_char_case(res) if res and res[0].isupper() else res
    elif ref.case_conversion in ("startupper", "firstupper"):
        res = uppercase_first_char(res)

    return res


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
                    tok_str = _apply_match_conversions(tok_str, elem)
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
                    tok_str = _apply_match_conversions(tok_str, elem)
                    parts.append(tok_str)
                else:
                    parts.append(f"\\{elem.no}")

        res = "".join(parts)
        if not res:
            return res

        # Adjust capitalization if the error tokens are all-uppercase or first token is capitalized
        if error_tokens:
            first_err = error_tokens[0].token or ""
            err_words = [t.token for t in error_tokens if t.token and not t.is_whitespace()]
            if is_all_uppercase_tokens(err_words) and len(first_err) > 1:
                res = res.upper()
            elif is_capitalized_word(first_err):
                res = uppercase_first_char(res)

        return res
