"""src/pylat_ru/grammar/matcher.py

Token sequence pattern matcher and predicate evaluator for core XML grammar rules.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple
import regex

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.grammar.model import (
    GrammarRule,
    Pattern,
    PatternToken,
    PatternTokenException,
)


class CompiledPatternToken:
    """Precompiled regexes and matcher for a single PatternToken."""

    def __init__(self, token: PatternToken) -> None:
        self.raw = token
        self.text = token.text
        self.postag = token.postag
        self.postag_regexp = token.postag_regexp
        self.regexp = token.regexp
        self.negate = token.negate
        self.negate_pos = token.negate_pos
        self.inflected = token.inflected
        self.case_sensitive = token.case_sensitive

        # Precompile text regex if applicable
        if self.regexp and self.text is not None:
            flags = 0 if self.case_sensitive else regex.IGNORECASE
            self._text_regex = regex.compile(f"^(?:{self.text})$", flags)
        else:
            self._text_regex = None

        # Precompile postag regex if applicable
        if self.postag_regexp and self.postag is not None:
            # POS tags in LT are always matched case-sensitively
            self._postag_regex = regex.compile(f"^(?:{self.postag})$")
        else:
            self._postag_regex = None

        # Compile exceptions
        self.compiled_exceptions = [
            CompiledTokenException(exc) for exc in token.exceptions if exc.scope == "current"
        ]

    def matches_token_readings(self, atr: AnalyzedTokenReadings) -> bool:
        """Check if AnalyzedTokenReadings satisfies this pattern token."""
        # 1. Token-level exception matching: if any current-token exception matches, token is rejected
        for exc in self.compiled_exceptions:
            for reading in atr.readings:
                if exc.matches_reading(reading, atr):
                    return False

        # 2. Check if any reading satisfies the pattern requirements
        for reading in atr.readings:
            if self._matches_single_reading(reading, atr):
                return True

        return False

    def _matches_single_reading(self, at: AnalyzedToken, atr: AnalyzedTokenReadings) -> bool:
        is_sentence_start = bool(getattr(atr, "is_sentence_start", False))

        # 1. Text / Lemma matching
        if self.text is not None:
            text_matched = False
            token_str = at.token if at.token is not None else atr.token

            if self.inflected:
                # Inflected: compare target with reading's lemma or token
                target = self.text if self.case_sensitive else self.text.lower()
                lemmas = []
                if at.lemma:
                    lemmas.append(at.lemma)
                if token_str:
                    lemmas.append(token_str)

                for lem in lemmas:
                    lem_cmp = lem if self.case_sensitive else lem.lower()
                    if self._text_regex is not None:
                        if self._text_regex.search(lem) is not None:
                            text_matched = True
                            break
                    else:
                        if lem_cmp == target:
                            text_matched = True
                            break
            elif self._text_regex is not None:
                # Check regex text match
                text_matched = self._text_regex.search(token_str) is not None
                if not text_matched and self.case_sensitive and is_sentence_start and token_str and token_str[0].isupper():
                    lowered_start = token_str[0].lower() + token_str[1:]
                    text_matched = self._text_regex.search(lowered_start) is not None
            else:
                if not self.case_sensitive:
                    text_matched = (token_str.lower() == self.text.lower())
                else:
                    if token_str == self.text:
                        text_matched = True
                    elif is_sentence_start and token_str and token_str[0].isupper():
                        lowered_start = token_str[0].lower() + token_str[1:]
                        text_matched = (lowered_start == self.text)
                    else:
                        text_matched = False

            if self.negate:
                text_matched = not text_matched

            if not text_matched:
                return False

        # 2. POS tag matching
        if self.postag is not None:
            pos_matched = False
            at_pos = at.pos_tag

            if at_pos is not None:
                if self._postag_regex is not None:
                    pos_matched = self._postag_regex.search(at_pos) is not None
                else:
                    pos_matched = (at_pos == self.postag)

            if self.negate_pos:
                pos_matched = not pos_matched

            if not pos_matched:
                return False

        return True


class CompiledTokenException:
    """Precompiled exception predicate."""

    def __init__(self, exc: PatternTokenException) -> None:
        self.raw = exc
        self.text = exc.text
        self.postag = exc.postag
        self.postag_regexp = exc.postag_regexp
        self.regexp = exc.regexp
        self.negate = exc.negate
        self.negate_pos = exc.negate_pos
        self.inflected = exc.inflected
        self.case_sensitive = exc.case_sensitive

        if self.regexp and self.text is not None:
            flags = 0 if self.case_sensitive else regex.IGNORECASE
            self._text_regex = regex.compile(f"^(?:{self.text})$", flags)
        else:
            self._text_regex = None

        if self.postag_regexp and self.postag is not None:
            self._postag_regex = regex.compile(f"^(?:{self.postag})$")
        else:
            self._postag_regex = None

    def matches_reading(self, at: AnalyzedToken, atr: AnalyzedTokenReadings) -> bool:
        # Check text
        if self.text is not None:
            token_str = at.token if at.token is not None else atr.token
            text_matched = False

            if self.inflected:
                target = self.text if self.case_sensitive else self.text.lower()
                lemmas = []
                if at.lemma:
                    lemmas.append(at.lemma)
                if token_str:
                    lemmas.append(token_str)

                for lem in lemmas:
                    lem_cmp = lem if self.case_sensitive else lem.lower()
                    if self._text_regex is not None:
                        if self._text_regex.search(lem) is not None:
                            text_matched = True
                            break
                    else:
                        if lem_cmp == target:
                            text_matched = True
                            break
            elif self._text_regex is not None:
                text_matched = self._text_regex.search(token_str) is not None
            else:
                if self.case_sensitive:
                    text_matched = (token_str == self.text)
                else:
                    text_matched = (token_str.lower() == self.text.lower())

            if self.negate:
                text_matched = not text_matched

            if not text_matched:
                return False

        # Check POS
        if self.postag is not None:
            pos_matched = False
            at_pos = at.pos_tag
            if at_pos is not None:
                if self._postag_regex is not None:
                    pos_matched = self._postag_regex.search(at_pos) is not None
                else:
                    pos_matched = (at_pos == self.postag)

            if self.negate_pos:
                pos_matched = not pos_matched

            if not pos_matched:
                return False

        return True


class CompiledPattern:
    """Compiled pattern with token elements and marker span boundaries."""

    def __init__(self, pattern: Pattern) -> None:
        self.raw = pattern
        self.tokens: List[CompiledPatternToken] = [
            CompiledPatternToken(t) for t in pattern.tokens
        ]
        self.has_marker = pattern.has_marker
        self.marker_start_idx = pattern.marker_start_idx
        self.marker_end_idx = pattern.marker_end_idx

    def match_at(
        self,
        non_blank_tokens: Sequence[AnalyzedTokenReadings],
        start_idx: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        """Attempt to match the compiled pattern starting at non_blank_tokens[start_idx].

        Returns (match_start, match_end, error_start, error_end) in non_blank_tokens indices,
        or None if no match.
        """
        pattern_len = len(self.tokens)
        if pattern_len == 0:
            return None
        if start_idx + pattern_len > len(non_blank_tokens):
            return None

        for offset in range(pattern_len):
            tok_pred = self.tokens[offset]
            token_reading = non_blank_tokens[start_idx + offset]
            if not tok_pred.matches_token_readings(token_reading):
                return None

        match_start = start_idx
        match_end = start_idx + pattern_len

        if self.has_marker and self.marker_start_idx is not None and self.marker_end_idx is not None:
            error_start = start_idx + self.marker_start_idx
            error_end = start_idx + self.marker_end_idx
        else:
            error_start = match_start
            error_end = match_end

        return match_start, match_end, error_start, error_end
