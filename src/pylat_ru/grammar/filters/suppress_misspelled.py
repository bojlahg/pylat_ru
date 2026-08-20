"""Port of ``org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter``.

The leaf class is empty; all behavior comes from
``org.languagetool.rules.AbstractSuppressMisspelledSuggestionsFilter``, which
drops replacements the language's *default spelling rule* rejects and, unless
``suppressMatch`` is literally ``false``, suppresses the whole match when no
replacement survives.
"""

from dataclasses import replace as dataclass_replace
from typing import Dict, List, Optional

from pylat_ru.analysis import AnalyzedTokenReadings
from pylat_ru.grammar.model import RuleMatchResult

from .base import RuleFilter


class RussianSuppressMisspelledSuggestionsFilter(RuleFilter):
    """Remove misspelled replacements; optionally suppress the entire match."""

    def accept_rule_match(
        self,
        match: RuleMatchResult,
        arguments: Dict[str, str],
        pattern_token_pos: int,
        pattern_tokens: List[AnalyzedTokenReadings],
        token_positions: List[int],
    ) -> Optional[RuleMatchResult]:
        from pylat_ru.tagging.russian import RussianTagger

        replacements = list(match.suggestions)
        suppress_match = self.get_required("suppressMatch", arguments)
        suppress_postag = self.get_optional("SuppressPostag", arguments)

        tagged: List[AnalyzedTokenReadings] = []
        if suppress_postag is not None:
            tagged = list(RussianTagger.get_instance().tag(replacements))

        new_replacements: List[str] = []
        for index, replacement in enumerate(replacements):
            if self.is_misspelled(replacement):
                continue
            if suppress_postag is not None:
                if index < len(tagged) and tagged[index].matches_pos_tag_regex(suppress_postag):
                    continue
            new_replacements.append(replacement)

        b_suppress_match = True
        if suppress_match is not None and suppress_match.lower() == "false":
            b_suppress_match = False

        if not new_replacements and b_suppress_match:
            return None
        return dataclass_replace(match, suggestions=new_replacements)

    @staticmethod
    def is_misspelled(text: str) -> bool:
        """``AbstractSuppressMisspelledSuggestionsFilter.isMisspelled``.

        The replacement is tokenized with the Russian word tokenizer and is
        misspelled if the default spelling rule rejects any of its tokens.
        """
        from pylat_ru.spelling import get_default_spelling_rule
        from pylat_ru.tokenization.word import RussianWordTokenizer

        speller = get_default_spelling_rule()
        for token in RussianWordTokenizer().tokenize(text):
            if speller.is_misspelled(token):
                return True
        return False
