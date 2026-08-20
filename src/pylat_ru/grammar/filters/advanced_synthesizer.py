import re
import dataclasses
from typing import List, Dict, Optional
from pylat_ru.analysis import AnalyzedTokenReadings, AnalyzedToken
from pylat_ru.grammar.model import RuleMatchResult
from pylat_ru.tagging.string_tools import is_capitalized_word, is_all_uppercase, uppercase_first_char
from pylat_ru.synthesis.synthesizer import RussianSynthesizer
from .base import RuleFilter, FilterIllegalArgumentError

class AdvancedSynthesizerFilter(RuleFilter):
    """Filters rule matches and synthesizes suggestions.
    
    Port of org.languagetool.rules.ru.AdvancedSynthesizerFilter.
    """

    def accept_rule_match(
        self,
        match: RuleMatchResult,
        arguments: Dict[str, str],
        pattern_token_pos: int,
        pattern_tokens: List[AnalyzedTokenReadings],
        token_positions: List[int]
    ) -> Optional[RuleMatchResult]:
        postag_select = self.get_required("postagSelect", arguments)
        lemma_select = self.get_required("lemmaSelect", arguments)
        postag_from_str = self.get_required("postagFrom", arguments)
        lemma_from_str = self.get_required("lemmaFrom", arguments)
        new_lemma = self.get_optional("newLemma", arguments, "")

        postag_from_idx = self.get_position(postag_from_str, pattern_tokens, match)
        lemma_from_idx = self.get_position(lemma_from_str, pattern_tokens, match)

        postag_replace = self.get_optional("postagReplace", arguments)

        lemma_token = pattern_tokens[lemma_from_idx]
        postag_token = pattern_tokens[postag_from_idx]

        lemma_reading = self.get_analyzed_token(lemma_token, lemma_select)
        postag_reading = self.get_analyzed_token(postag_token, postag_select)

        desired_lemma = lemma_reading.lemma
        original_postag = lemma_reading.pos_tag
        desired_postag = postag_reading.pos_tag

        if new_lemma:
            if new_lemma.startswith("_"):
                desired_lemma = self.get_new_lemma(desired_lemma, new_lemma)
            else:
                desired_lemma = new_lemma

        if desired_lemma is None:
            return None

        if desired_postag is None:
            raise FilterIllegalArgumentError(
                f"AdvancedSynthesizerFilter: undefined POS tag for rule {match.full_rule_id} "
                f"with POS regex '{postag_select}' for token: {postag_token}"
            )

        if postag_replace is not None:
            desired_postag = self.get_composite_postag(
                lemma_select, postag_select, original_postag or "UNKNOWN", desired_postag, postag_replace
            )

        # Capitalization source: lemma token surface text
        lemma_surface = lemma_token.token
        is_word_capitalized = is_capitalized_word(lemma_surface)
        is_word_all_upper = is_all_uppercase(lemma_surface)

        token = AnalyzedToken(token="", lemma=desired_lemma, pos_tag=desired_postag)
        synth = self.synthesizer or RussianSynthesizer.get_instance()
        replacements = synth.synthesize(token, desired_postag, pos_tag_is_regex=True)

        if len(replacements) > 0:
            replacements_list: List[str] = []
            suggestion_used = False

            # If the match has suggestions, we expand them
            for r in match.suggestions:
                for nr in replacements:
                    if self.is_suggestion_exception(nr, desired_postag):
                        continue
                    if "{suggestion}" in r or "{Suggestion}" in r or "{SUGGESTION}" in r:
                        suggestion_used = True
                    
                    if is_word_capitalized:
                        nr = uppercase_first_char(nr)
                    if is_word_all_upper:
                        nr = nr.upper()

                    complete_suggestion = r.replace("{suggestion}", nr)
                    complete_suggestion = complete_suggestion.replace("{Suggestion}", uppercase_first_char(nr))
                    complete_suggestion = complete_suggestion.replace("{SUGGESTION}", nr.upper())

                    if complete_suggestion not in replacements_list:
                        replacements_list.append(complete_suggestion)

            if not suggestion_used:
                # Java appends the raw synthesizer array here: no casing pass and
                # no extra deduplication beyond whatever the synthesizer returned.
                replacements_list.extend(replacements)

            # Java returns a fresh RuleMatch, whose pattern span defaults to
            # the finding span rather than retaining the provisional span.
            return dataclasses.replace(
                match,
                suggestions=replacements_list,
                pattern_from_pos=match.from_pos,
                pattern_to_pos=match.to_pos,
                pattern_from_pos_utf16=match.from_pos_utf16,
                pattern_to_pos_utf16=match.to_pos_utf16,
                url=None,
            )

        return match

    def get_composite_postag(
        self,
        lemma_select: str,
        postag_select: str,
        original_postag: str,
        desired_postag: str,
        postag_replace: str
    ) -> str:
        a_pattern = re.compile(lemma_select)
        b_pattern = re.compile(postag_select)
        a_match = a_pattern.fullmatch(original_postag)
        b_match = b_pattern.fullmatch(desired_postag)
        result = postag_replace
        if a_match is not None and b_match is not None:
            for i in range(1, a_pattern.groups + 1):
                group_str = a_match.group(i)
                if group_str is not None:
                    to_replace = f"\\a{i}"
                    result = result.replace(to_replace, group_str)
            for i in range(1, b_pattern.groups + 1):
                group_str = b_match.group(i)
                if group_str is not None:
                    to_replace = f"\\b{i}"
                    result = result.replace(to_replace, group_str)
        return result

    def get_analyzed_token(self, a_token: AnalyzedTokenReadings, regexp: str) -> AnalyzedToken:
        pattern = re.compile(regexp)
        for reading in a_token.readings:
            pos_tag = reading.pos_tag if reading.pos_tag is not None else "UNKNOWN"
            if pattern.fullmatch(pos_tag):
                return reading
        return a_token.readings[0]

    def get_new_lemma(self, word: str, new_lemma: str) -> Optional[str]:
        return None

    def is_suggestion_exception(self, token: str, desired_postag: str) -> bool:
        return False
