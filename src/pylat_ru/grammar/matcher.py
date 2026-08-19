"""src/pylat_ru/grammar/matcher.py

Advanced LanguageTool pattern matching engine implementing the complete
v6.8 AbstractPatternRulePerformer state machine, PatternTokenMatcher,
greedy repeat skipMaxTokens, skip lookaheads, scoped exceptions,
chunk matching, reading-aware <and> evaluation, antipattern immunization,
token-level dynamic match references, and RuleWithMaxFilter overlap pruning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union
import sys
import regex

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.grammar.errors import GrammarError, GrammarFormatError
from pylat_ru.grammar.model import (
    GrammarRule,
    MatchReference,
    Pattern,
    PatternAnd,
    PatternElement,
    PatternOr,
    PatternPhrase,
    PatternToken,
    PatternTokenException,
    PatternUnify,
    PatternUnifyIgnore,
)
from pylat_ru.grammar.unification import Unifier, UnifierConfiguration
from pylat_ru.synthesis.synthesizer import RussianSynthesizer


class CompiledTokenException:
    """Precompiled exception predicate with scope and whitespace awareness."""

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
        self.scope = exc.scope  # "current", "previous", "next"
        self.spacebefore = exc.spacebefore  # "yes", "no", or None
        self.raw_pos = exc.raw_pos
        self.match = exc.match

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
        """Evaluate exception against single token reading."""
        # 1. Whitespace before check
        if self.spacebefore is not None:
            has_ws = bool(getattr(atr, "whitespace_before", False))
            if self.spacebefore == "yes" and not has_ws:
                return False
            elif self.spacebefore == "no" and has_ws:
                return False

        # 2. Text / Lemma check
        if self.text is not None:
            token_str = at.token if at.token is not None else atr.token
            test_str = at.lemma if (self.inflected and at.lemma is not None) else token_str

            if self._text_regex is not None:
                text_matched = self._text_regex.fullmatch(test_str) is not None
            else:
                if self.case_sensitive:
                    text_matched = (test_str == self.text)
                else:
                    text_matched = (test_str.lower() == self.text.lower())

            if self.negate:
                text_matched = not text_matched

            if not text_matched:
                return False

        # 3. POS tag check
        if self.postag is not None:
            at_pos = at.pos_tag
            if at_pos == "SENT_END":
                at_pos = "SENT_END" if "SENT_END" in self.postag else None

            if at_pos is None:
                if self._postag_regex is not None:
                    pos_matched = (
                        self._postag_regex.fullmatch("UNKNOWN") is not None
                        or (getattr(atr, "is_sentence_end", False) and self._postag_regex.fullmatch("SENT_END") is not None)
                    )
                else:
                    pos_matched = (self.postag == "UNKNOWN") or (getattr(atr, "is_sentence_end", False) and self.postag == "SENT_END")
            else:
                if self._postag_regex is not None:
                    pos_matched = self._postag_regex.fullmatch(at_pos) is not None
                else:
                    pos_matched = (at_pos == self.postag)

            if self.negate_pos:
                pos_matched = not pos_matched

            if not pos_matched:
                return False

        return True


class CompiledPatternToken:
    """Compiled matcher for a pattern token supporting skip, min/max, chunk, AND, exceptions."""

    def __init__(
        self,
        token: PatternToken,
        and_tokens: Optional[List[PatternToken]] = None,
        and_exceptions: Optional[List[PatternTokenException]] = None,
    ) -> None:
        self.raw = token
        self.text = token.text
        self.postag = token.postag
        self.postag_regexp = token.postag_regexp
        self.regexp = token.regexp
        self.negate = token.negate
        self.negate_pos = token.negate_pos
        self.inflected = token.inflected
        self.case_sensitive = token.case_sensitive
        self.skip = token.skip
        self.min = token.min if token.min is not None else 1
        self.max = token.max if token.max is not None else 1
        self.chunk = token.chunk
        self.spacebefore = token.spacebefore
        self.raw_pos = token.raw_pos
        self.is_in_marker = token.is_in_marker
        self.match_ref = token.match

        # Unification metadata
        self.uni_features: Dict[str, List[str]] = dict(getattr(token, "uni_features", {}))
        self.is_unify: bool = bool(getattr(token, "is_unify", False))
        self.is_unify_negated: bool = bool(getattr(token, "is_unify_negated", False))
        self.is_unify_neutral: bool = bool(getattr(token, "is_unify_neutral", False))
        self.is_last_in_unify: bool = bool(getattr(token, "is_last_in_unify", False))

        # Dynamic match reference state (resolved per match attempt)
        self.dynamic_text: Optional[str] = None
        self.dynamic_postag: Optional[str] = None
        self.dynamic_text_regex: Optional[Any] = None
        self.dynamic_postag_regex: Optional[Any] = None

        # Precompile static text regex
        if self.regexp and self.text is not None:
            flags = 0 if self.case_sensitive else regex.IGNORECASE
            self._text_regex = regex.compile(f"^(?:{self.text})$", flags)
        else:
            self._text_regex = None

        # Precompile static postag regex
        if self.postag_regexp and self.postag is not None:
            self._postag_regex = regex.compile(f"^(?:{self.postag})$")
        else:
            self._postag_regex = None

        # Precompile chunk regex if applicable
        if self.chunk is not None:
            if any(c in self.chunk for c in (".*", "[", "]", "(", ")", "+", "?", "\\", "^", "$")):
                self._chunk_regex = regex.compile(f"^(?:{self.chunk})$")
            else:
                self._chunk_regex = None
        else:
            self._chunk_regex = None

        # Exceptions
        all_exceptions = list(token.exceptions)
        if and_exceptions:
            all_exceptions.extend(and_exceptions)

        self.exceptions = [CompiledTokenException(e) for e in all_exceptions]
        self.exceptions_current = [e for e in self.exceptions if e.scope == "current"]
        self.exceptions_previous = [e for e in self.exceptions if e.scope == "previous"]
        self.exceptions_next = [e for e in self.exceptions if e.scope == "next"]

        # AND group members
        and_list = list(and_tokens) if and_tokens else []
        if hasattr(token, "and_elements") and token.and_elements:
            for ae in token.and_elements:
                if isinstance(ae, PatternToken):
                    and_list.append(ae)

        if and_list:
            self.and_members = [CompiledPatternToken(t) for t in and_list]
            self.and_group_checks: List[bool] = [False] * len(self.and_members)
        else:
            self.and_members = []
            self.and_group_checks = []

    @property
    def is_unified(self) -> bool:
        return self.is_unify or self.is_unify_neutral

    def has_and_group(self) -> bool:
        return len(self.and_members) > 0

    def prepare_and_group(
        self,
        first_match_token: int,
        tokens: Sequence[AnalyzedTokenReadings],
        synthesizer: Optional[RussianSynthesizer] = None,
    ) -> None:
        """Reset AND group verification state for a candidate token."""
        for i in range(len(self.and_group_checks)):
            self.and_group_checks[i] = False
            self.and_members[i].resolve_reference(first_match_token, tokens, synthesizer)

    def add_member_and_group(self, at: AnalyzedToken, atr: AnalyzedTokenReadings) -> None:
        """Record matching AND members for a single reading."""
        for i, member in enumerate(self.and_members):
            if not self.and_group_checks[i]:
                if member.matches_reading(at, atr):
                    self.and_group_checks[i] = True

    def check_and_group(self, base_matched: bool) -> bool:
        """Verify that all members of AND group matched at least one reading."""
        if not base_matched:
            return False
        return all(self.and_group_checks)

    def resolve_reference(
        self,
        first_match_token: int,
        tokens: Sequence[AnalyzedTokenReadings],
        synthesizer: Optional[RussianSynthesizer] = None,
    ) -> None:
        """Dynamically resolve token-level <match> references if present."""
        self.dynamic_text = None
        self.dynamic_postag = None
        self.dynamic_text_regex = None
        self.dynamic_postag_regex = None

        if self.match_ref is None or first_match_token == -1:
            return

        ref_no = self.match_ref.no
        target_idx = first_match_token + ref_no  # 0-indexed token reference relative to first_match_token
        if target_idx < 0 or target_idx >= len(tokens):
            return

        ref_atr = tokens[target_idx]
        ref_at = ref_atr.readings[0] if ref_atr.readings else AnalyzedToken(ref_atr.token, None, None)

        synth = synthesizer or RussianSynthesizer.get_instance()
        target_pos = self.match_ref.postag

        if target_pos and self.match_ref.postag_regexp and self.match_ref.postag_replace:
            # POS replacement regex
            orig_pos = ref_at.pos_tag or ""
            target_pos = regex.sub(self.match_ref.postag, self.match_ref.postag_replace, orig_pos)

        if target_pos and synth:
            lemma = self.match_ref.lemma or ref_at.lemma or ref_at.token or ref_atr.token
            forms = synth.synthesize(lemma, target_pos)
            if forms:
                self.dynamic_text = forms[0]
                self.dynamic_postag = target_pos
            else:
                self.dynamic_text = ref_at.token
                self.dynamic_postag = target_pos
        else:
            self.dynamic_text = ref_at.token
            self.dynamic_postag = ref_at.pos_tag

    def matches_reading(self, at: AnalyzedToken, atr: AnalyzedTokenReadings) -> bool:
        """Evaluate core token predicate against a single reading."""
        # 1. Whitespace before check
        if self.spacebefore is not None:
            has_ws = bool(getattr(atr, "whitespace_before", False))
            if self.spacebefore == "yes" and not has_ws:
                return False
            elif self.spacebefore == "no" and has_ws:
                return False

        # 2. Text / Lemma matching
        target_text = self.dynamic_text if self.dynamic_text is not None else self.text
        if target_text is not None:
            token_str = at.token if at.token is not None else atr.token
            test_str = at.lemma if (self.inflected and at.lemma is not None) else token_str

            is_sent_start = bool(getattr(atr, "is_sentence_start", False))

            if self._text_regex is not None and self.dynamic_text is None:
                text_matched = self._text_regex.fullmatch(test_str) is not None
                if not text_matched and self.case_sensitive and is_sent_start and test_str and test_str[0].isupper():
                    lowered_start = test_str[0].lower() + test_str[1:]
                    text_matched = self._text_regex.fullmatch(lowered_start) is not None
            else:
                if not self.case_sensitive:
                    text_matched = (test_str.lower() == target_text.lower())
                else:
                    if test_str == target_text:
                        text_matched = True
                    elif is_sent_start and test_str and test_str[0].isupper():
                        lowered_start = test_str[0].lower() + test_str[1:]
                        text_matched = (lowered_start == target_text)
                    else:
                        text_matched = False

            if self.negate:
                text_matched = not text_matched

            if not text_matched:
                return False

        # 3. POS tag matching
        target_pos = self.dynamic_postag if self.dynamic_postag is not None else self.postag
        if target_pos is not None:
            at_pos = at.pos_tag
            if at_pos == "SENT_END":
                at_pos = "SENT_END" if "SENT_END" in target_pos else None

            if at_pos is None:
                if self._postag_regex is not None and self.dynamic_postag is None:
                    pos_matched = (
                        self._postag_regex.fullmatch("UNKNOWN") is not None
                        or (getattr(atr, "is_sentence_end", False) and self._postag_regex.fullmatch("SENT_END") is not None)
                    )
                else:
                    pos_matched = (target_pos == "UNKNOWN") or (getattr(atr, "is_sentence_end", False) and target_pos == "SENT_END")
            else:
                if self._postag_regex is not None and self.dynamic_postag is None:
                    pos_matched = self._postag_regex.fullmatch(at_pos) is not None
                else:
                    pos_matched = (at_pos == target_pos)

            if self.negate_pos:
                pos_matched = not pos_matched

            if not pos_matched:
                return False

        return True

    def matches_chunk(self, atr: AnalyzedTokenReadings) -> bool:
        """Evaluate chunk tag matching on AnalyzedTokenReadings."""
        if self.chunk is None:
            return True

        chunk_tags = getattr(atr, "chunk_tags", []) or []
        if not chunk_tags:
            return self.negate  # if negate, absence of chunk matches

        matched = False
        for ctag in chunk_tags:
            if self._chunk_regex is not None:
                if self._chunk_regex.fullmatch(ctag) is not None:
                    matched = True
                    break
            else:
                if ctag == self.chunk:
                    matched = True
                    break

        if self.negate:
            return not matched
        return matched

    def matches_current_exception(self, at: AnalyzedToken, atr: AnalyzedTokenReadings) -> bool:
        """Check if any current-scope exception matches."""
        for exc in self.exceptions_current:
            if exc.matches_reading(at, atr):
                return True
        return False

    def matches_previous_exception(self, prev_atr: AnalyzedTokenReadings) -> bool:
        """Check if any previous-scope exception matches previous token."""
        for exc in self.exceptions_previous:
            for reading in prev_atr.readings:
                if exc.matches_reading(reading, prev_atr):
                    return True
        return False

    def matches_next_exception(self, next_atr: AnalyzedTokenReadings) -> bool:
        """Check if any next-scope exception matches next token."""
        for exc in self.exceptions_next:
            for reading in next_atr.readings:
                if exc.matches_reading(reading, next_atr):
                    return True
        return False

    def matches_scope_next(self, next_at: AnalyzedToken, next_atr: AnalyzedTokenReadings) -> bool:
        """Check if any next-scope exception matches next token reading."""
        for exc in self.exceptions_next:
            if exc.matches_reading(next_at, next_atr):
                return True
        return False

    def matches_token_readings(
        self,
        atr: AnalyzedTokenReadings,
        prev_atr: Optional[AnalyzedTokenReadings] = None,
        next_atr: Optional[AnalyzedTokenReadings] = None,
    ) -> bool:
        """Evaluate whether this compiled pattern token matches an AnalyzedTokenReadings."""
        if not self.matches_chunk(atr):
            return False

        if prev_atr is not None and self.matches_previous_exception(prev_atr):
            return False

        if next_atr is not None and self.matches_next_exception(next_atr):
            return False

        readings = atr.readings or [AnalyzedToken(atr.token)]
        for at in readings:
            if self.matches_reading(at, atr):
                if not self.matches_current_exception(at, atr):
                    return True

        return False


@dataclass
class MatchStateResult:
    """Raw pattern match result containing token positions and marker spans."""

    token_positions: List[int]
    first_match_token: int  # 0-indexed token index in sentence tokens
    last_match_token: int   # 0-indexed inclusive token index
    first_marker_token: int # 0-indexed token index
    last_marker_token: int  # 0-indexed inclusive token index
    match_start_idx: int    # 0-indexed
    match_end_idx: int      # 0-indexed exclusive
    error_start_idx: int    # 0-indexed
    error_end_idx: int      # 0-indexed exclusive
    filtered_tokens: Optional[List[AnalyzedTokenReadings]] = None


class CompiledRuleVariant:
    """Executable pattern rule variant corresponding to Java AbstractPatternRule."""

    def __init__(
        self,
        source_rule: GrammarRule,
        variant_idx: int,
        tokens: List[CompiledPatternToken],
        element_lengths: List[int],
        has_marker: bool,
        marker_start_idx: Optional[int],
        marker_end_idx: Optional[int],
        raw_pos: bool = False,
        antipatterns: Optional[List[CompiledRuleVariant]] = None,
        minprevmatches: Optional[int] = None,
        distancetokens: Optional[int] = None,
        unifier_config: Optional[UnifierConfiguration] = None,
    ) -> None:
        self.source_rule = source_rule
        self.variant_idx = variant_idx
        self.tokens = tokens
        self.element_lengths = element_lengths
        self.has_marker = has_marker or any(t.is_in_marker for t in self.tokens)
        self.marker_start_idx = marker_start_idx
        self.marker_end_idx = marker_end_idx
        self.raw_pos = raw_pos
        self.antipatterns = antipatterns or []
        self.minprevmatches = minprevmatches
        self.distancetokens = distancetokens
        self.unifier_config = unifier_config
        self.unifier: Optional[Unifier] = unifier_config.create_unifier() if unifier_config is not None else None
        self.has_unification = any(t.is_unified for t in self.tokens)
        self.min_occur_correction = sum(1 for t in self.tokens if t.min == 0)
        self.is_sent_start = (
            len(self.tokens) > 0
            and self.tokens[0].postag == "SENT_START"
            and not self.tokens[0].negate_pos
        )

    def match_sentence(
        self,
        sentence: AnalyzedSentence,
        synthesizer: Optional[RussianSynthesizer] = None,
        immunized_tokens: Optional[Set[int]] = None,
    ) -> List[MatchStateResult]:
        """Scan sentence tokens and find all matching pattern occurrences."""
        # 1. Select token stream based on raw_pos
        all_tokens = sentence.pre_disambig_tokens if self.raw_pos else sentence.tokens

        # 2. Filter non-blank tokens (keeping SENT_START if present)
        non_blank_tokens: List[AnalyzedTokenReadings] = []
        for t in all_tokens:
            if t.has_pos_tag("SENT_START"):
                non_blank_tokens.append(t)
            elif t.token and not t.is_whitespace():
                non_blank_tokens.append(t)

        if not non_blank_tokens:
            return []

        # 3. Limit start position: if is_sent_start -> only index 0
        limit = (
            1
            if self.is_sent_start
            else max(0, len(non_blank_tokens) - len(self.tokens) + 1) + self.min_occur_correction
        )

        results: List[MatchStateResult] = []
        imm_set = immunized_tokens or set()

        for start_idx in range(min(limit, len(non_blank_tokens))):
            m_res = self._match_from(
                tokens=non_blank_tokens,
                start_idx=start_idx,
                synthesizer=synthesizer,
                immunized_tokens=imm_set,
            )
            if m_res is not None:
                results.append(m_res)

        return results

    def reset_dynamic_state(self) -> None:
        """Reset all dynamic token reference states across compiled tokens."""
        for tok in self.tokens:
            tok.dynamic_text = None
            tok.dynamic_postag = None
            tok.dynamic_text_regex = None
            tok.dynamic_postag_regex = None

    def _match_from(
        self,
        tokens: Sequence[AnalyzedTokenReadings],
        start_idx: int,
        synthesizer: Optional[RussianSynthesizer],
        immunized_tokens: Set[int],
    ) -> Optional[MatchStateResult]:
        """Attempt matching from start_idx using the LT state machine."""
        self.reset_dynamic_state()
        pattern_size = len(self.tokens)
        token_positions = [0] * pattern_size
        skip_shift_total = 0
        min_occur_skip = 0
        prev_skip_next = 0

        first_match_token = -1
        last_match_token = -1
        first_marker_match_token = -1
        last_marker_match_token = -1
        all_elements_match = False
        matching_tokens = 0

        to_unify: Dict[CompiledPatternToken, List[List[AnalyzedToken]]] = {}
        neutral_readings: Dict[CompiledPatternToken, List[AnalyzedTokenReadings]] = {}

        prev_token_matcher: Optional[CompiledPatternToken] = None
        p_token_matcher: Optional[CompiledPatternToken] = None

        for k in range(pattern_size):
            prev_token_matcher = p_token_matcher
            p_token_matcher = self.tokens[k]
            p_token_matcher.resolve_reference(first_match_token, tokens, synthesizer)

            next_pos = start_idx + k + skip_shift_total - min_occur_skip
            all_elements_match = False
            prev_matched = False

            if prev_skip_next + next_pos >= len(tokens) or prev_skip_next < 0:
                prev_skip_next = len(tokens) - (next_pos + 1)

            max_tok = min(
                next_pos + prev_skip_next,
                len(tokens) - (pattern_size - k) + self.min_occur_correction,
            )

            for m in range(next_pos, max_tok + 1):
                all_elements_match, prev_matched, readings_to_unify = self._test_all_readings(
                    tokens=tokens,
                    matcher=p_token_matcher,
                    prev_element=prev_token_matcher,
                    token_no=m,
                    first_match_token=first_match_token,
                    prev_skip_next=prev_skip_next,
                    prev_matched=prev_matched,
                    immunized_tokens=immunized_tokens,
                )

                # Optional element lookahead check
                if p_token_matcher.min == 0:
                    found_next = False
                    for k2 in range(k + 1, pattern_size):
                        next_elem = self.tokens[k2]
                        next_elem_match, _, _ = self._test_all_readings(
                            tokens=tokens,
                            matcher=next_elem,
                            prev_element=p_token_matcher,
                            token_no=m,
                            first_match_token=first_match_token,
                            prev_skip_next=prev_skip_next,
                            prev_matched=False,
                            immunized_tokens=immunized_tokens,
                        )
                        if next_elem_match:
                            all_elements_match = True
                            min_occur_skip += 1
                            token_positions[matching_tokens] = 0
                            matching_tokens += 1
                            found_next = True
                            break
                        elif next_elem.min > 0:
                            break
                    if found_next:
                        break

                if prev_matched:
                    break

                if all_elements_match:
                    if p_token_matcher.is_unify_neutral:
                        neutral_readings.setdefault(p_token_matcher, []).append(tokens[m])
                    if p_token_matcher.is_unify and readings_to_unify:
                        to_unify.setdefault(p_token_matcher, []).append(readings_to_unify)

                    skip_for_max = self._skip_max_tokens(
                        tokens=tokens,
                        matcher=p_token_matcher,
                        prev_element=prev_token_matcher,
                        m=m,
                        first_match_token=first_match_token,
                        prev_skip_next=prev_skip_next,
                        remaining_elems=pattern_size - k - 1,
                        immunized_tokens=immunized_tokens,
                        to_unify=to_unify,
                        neutral_readings=neutral_readings,
                    )
                    last_match_token = m + skip_for_max
                    skip_shift = last_match_token - next_pos
                    token_positions[matching_tokens] = skip_shift + 1
                    matching_tokens += 1
                    prev_skip_next = p_token_matcher.skip if p_token_matcher.skip is not None else 0
                    skip_shift_total += skip_shift

                    if first_match_token == -1:
                        first_match_token = last_match_token - skip_for_max
                    if first_marker_match_token == -1 and p_token_matcher.is_in_marker:
                        first_marker_match_token = last_match_token - skip_for_max
                    if p_token_matcher.is_in_marker:
                        last_marker_match_token = last_match_token
                    break

            if not all_elements_match:
                break

        if all_elements_match and matching_tokens == pattern_size:
            filtered_tokens: Optional[List[AnalyzedTokenReadings]] = None
            if self.has_unification:
                uni_ok, filtered_tokens = self._test_unification(to_unify, neutral_readings)
                if not uni_ok:
                    return None

            # Compute match and error spans
            match_start = first_match_token
            match_end = last_match_token + 1

            if self.has_marker and first_marker_match_token != -1 and last_marker_match_token != -1:
                error_start = first_marker_match_token
                error_end = last_marker_match_token + 1
            else:
                error_start = match_start
                error_end = match_end

            return MatchStateResult(
                token_positions=token_positions,
                first_match_token=first_match_token,
                last_match_token=last_match_token,
                first_marker_token=first_marker_match_token,
                last_marker_token=last_marker_match_token,
                match_start_idx=match_start,
                match_end_idx=match_end,
                error_start_idx=error_start,
                error_end_idx=error_end,
                filtered_tokens=filtered_tokens,
            )

        return None

    def _test_all_readings(
        self,
        tokens: Sequence[AnalyzedTokenReadings],
        matcher: CompiledPatternToken,
        prev_element: Optional[CompiledPatternToken],
        token_no: int,
        first_match_token: int,
        prev_skip_next: int,
        prev_matched: bool,
        immunized_tokens: Set[int],
    ) -> Tuple[bool, bool, List[AnalyzedToken]]:
        """Evaluate token matching across readings, scopes, chunks, and AND groups."""
        if token_no in immunized_tokens:
            return False, prev_matched, []

        atr = tokens[token_no]
        readings = atr.readings
        if not readings:
            return False, prev_matched, []

        # Prepare AND group
        if matcher.has_and_group():
            matcher.prepare_and_group(first_match_token, tokens)

        for i, match_token in enumerate(readings):
            # Check scope="next" from prev_element when prev_skip_next > 0
            if prev_skip_next > 0 and prev_element is not None:
                if prev_element.matches_scope_next(match_token, atr):
                    prev_matched = True

            # Check scope="next" on matcher when prev_skip_next == 0 and token_no + 1 < len(tokens)
            if prev_skip_next == 0 and token_no + 1 < len(tokens):
                next_atr = tokens[token_no + 1]
                if next_atr.readings:
                    if matcher.matches_scope_next(next_atr.readings[0], next_atr):
                        prev_matched = True

            if prev_matched:
                return False, True, []

        any_matched = False
        readings_to_unify: List[AnalyzedToken] = []
        for match_token in readings:
            reading_matches = matcher.matches_reading(match_token, atr)
            if reading_matches:
                any_matched = True
                if matcher.is_unify and not matcher.is_unify_neutral:
                    readings_to_unify.append(match_token)
            if matcher.has_and_group():
                matcher.add_member_and_group(match_token, atr)

        if matcher.has_and_group():
            if not matcher.check_and_group(any_matched):
                return False, prev_matched, []
        elif not any_matched:
            return False, prev_matched, []

        # Current-scope exceptions
        for match_token in readings:
            if matcher.matches_current_exception(match_token, atr):
                return False, prev_matched, []

        # Previous-scope exceptions
        if token_no > 0 and matcher.exceptions_previous:
            prev_atr = tokens[token_no - 1]
            if matcher.matches_previous_exception(prev_atr):
                return False, prev_matched, []

        # Chunk matching
        if not matcher.matches_chunk(atr):
            return False, prev_matched, []

        return True, prev_matched, readings_to_unify

    def _skip_max_tokens(
        self,
        tokens: Sequence[AnalyzedTokenReadings],
        matcher: CompiledPatternToken,
        prev_element: Optional[CompiledPatternToken],
        m: int,
        first_match_token: int,
        prev_skip_next: int,
        remaining_elems: int,
        immunized_tokens: Set[int],
        to_unify: Optional[Dict[CompiledPatternToken, List[List[AnalyzedToken]]]] = None,
        neutral_readings: Optional[Dict[CompiledPatternToken, List[AnalyzedTokenReadings]]] = None,
    ) -> int:
        """Skip repeated matches up to maxOccurrences matching Java LT AbstractPatternRulePerformer."""
        max_skip = 0
        max_occurrences = matcher.max if (matcher.max is not None and matcher.max != -1) else sys.maxsize

        for j in range(1, max_occurrences):
            if m + j >= len(tokens) - remaining_elems:
                break
            next_match, _, rep_readings = self._test_all_readings(
                tokens=tokens,
                matcher=matcher,
                prev_element=prev_element,
                token_no=m + j,
                first_match_token=first_match_token,
                prev_skip_next=prev_skip_next,
                prev_matched=False,
                immunized_tokens=immunized_tokens,
            )
            if next_match:
                if to_unify is not None and matcher.is_unify and rep_readings:
                    to_unify.setdefault(matcher, []).append(rep_readings)
                if neutral_readings is not None and matcher.is_unify_neutral:
                    neutral_readings.setdefault(matcher, []).append(tokens[m + j])
                max_skip += 1
            else:
                break

        return max_skip

    def _test_unification(
        self,
        to_unify: Dict[CompiledPatternToken, List[List[AnalyzedToken]]],
        neutral_readings: Dict[CompiledPatternToken, List[AnalyzedTokenReadings]],
    ) -> Tuple[bool, Optional[List[AnalyzedTokenReadings]]]:
        """Perform feature unification agreement check across matched candidate tokens."""
        if self.unifier is None:
            return True, None

        self.unifier.reset()
        final_unified: Optional[List[AnalyzedTokenReadings]] = None

        for matcher in self.tokens:
            neutral = neutral_readings.get(matcher)
            if neutral is not None:
                for atr in neutral:
                    self.unifier.add_neutral_element(atr)
                continue

            reading_sets = to_unify.get(matcher)
            if reading_sets is None:
                continue

            for readings in reading_sets:
                any_matched = False
                for i, match_token in enumerate(readings):
                    is_last_reading = (i == len(readings) - 1)
                    res = self.unifier.is_unified(match_token, matcher.uni_features, is_last_reading, True)
                    any_matched = any_matched or res

                if matcher.is_unify_negated and any_matched:
                    return False, None

                if matcher.is_last_in_unify and readings == reading_sets[-1]:
                    if not any_matched and not matcher.is_unify_negated:
                        return False, None
                    final_unified = self.unifier.get_final_unified()
                    self.unifier.reset()

        return True, final_unified

def expand_rule_into_variants(
    rule: GrammarRule,
    global_phrases: Dict[str, PatternPhrase],
    unifier_config: Optional[UnifierConfiguration] = None,
) -> List[CompiledRuleVariant]:
    """Recursively expand <or> and <phrase> into physical rule variants matching Java LT."""
    # 1. Expand pattern elements into Cartesian product of token sequences
    pattern_elements = rule.pattern.elements if rule.pattern.elements else (rule.pattern.tokens or [])
    expanded_branches = _expand_pattern_elements(pattern_elements, global_phrases)

    # 2. Expand antipatterns if present
    compiled_antipatterns: List[CompiledRuleVariant] = []
    for ap_idx, ap in enumerate(rule.antipatterns):
        ap_elements = ap.elements if ap.elements else (ap.tokens or [])
        ap_branches = _expand_pattern_elements(ap_elements, global_phrases)
        for ap_b_tokens, ap_b_lens in ap_branches:
            ap_compiled_tokens = [CompiledPatternToken(t) for t in ap_b_tokens]
            compiled_antipatterns.append(
                CompiledRuleVariant(
                    source_rule=rule,
                    variant_idx=ap_idx,
                    tokens=ap_compiled_tokens,
                    element_lengths=ap_b_lens,
                    has_marker=ap.has_marker,
                    marker_start_idx=ap.marker_start_idx,
                    marker_end_idx=ap.marker_end_idx,
                    raw_pos=ap.raw_pos,
                    unifier_config=unifier_config,
                )
            )

    # 3. Create CompiledRuleVariant for each physical branch
    variants: List[CompiledRuleVariant] = []
    for v_idx, (b_tokens, b_lens) in enumerate(expanded_branches):
        compiled_tokens = [CompiledPatternToken(t) for t in b_tokens]
        variants.append(
            CompiledRuleVariant(
                source_rule=rule,
                variant_idx=v_idx,
                tokens=compiled_tokens,
                element_lengths=b_lens,
                has_marker=rule.pattern.has_marker,
                marker_start_idx=rule.pattern.marker_start_idx,
                marker_end_idx=rule.pattern.marker_end_idx,
                raw_pos=rule.pattern.raw_pos,
                antipatterns=compiled_antipatterns,
                minprevmatches=rule.minprevmatches,
                distancetokens=rule.distancetokens,
                unifier_config=unifier_config,
            )
        )

    return variants


def _expand_pattern_elements(
    elements: Sequence[PatternElement],
    global_phrases: Dict[str, PatternPhrase],
    in_marker_override: Optional[bool] = None,
) -> List[Tuple[List[PatternToken], List[int]]]:
    """Cartesian expansion of PatternElements into (token_list, element_lengths)."""
    if not elements:
        return [([], [])]

    first = elements[0]
    rest_variants = _expand_pattern_elements(
        elements[1:], global_phrases, in_marker_override=in_marker_override
    )
    first_branches = _expand_single_element(
        first, global_phrases, in_marker_override=in_marker_override
    )

    combined: List[Tuple[List[PatternToken], List[int]]] = []
    for f_tokens, f_len in first_branches:
        for r_tokens, r_lens in rest_variants:
            combined.append((f_tokens + r_tokens, [f_len] + r_lens))

    return combined


def _flatten_and_to_tokens(and_elem: PatternAnd) -> List[PatternToken]:
    """Flatten PatternAnd into tokens preserving member predicates and exceptions."""
    primary_token: Optional[PatternToken] = None
    and_tokens: List[PatternToken] = []

    for child in and_elem.elements:
        if isinstance(child, PatternToken):
            if primary_token is None:
                primary_token = child
            else:
                and_tokens.append(child)

    if primary_token is not None:
        merged_exceptions = list(primary_token.exceptions) + list(and_elem.exceptions)
        return [
            PatternToken(
                text=primary_token.text,
                postag=primary_token.postag,
                postag_regexp=primary_token.postag_regexp,
                regexp=primary_token.regexp,
                negate=primary_token.negate,
                negate_pos=primary_token.negate_pos,
                inflected=primary_token.inflected,
                case_sensitive=primary_token.case_sensitive,
                skip=primary_token.skip,
                min=primary_token.min,
                max=primary_token.max,
                chunk=primary_token.chunk,
                spacebefore=primary_token.spacebefore,
                raw_pos=primary_token.raw_pos,
                is_in_marker=and_elem.is_in_marker,
                match=primary_token.match,
                exceptions=merged_exceptions,
                and_elements=and_tokens,
            )
        ]

    return [PatternToken(is_in_marker=and_elem.is_in_marker)]


def _expand_single_element(
    elem: PatternElement,
    global_phrases: Dict[str, PatternPhrase],
    in_marker_override: Optional[bool] = None,
) -> List[Tuple[List[PatternToken], int]]:
    """Expand a single PatternElement into a list of (branch_tokens, logical_element_length)."""
    effective_marker = True if (in_marker_override or getattr(elem, "is_in_marker", False)) else None

    if isinstance(elem, PatternToken):
        tok = elem
        if in_marker_override is not None and tok.is_in_marker != in_marker_override:
            tok = PatternToken(
                text=tok.text,
                postag=tok.postag,
                postag_regexp=tok.postag_regexp,
                regexp=tok.regexp,
                negate=tok.negate,
                negate_pos=tok.negate_pos,
                inflected=tok.inflected,
                case_sensitive=tok.case_sensitive,
                skip=tok.skip,
                min=tok.min,
                max=tok.max,
                chunk=tok.chunk,
                spacebefore=tok.spacebefore,
                raw_pos=tok.raw_pos,
                is_in_marker=in_marker_override,
                match=tok.match,
                exceptions=tok.exceptions,
                and_elements=tok.and_elements,
                uni_features=tok.uni_features,
                is_unify=tok.is_unify,
                is_unify_negated=tok.is_unify_negated,
                is_unify_neutral=tok.is_unify_neutral,
                is_last_in_unify=tok.is_last_in_unify,
            )
        return [([tok], 1)]

    elif isinstance(elem, PatternAnd):
        toks = _flatten_and_to_tokens(elem)
        if in_marker_override is not None:
            for t in toks:
                t.is_in_marker = in_marker_override
        return [(toks, 1)]

    elif isinstance(elem, PatternOr):
        branches: List[Tuple[List[PatternToken], int]] = []
        ordered_elements = list(elem.elements[1:]) + [elem.elements[0]] if len(elem.elements) > 1 else elem.elements
        for opt in ordered_elements:
            for opt_tokens, opt_len in _expand_single_element(opt, global_phrases, in_marker_override=effective_marker):
                branches.append((opt_tokens, opt_len))
        return branches

    elif isinstance(elem, PatternPhrase):
        pref = elem.ref or elem.id
        if not pref or pref not in global_phrases:
            raise GrammarFormatError(f"Undefined or missing phrase reference '{pref}' in pattern")
        target_phrase = global_phrases[pref]
        phrase_expansions = _expand_pattern_elements(
            target_phrase.elements, global_phrases, in_marker_override=effective_marker
        )
        branches = []
        for p_tokens, _ in phrase_expansions:
            branches.append((p_tokens, len(p_tokens)))
        return branches

    elif isinstance(elem, PatternUnify):
        uni_features = {f.name: list(f.types) for f in elem.features}
        unify_expansions = _expand_pattern_elements(
            elem.elements, global_phrases, in_marker_override=effective_marker
        )
        branches = []
        for u_tokens, _ in unify_expansions:
            expanded_tokens = []
            for tok in u_tokens:
                if tok.min is not None and tok.min > 1:
                    for _ in range(tok.min):
                        expanded_tokens.append(
                            PatternToken(
                                text=tok.text,
                                postag=tok.postag,
                                postag_regexp=tok.postag_regexp,
                                regexp=tok.regexp,
                                negate=tok.negate,
                                negate_pos=tok.negate_pos,
                                inflected=tok.inflected,
                                case_sensitive=tok.case_sensitive,
                                skip=tok.skip,
                                min=1,
                                max=tok.max,
                                chunk=tok.chunk,
                                spacebefore=tok.spacebefore,
                                raw_pos=tok.raw_pos,
                                is_in_marker=tok.is_in_marker,
                                match=tok.match,
                                exceptions=tok.exceptions,
                                and_elements=tok.and_elements,
                                uni_features=dict(uni_features) if not tok.is_unify_neutral else {},
                                is_unify=True if not tok.is_unify_neutral else False,
                                is_unify_neutral=tok.is_unify_neutral,
                            )
                        )
                else:
                    expanded_tokens.append(
                        PatternToken(
                            text=tok.text,
                            postag=tok.postag,
                            postag_regexp=tok.postag_regexp,
                            regexp=tok.regexp,
                            negate=tok.negate,
                            negate_pos=tok.negate_pos,
                            inflected=tok.inflected,
                            case_sensitive=tok.case_sensitive,
                            skip=tok.skip,
                            min=tok.min,
                            max=tok.max,
                            chunk=tok.chunk,
                            spacebefore=tok.spacebefore,
                            raw_pos=tok.raw_pos,
                            is_in_marker=tok.is_in_marker,
                            match=tok.match,
                            exceptions=tok.exceptions,
                            and_elements=tok.and_elements,
                            uni_features=dict(uni_features) if not tok.is_unify_neutral else {},
                            is_unify=True if not tok.is_unify_neutral else False,
                            is_unify_neutral=tok.is_unify_neutral,
                        )
                    )
            if expanded_tokens:
                last_tok = expanded_tokens[-1]
                last_tok.is_last_in_unify = True
                if elem.negate:
                    last_tok.is_unify_negated = True
            branches.append((expanded_tokens, len(expanded_tokens)))
        return branches

    elif isinstance(elem, PatternUnifyIgnore):
        ignore_expansions = _expand_pattern_elements(
            elem.elements, global_phrases, in_marker_override=effective_marker
        )
        branches = []
        for i_tokens, _ in ignore_expansions:
            expanded_tokens = []
            for tok in i_tokens:
                expanded_tokens.append(
                    PatternToken(
                        text=tok.text,
                        postag=tok.postag,
                        postag_regexp=tok.postag_regexp,
                        regexp=tok.regexp,
                        negate=tok.negate,
                        negate_pos=tok.negate_pos,
                        inflected=tok.inflected,
                        case_sensitive=tok.case_sensitive,
                        skip=tok.skip,
                        min=tok.min,
                        max=tok.max,
                        chunk=tok.chunk,
                        spacebefore=tok.spacebefore,
                        raw_pos=tok.raw_pos,
                        is_in_marker=tok.is_in_marker,
                        match=tok.match,
                        exceptions=tok.exceptions,
                        and_elements=tok.and_elements,
                        is_unify_neutral=True,
                    )
                )
            branches.append((expanded_tokens, len(expanded_tokens)))
        return branches

    else:
        raise GrammarFormatError(f"Unsupported pattern element type: {type(elem).__name__}")


def filter_subsumed_rule_matches(matches: List[RuleMatchResult]) -> List[RuleMatchResult]:
    """Filter subsumed rule matches exactly matching Java LT RuleWithMaxFilter."""
    if len(matches) <= 1:
        return list(matches)

    sorted_matches = sorted(matches, key=lambda m: m.from_pos)
    filtered: List[RuleMatchResult] = []
    i = 0
    n = len(sorted_matches)
    while i < n:
        m = sorted_matches[i]
        while i < n - 1:
            next_m = sorted_matches[i + 1]
            if (
                m.from_pos <= next_m.from_pos
                and m.to_pos >= next_m.to_pos
                and m.rule_id == next_m.rule_id
                and m.full_rule_id == next_m.full_rule_id
            ):
                i += 1
            else:
                break
        filtered.append(m)
        i += 1
    return filtered


class CompiledPattern:
    """Compiled pattern wrapper supporting match_at."""

    def __init__(self, pattern: Pattern) -> None:
        self.raw = pattern
        self.tokens = [CompiledPatternToken(t) for t in pattern.tokens]
        self.has_marker = pattern.has_marker
        self.marker_start_idx = pattern.marker_start_idx
        self.marker_end_idx = pattern.marker_end_idx
        self._variant = CompiledRuleVariant(
            source_rule=None,  # type: ignore[arg-type]
            variant_idx=0,
            tokens=self.tokens,
            element_lengths=[1] * len(self.tokens),
            has_marker=self.has_marker,
            marker_start_idx=self.marker_start_idx,
            marker_end_idx=self.marker_end_idx,
            raw_pos=pattern.raw_pos,
        )

    def match_at(
        self,
        non_blank_tokens: Sequence[AnalyzedTokenReadings],
        start_idx: int,
    ) -> Optional[Tuple[int, int, int, int]]:
        res = self._variant._match_from(
            tokens=non_blank_tokens,
            start_idx=start_idx,
            synthesizer=None,
            immunized_tokens=set(),
        )
        if res is None:
            return None
        return res.match_start_idx, res.match_end_idx, res.error_start_idx, res.error_end_idx

