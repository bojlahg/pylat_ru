"""Disambiguation pattern rules and replacement engine matching LanguageTool."""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Pattern, Sequence, Tuple, Union

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.filters import DisambiguationFilter
from pylat_ru.disambiguation.pattern_matcher import PatternRuleMatcher, PatternToken, RuleMatchResult


class DisambiguatorAction(enum.Enum):
    """Possible disambiguation actions in LanguageTool."""

    ADD = "add"
    FILTER = "filter"
    REMOVE = "remove"
    REPLACE = "replace"
    UNIFY = "unify"
    IMMUNIZE = "immunize"
    IGNORE_SPELLING = "ignore_spelling"
    FILTERALL = "filterall"
    ADDCHUNK = "addchunk"


@dataclass
class MatchElement:
    """Represents a <match> element in <disambig>."""

    no: int  # 0-indexed reference to matched token
    postag: Optional[str] = None
    postag_regex: Optional[str] = None
    pos_replace: Optional[str] = None
    set_postag: Optional[str] = None


@dataclass
class DisambiguatedExample:
    """An example sentence testing a disambiguation rule."""

    example: str
    example_type: str = "ambiguous"  # "ambiguous" or "untouched"
    input_form: Optional[str] = None
    output_form: Optional[str] = None


@dataclass
class DisambiguationPatternRule:
    """A single disambiguation pattern rule."""

    id: str
    name: str
    pattern_tokens: List[PatternToken]
    action: DisambiguatorAction
    sub_id: Optional[str] = None
    rulegroup_id: Optional[str] = None
    disambiguated_pos: Optional[str] = None
    match_element: Optional[MatchElement] = None
    new_token_readings: List[AnalyzedToken] = field(default_factory=list)
    filter: Optional[DisambiguationFilter] = None
    filter_args: Optional[str] = None
    antipatterns: List[DisambiguationPatternRule] = field(default_factory=list)
    examples: List[DisambiguatedExample] = field(default_factory=list)
    untouched_examples: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.matcher = PatternRuleMatcher(self.pattern_tokens)


class DisambiguationPatternRuleReplacer:
    """Executes a DisambiguationPatternRule against an AnalyzedSentence."""

    def __init__(self, rule: DisambiguationPatternRule) -> None:
        self.rule = rule

    def replace(self, sentence: AnalyzedSentence) -> AnalyzedSentence:
        """Apply rule matches and actions to sentence."""
        matches = self.rule.matcher.find_matches(sentence)
        if not matches:
            return sentence

        tokens_without_ws = sentence.get_tokens_without_whitespace()
        raw_tokens = [AnalyzedTokenReadings(t) for t in sentence.get_tokens()]
        changed = False

        for match in matches:
            # Check antipatterns
            if not self._keep_by_disambig(sentence, match):
                continue

            # Check filters
            if not self._keep_despite_filter(tokens_without_ws, match):
                continue

            # Execute action
            self._execute_action(sentence, raw_tokens, tokens_without_ws, match)
            changed = True

        if changed:
            return AnalyzedSentence(tokens=raw_tokens, pre_disambig_tokens=sentence.get_tokens())
        return sentence

    def _keep_by_disambig(self, sentence: AnalyzedSentence, match: RuleMatchResult) -> bool:
        """Return False if any antipattern overlaps with this rule match."""
        if not self.rule.antipatterns:
            return True

        tokens = sentence.get_tokens_without_whitespace()
        match_from_pos = tokens[match.first_match_token].start_pos
        match_to_pos = tokens[match.last_match_token].start_pos + len(tokens[match.last_match_token].token)

        for antipattern in self.rule.antipatterns:
            anti_matches = antipattern.matcher.find_matches(sentence)
            for am in anti_matches:
                anti_from_pos = tokens[am.first_match_token].start_pos
                anti_to_pos = tokens[am.last_match_token].start_pos + len(tokens[am.last_match_token].token)
                if (
                    (anti_from_pos <= match_from_pos and anti_to_pos >= match_from_pos)
                    or (anti_from_pos <= match_to_pos and anti_to_pos >= match_to_pos)
                    or (anti_from_pos >= match_from_pos and anti_to_pos <= match_to_pos)
                ):
                    return False
        return True

    def _keep_despite_filter(
        self, tokens: Sequence[AnalyzedTokenReadings], match: RuleMatchResult
    ) -> bool:
        """Return True if filter accepts the match or no filter is configured."""
        if self.rule.filter is not None and self.rule.filter_args is not None:
            relevant_tokens = tokens[match.first_match_token : match.last_match_token + 1]
            return self.rule.filter.matches(
                self.rule.filter_args,
                relevant_tokens,
                match.first_match_token,
                match.token_positions,
            )
        return True

    def _execute_action(
        self,
        sentence: AnalyzedSentence,
        wh_tokens: List[AnalyzedTokenReadings],
        non_blank_tokens: Sequence[AnalyzedTokenReadings],
        match: RuleMatchResult,
    ) -> None:
        """Apply rule action to marked tokens in wh_tokens."""
        action = self.rule.action
        first_marker = match.first_marker_match_token
        last_marker = match.last_marker_match_token

        marker_count = last_marker - first_marker + 1
        new_readings = self.rule.new_token_readings
        disambiguated_pos = self.rule.disambiguated_pos
        match_elem = self.rule.match_element

        if action == DisambiguatorAction.ADD:
            if new_readings:
                for i, new_reading in enumerate(new_readings):
                    non_wh_idx = first_marker + i
                    if non_wh_idx < len(non_blank_tokens):
                        orig_idx = sentence.get_original_position(non_wh_idx)
                        tok_str = new_reading.token if new_reading.token else wh_tokens[orig_idx].token
                        lemma_str = new_reading.lemma if new_reading.lemma is not None else tok_str
                        added_at = AnalyzedToken(token=tok_str, pos_tag=new_reading.pos_tag, lemma=lemma_str)
                        wh_tokens[orig_idx].add_reading(added_at, self.rule.id)

        elif action == DisambiguatorAction.REMOVE:
            if new_readings:
                for i, new_reading in enumerate(new_readings):
                    non_wh_idx = first_marker + i
                    if non_wh_idx < len(non_blank_tokens):
                        orig_idx = sentence.get_original_position(non_wh_idx)
                        wh_tokens[orig_idx].remove_reading(new_reading, self.rule.id)
            elif disambiguated_pos:
                p = re.compile(disambiguated_pos)
                for non_wh_idx in range(first_marker, last_marker + 1):
                    orig_idx = sentence.get_original_position(non_wh_idx)
                    tmp_readings = list(wh_tokens[orig_idx].readings)
                    for r in tmp_readings:
                        if r.pos_tag is not None and p.fullmatch(r.pos_tag) is not None:
                            wh_tokens[orig_idx].remove_reading(r, self.rule.id)

        elif action == DisambiguatorAction.IGNORE_SPELLING:
            for non_wh_idx in range(first_marker, last_marker + 1):
                orig_idx = sentence.get_original_position(non_wh_idx)
                wh_tokens[orig_idx].ignore_spelling()

        elif action == DisambiguatorAction.IMMUNIZE:
            for non_wh_idx in range(first_marker, last_marker + 1):
                orig_idx = sentence.get_original_position(non_wh_idx)
                wh_tokens[orig_idx].immunize()

        elif action in (DisambiguatorAction.FILTER, DisambiguatorAction.REPLACE):
            if new_readings:
                for i, new_reading in enumerate(new_readings):
                    non_wh_idx = first_marker + i
                    if non_wh_idx < len(non_blank_tokens):
                        orig_idx = sentence.get_original_position(non_wh_idx)
                        tok_str = new_reading.token if new_reading.token else wh_tokens[orig_idx].token
                        lemma_str = new_reading.lemma if new_reading.lemma is not None else tok_str
                        wh_tokens[orig_idx].readings = [
                            AnalyzedToken(token=tok_str, pos_tag=new_reading.pos_tag, lemma=lemma_str)
                        ]
            elif match_elem is not None:
                # Use referenced matched token's lemma or token
                ref_non_wh = match.first_match_token + match_elem.no
                ref_orig = sentence.get_original_position(ref_non_wh)
                ref_tok = wh_tokens[ref_orig]

                target_postag = match_elem.postag or match_elem.set_postag or disambiguated_pos
                for non_wh_idx in range(first_marker, last_marker + 1):
                    orig_idx = sentence.get_original_position(non_wh_idx)
                    lemma = wh_tokens[orig_idx].readings[0].lemma_or_token if wh_tokens[orig_idx].readings else wh_tokens[orig_idx].token
                    wh_tokens[orig_idx].readings = [
                        AnalyzedToken(token=wh_tokens[orig_idx].token, pos_tag=target_postag, lemma=lemma)
                    ]
            elif disambiguated_pos:
                p = re.compile(disambiguated_pos)
                for non_wh_idx in range(first_marker, last_marker + 1):
                    orig_idx = sentence.get_original_position(non_wh_idx)
                    tok = wh_tokens[orig_idx]
                    if action == DisambiguatorAction.REPLACE:
                        lemma = None
                        for r in tok.readings:
                            if r.pos_tag == disambiguated_pos and r.lemma:
                                lemma = r.lemma
                                break
                        if not lemma and tok.readings:
                            lemma = tok.readings[0].lemma
                        if not lemma:
                            lemma = tok.token
                        wh_tokens[orig_idx].readings = [
                            AnalyzedToken(token=tok.token, pos_tag=disambiguated_pos, lemma=lemma)
                        ]
                    else:  # FILTER
                        matching_readings = [
                            r for r in tok.readings
                            if r.pos_tag is not None and p.fullmatch(r.pos_tag) is not None
                        ]
                        if matching_readings:
                            wh_tokens[orig_idx].readings = matching_readings
