"""Pattern token matching engine for XML disambiguation rules with backtracking."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple, Union

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings


@dataclass
class PatternTokenException:
    """An exception condition within a pattern token."""

    string: Optional[str] = None
    is_regex: bool = False
    is_case_sensitive: bool = False
    is_negated: bool = False
    is_inflected: bool = False
    postag: Optional[str] = None
    is_postag_regex: bool = False
    is_postag_negated: bool = False
    scope: str = "current"  # "current" or "next"

    def __post_init__(self) -> None:
        self._compiled_regex: Optional[Pattern[str]] = None
        self._compiled_postag_regex: Optional[Pattern[str]] = None

        if self.string is not None and self.is_regex:
            flags = 0 if self.is_case_sensitive else re.IGNORECASE
            self._compiled_regex = re.compile(self.string, flags)

        if self.postag is not None:
            flags = 0 if self.is_case_sensitive else re.IGNORECASE
            if self.is_postag_regex:
                self._compiled_postag_regex = re.compile(self.postag, flags)
            else:
                self._compiled_postag_regex = re.compile(re.escape(self.postag), flags)

    def matches_reading(self, reading: AnalyzedToken) -> bool:
        """Check if a single morphology reading matches this exception."""
        text_matches = True
        if self.string is not None:
            target_str = reading.lemma if self.is_inflected and reading.lemma is not None else reading.token
            if self._compiled_regex is not None:
                text_matches = self._compiled_regex.fullmatch(target_str) is not None
            elif self.is_case_sensitive:
                text_matches = (target_str == self.string)
            else:
                text_matches = (target_str.lower() == self.string.lower())

            if self.is_negated:
                text_matches = not text_matches

        tag_matches = True
        if self.postag is not None:
            if reading.pos_tag is None:
                tag_matches = self.is_postag_negated
            else:
                if self._compiled_postag_regex is not None:
                    tag_matches = self._compiled_postag_regex.fullmatch(reading.pos_tag) is not None
                elif self.is_case_sensitive:
                    tag_matches = (reading.pos_tag == self.postag)
                else:
                    tag_matches = (reading.pos_tag.lower() == self.postag.lower())

                if self.is_postag_negated:
                    tag_matches = not tag_matches

        return text_matches and tag_matches

    def matches_token(self, token_readings: AnalyzedTokenReadings) -> bool:
        """Check if any reading in token_readings matches this exception."""
        return any(self.matches_reading(r) for r in token_readings.readings)


@dataclass
class PatternToken:
    """A pattern element representing match criteria for a single token position."""

    string: Optional[str] = None
    is_regex: bool = False
    is_case_sensitive: bool = False
    is_negated: bool = False
    is_inflected: bool = False
    postag: Optional[str] = None
    is_postag_regex: bool = False
    is_postag_negated: bool = False
    skip: int = 0
    is_inside_marker: bool = False
    min_occurrence: int = 1
    max_occurrence: int = 1

    and_tokens: List[PatternToken] = field(default_factory=list)
    exceptions: List[PatternTokenException] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._compiled_regex: Optional[Pattern[str]] = None
        self._compiled_postag_regex: Optional[Pattern[str]] = None

        if self.string is not None and self.is_regex:
            flags = 0 if self.is_case_sensitive else re.IGNORECASE
            self._compiled_regex = re.compile(self.string, flags)

        if self.postag is not None:
            flags = 0 if self.is_case_sensitive else re.IGNORECASE
            if self.is_postag_regex:
                self._compiled_postag_regex = re.compile(self.postag, flags)
            else:
                self._compiled_postag_regex = re.compile(re.escape(self.postag), flags)

    def matches_reading(self, reading: AnalyzedToken) -> bool:
        """Check if a single reading satisfies string and pos_tag criteria."""
        text_matches = True
        if self.string is not None:
            target_str = reading.lemma if self.is_inflected and reading.lemma is not None else reading.token
            if self._compiled_regex is not None:
                text_matches = self._compiled_regex.fullmatch(target_str) is not None
            elif self.is_case_sensitive:
                text_matches = (target_str == self.string)
            else:
                text_matches = (target_str.lower() == self.string.lower())

            if self.is_negated:
                text_matches = not text_matches

        tag_matches = True
        if self.postag is not None:
            if reading.pos_tag is None:
                tag_matches = self.is_postag_negated
            else:
                if self._compiled_postag_regex is not None:
                    tag_matches = self._compiled_postag_regex.fullmatch(reading.pos_tag) is not None
                elif self.is_case_sensitive:
                    tag_matches = (reading.pos_tag == self.postag)
                else:
                    tag_matches = (reading.pos_tag.lower() == self.postag.lower())

                if self.is_postag_negated:
                    tag_matches = not tag_matches

        return text_matches and tag_matches

    def matches_token(self, token_readings: AnalyzedTokenReadings) -> bool:
        """Check if token_readings satisfies this pattern token."""
        # 1. Check current-scope exceptions
        for exc in self.exceptions:
            if exc.scope == "current":
                if exc.matches_token(token_readings):
                    return False

        # 2. If <and> conjunction is present, each child condition must be satisfied by the token's readings
        if self.and_tokens:
            for sub_p in self.and_tokens:
                if not sub_p.matches_token(token_readings):
                    return False
            return True

        # 3. Check base criteria across token readings
        if self.string is None and self.postag is None:
            return True

        return any(self.matches_reading(r) for r in token_readings.readings)

    def matches_scope_next_exception_reading(self, reading: AnalyzedToken) -> bool:
        """Check whether one reading triggers a ``scope="next"`` exception.

        Pinned ``AbstractPatternRulePerformer.testAllReadings`` tests the *previous*
        element's next-scope exception against each reading of the token currently
        being considered whenever that previous element carried a ``skip``.
        """
        for exc in self.exceptions:
            if exc.scope != "next":
                continue
            if exc.matches_reading(reading):
                return True
        return False

    def matches_scope_next_exception(self, next_token: AnalyzedTokenReadings) -> bool:
        """Check if next_token triggers any scope='next' exception on this pattern token."""
        for exc in self.exceptions:
            if exc.scope == "next":
                if exc.matches_token(next_token):
                    return True
        return False


@dataclass
class RuleMatchResult:
    """Represents a successful match of a pattern rule over an AnalyzedSentence."""

    first_match_token: int
    last_match_token: int
    first_marker_match_token: int
    last_marker_match_token: int
    token_positions: List[int]
    matching_tokens_count: int


class PatternRuleMatcher:
    """Matches a sequence of PatternTokens against non-blank tokens in an AnalyzedSentence."""

    def __init__(self, pattern_tokens: Sequence[PatternToken]) -> None:
        self.pattern_tokens = list(pattern_tokens)
        self.pattern_size = len(self.pattern_tokens)

    def find_matches(self, sentence: AnalyzedSentence) -> List[RuleMatchResult]:
        """Find all match occurrences of the pattern in the sentence."""
        tokens = sentence.get_tokens_without_whitespace()
        n = len(tokens)
        results: List[RuleMatchResult] = []

        if self.pattern_size == 0 or n < self.pattern_size:
            return results

        for start_idx in range(n):
            match = self._match_from(start_idx, tokens)
            if match is not None:
                results.append(match)

        return results

    def _match_from(
        self, start_idx: int, tokens: Sequence[AnalyzedTokenReadings]
    ) -> Optional[RuleMatchResult]:
        """Attempt to match the pattern starting from start_idx with backtracking."""
        n = len(tokens)

        def match_step(
            p_idx: int,
            curr_pos: int,
            prev_skip: int,
            matched_indices: List[int],
        ) -> Optional[List[int]]:
            if p_idx == self.pattern_size:
                return matched_indices

            p_token = self.pattern_tokens[p_idx]
            max_skip = prev_skip if prev_skip >= 0 else (n - curr_pos)

            for skip_offset in range(max_skip + 1):
                cand_pos = curr_pos + skip_offset
                if cand_pos >= n:
                    break

                if p_token.matches_token(tokens[cand_pos]):
                    # Pinned AbstractPatternRulePerformer.testAllReadings: when the
                    # previous element carried a skip, its scope="next" exception is
                    # tested against the readings of *this* candidate token, not
                    # against the literal following token.  Only without a skip does
                    # the current element test its own next-exception against the
                    # first reading of the token that follows.
                    previous = self.pattern_tokens[p_idx - 1] if p_idx > 0 else None
                    if prev_skip > 0 and previous is not None:
                        if any(
                            previous.matches_scope_next_exception_reading(reading)
                            for reading in tokens[cand_pos].readings
                        ):
                            continue
                    elif prev_skip == 0 and cand_pos + 1 < n:
                        if p_token.matches_scope_next_exception(tokens[cand_pos + 1]):
                            continue

                    res = match_step(
                        p_idx + 1,
                        cand_pos + 1,
                        p_token.skip,
                        matched_indices + [cand_pos],
                    )
                    if res is not None:
                        return res

            return None

        matched_pos_list = match_step(0, start_idx, 0, [])
        if matched_pos_list is None:
            return None

        first_match = matched_pos_list[0]
        last_match = matched_pos_list[-1]
        first_marker = -1
        last_marker = -1

        token_positions: List[int] = []
        for k, pos in enumerate(matched_pos_list):
            p_tok = self.pattern_tokens[k]
            prev_p_pos = matched_pos_list[k - 1] if k > 0 else (start_idx - 1)
            token_positions.append(pos - prev_p_pos)
            if p_tok.is_inside_marker:
                if first_marker == -1:
                    first_marker = pos
                last_marker = pos

        if first_marker == -1:
            first_marker = first_match
            last_marker = last_match

        return RuleMatchResult(
            first_match_token=first_match,
            last_match_token=last_match,
            first_marker_match_token=first_marker,
            last_marker_match_token=last_marker,
            token_positions=token_positions,
            matching_tokens_count=len(token_positions),
        )
