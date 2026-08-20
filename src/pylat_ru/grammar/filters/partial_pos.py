import re
from typing import List, Dict, Optional
from pylat_ru.analysis import AnalyzedTokenReadings, AnalyzedSentence
from pylat_ru.grammar.model import RuleMatchResult
from pylat_ru.tagging.russian import RussianTagger
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from .base import RuleFilter

class RussianPartialPosTagFilter(RuleFilter):
    """Filters rule matches by checking POS tags of a sub-token.
    
    Port of org.languagetool.rules.ru.RussianPartialPosTagFilter.
    """

    def accept_rule_match(
        self,
        match: RuleMatchResult,
        arguments: Dict[str, str],
        pattern_token_pos: int,
        pattern_tokens: List[AnalyzedTokenReadings],
        token_positions: List[int]
    ) -> Optional[RuleMatchResult]:
        if "no" not in arguments or "regexp" not in arguments or "postag_regexp" not in arguments:
            raise ValueError(
                "Set 'no', 'regexp' and 'postag_regexp' for filter RussianPartialPosTagFilter"
            )

        token_pos = int(arguments["no"])
        regexp_pattern = arguments["regexp"]
        required_tag_regexp = arguments["postag_regexp"]

        negate_pos = "negate_pos" in arguments
        two_groups_regexp = "two_groups_regexp" in arguments

        prefix = arguments.get("prefix", "")
        suffix = arguments.get("suffix", "")

        if token_pos - 1 >= len(pattern_tokens):
            return None

        target_token = pattern_tokens[token_pos - 1]
        token_str = prefix + target_token.token + suffix

        pattern = re.compile(regexp_pattern)
        if (pattern.groups != 1) and not two_groups_regexp:
            raise ValueError(f"Got {pattern.groups} groups for regex '{regexp_pattern}', expected 1")
        if (pattern.groups != 2) and two_groups_regexp:
            raise ValueError(f"Got {pattern.groups} groups for regex '{regexp_pattern}', expected 2")

        m = pattern.fullmatch(token_str)
        if m is not None:
            partial_token = m.group(1)
            if pattern.groups == 2:
                partial_token += m.group(2)

            tags = self.tag(partial_token)
            if tags and self.partial_tag_has_required_tag(tags, required_tag_regexp, negate_pos):
                return match

        return None

    def tag(self, token: str) -> List[AnalyzedTokenReadings]:
        try:
            tagger = RussianTagger.get_instance()
            tags = tagger.tag([token])
            sentence = AnalyzedSentence(tags)
            disambiguator = RussianHybridDisambiguator.get_instance()
            disambiguated = disambiguator.disambiguate(sentence)
            return disambiguated.tokens
        except Exception as e:
            raise RuntimeError(f"Could not tag and disambiguate '{token}'") from e

    def partial_tag_has_required_tag(
        self,
        tags: List[AnalyzedTokenReadings],
        required_tag_regexp: str,
        negate_pos: bool
    ) -> bool:
        postag_count = 0
        tag_pattern = re.compile(required_tag_regexp)

        for tag in tags:
            for reading in tag.readings:
                if reading.pos_tag is not None:
                    if negate_pos:
                        postag_count += 1
                        if tag_pattern.fullmatch(reading.pos_tag):
                            return False
                    else:
                        if tag_pattern.fullmatch(reading.pos_tag):
                            return True

        if postag_count == 0:
            return False
        return negate_pos
