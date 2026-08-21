"""pylat_ru: Native Python reimplementation of the Russian LanguageTool pipeline.

This library aims for upstream semantic compatibility with LanguageTool's
Russian grammar checking pipeline, without requiring Java, JRE, LanguageTool
server, Natasha, pymorphy, or another external NLP runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, List, Mapping, Sequence

from pylat_ru.analysis import (
    AnalyzedSentence,
    AnalyzedToken,
    AnalyzedTokenReadings,
)
from pylat_ru.disambiguation import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.match_filters import LEVEL_DEFAULT, filter_rule_matches
from pylat_ru.native_rules import NativeRuleFinding, RussianJavaRulesEngine
from pylat_ru.morfologik import (
    DictionaryEntry,
    MorfologikDictionary,
)
from pylat_ru.sentence_analyzer import (
    RussianSentenceAnalyzer,
    create_raw_analyzed_sentence,
)
from pylat_ru.synthesis import (
    BaseSynthesizer,
    ManualSynthesizer,
    RussianSynthesizer,
    Synthesizer,
)
from pylat_ru.tagging import RussianTagger
from pylat_ru.tagset import RussianTag, parse_tag
from pylat_ru.tokenization import (
    RussianSentenceTokenizer,
    RussianWordTokenizer,
    SentenceSpan,
    TextSpan,
    TokenSpan,
)

__version__ = "0.1.0a0"
__all__ = [
    "__version__",
    "AnalyzedSentence",
    "AnalyzedToken",
    "AnalyzedTokenReadings",
    "BaseSynthesizer",
    "DictionaryEntry",
    "LanguageToolRU",
    "ManualSynthesizer",
    "MorfologikDictionary",
    "RuleMatch",
    "RussianHybridDisambiguator",
    "RussianJavaRulesEngine",
    "RussianSentenceAnalyzer",
    "RussianSentenceTokenizer",
    "RussianSynthesizer",
    "RussianTag",
    "RussianTagger",
    "RussianWordTokenizer",
    "SentenceSpan",
    "Synthesizer",
    "TextSpan",
    "TokenSpan",
    "create_raw_analyzed_sentence",
    "parse_tag",
]



#: Characters pinned ``JLanguageTool.replaceSoftHyphens`` actually removes from the
#: tokens the rules run on.  ``Russian.getIgnoredCharactersRegex()`` also names the
#: combining acute and grave, but Task 0014 confirmed against the trusted oracle that
#: the pinned check path leaves those in place: inside the pipeline a soft-hyphenated
#: token appears cleaned, while a token carrying a combining mark keeps its original
#: surface and its extra untagged reading.
_IGNORED_CHARACTERS = "\u00ad"


def _strip_ignored_characters(text: str) -> tuple[str, list[int] | None]:
    """Remove the pinned ignored characters, returning the cleaned text and a map.

    ``original_offsets[i]`` is the code-point index in ``text`` of the ``i``-th
    character of the cleaned text; the list carries one extra trailing entry for the
    end of the text.  ``None`` means the text had no ignored characters at all, so no
    mapping is needed.
    """
    if not any(character in _IGNORED_CHARACTERS for character in text):
        return text, None
    cleaned_characters: list[str] = []
    original_offsets: list[int] = []
    for index, character in enumerate(text):
        if character in _IGNORED_CHARACTERS:
            continue
        cleaned_characters.append(character)
        original_offsets.append(index)
    original_offsets.append(len(text))
    return "".join(cleaned_characters), original_offsets


def _restore_ignored_character_offsets(
    match: "RuleMatch", original_offsets: list[int], text: str
) -> "RuleMatch":
    """Map one match from cleaned-text positions back onto the original text.

    The end position is taken from the last covered character, so ignored characters
    that sat inside the match are counted back into its length, exactly as the pinned
    position fix-up does.
    """
    start = original_offsets[match.offset]
    if match.length <= 0:
        end = start
    else:
        end = original_offsets[match.offset + match.length - 1] + 1
    utf16_start = _utf16_offset_of(text, start)
    utf16_end = _utf16_offset_of(text, end)
    return replace(
        match,
        offset=start,
        length=end - start,
        utf16_offset=utf16_start,
        utf16_length=utf16_end - utf16_start,
        original_error=text[start:end],
    )


def _utf16_offset_of(text: str, code_point_offset: int) -> int:
    """UTF-16 code-unit offset of a code-point offset in ``text``."""
    return code_point_offset + sum(
        1 for character in text[:code_point_offset] if ord(character) > 0xFFFF
    )


@dataclass(frozen=True)
class RuleMatch:
    """Represents a single rule match / finding."""

    rule_id: str
    category_id: str
    message: str
    offset: int
    length: int
    replacements: Sequence[str]
    short_message: str = ""
    source: str = "pylat_ru"
    category_name: str = ""
    url: str | None = None
    priority: int = 0
    full_rule_id: str = ""
    tags: tuple[str, ...] = ()
    registration_order: int = 0
    included_in_errors_corrected_all_at_once: bool = False
    original_error: str = ""
    utf16_offset: int = 0
    utf16_length: int = 0


class LanguageToolRU:
    """Russian LanguageTool pipeline interface (Python-native).

    Runs the accepted Russian analysis pipeline, all 892 XML grammar rules, and
    the 23 Python-native equivalents of the ordinary Russian Java rules,
    including native Morfologik spelling.  The language-model rule
    ``RussianConfusionProbabilityRule`` is not part of this surface.
    """

    def __init__(
        self,
        disabled_rules: Sequence[str] | None = None,
        enabled_rules: Sequence[str] | None = None,
        rule_config: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.disabled_rules = set(disabled_rules or [])
        self.enabled_rules = set(enabled_rules or [])
        self.grammar_engine = RussianGrammarEngine()
        self.java_rules_engine = RussianJavaRulesEngine(rule_config=rule_config)
        for rule_id in self.disabled_rules:
            if self.java_rules_engine.get_rule(rule_id):
                self.java_rules_engine.disable_rule(rule_id)
            elif self.grammar_engine.get_rule(rule_id):
                self.grammar_engine.disable_rule(rule_id)
        for rule_id in self.enabled_rules:
            if self.java_rules_engine.get_rule(rule_id):
                self.java_rules_engine.enable_rule(rule_id)
            elif self.grammar_engine.get_rule(rule_id):
                self.grammar_engine.enable_rule(rule_id)

    def check(self, text: str, level: str = LEVEL_DEFAULT) -> List[RuleMatch]:
        r"""Check Russian text without Java or an external NLP runtime.

        Pinned ``JLanguageTool`` removes the Russian ignored characters
        ``[\u00AD\u0301\u0300]`` from every token before the rules run, so the whole
        rule pipeline sees the cleaned text; only the reported positions are mapped
        back onto the original.  ``RussianSentenceAnalyzer`` keeps the uncleaned
        surface in an extra reading for the public analysis API, which is why a
        rule-level check and a whole-pipeline check legitimately differ on such text.
        """
        if not text:
            return []
        cleaned, original_offsets = _strip_ignored_characters(text)
        matches = filter_rule_matches(self._collect_matches(cleaned), cleaned, level=level)
        if original_offsets is None:
            return matches
        return [_restore_ignored_character_offsets(m, original_offsets, text) for m in matches]

    def _collect_matches(self, text: str) -> list[RuleMatch]:
        """Collect matches in pinned rule-execution order before global filters."""
        context = self.java_rules_engine.analyze(text)
        candidates: list[RuleMatch] = []

        for native in self.java_rules_engine.check_context(context):
            public = self._native_to_public(native)
            candidates.append(public)

        xml_order_base = len(self.java_rules_engine.rules)
        for unit in context.sentences:
            for finding in self.grammar_engine.check_sentence(unit.analyzed):
                rule = self.grammar_engine.get_rule(finding.full_rule_id)
                priority = self._xml_rule_priority(rule)
                public = RuleMatch(
                    rule_id=finding.rule_id,
                    category_id=finding.category_id,
                    message=finding.message,
                    offset=unit.start + finding.from_pos,
                    length=finding.to_pos - finding.from_pos,
                    replacements=tuple(finding.suggestions),
                    short_message=finding.short_message or "",
                    source="xml_grammar",
                    category_name=finding.category_name,
                    url=finding.url,
                    priority=priority,
                    full_rule_id=finding.full_rule_id,
                    tags=tuple(rule.tags) if rule else (),
                    registration_order=xml_order_base + (rule.source_order_index if rule else 0),
                    original_error=text[unit.start + finding.from_pos:unit.start + finding.to_pos],
                    utf16_offset=context.mapper.codepoint_to_utf16(unit.start + finding.from_pos),
                    utf16_length=finding.to_pos_utf16 - finding.from_pos_utf16,
                )
                candidates.append(public)
        return candidates

    @staticmethod
    def _native_to_public(finding: NativeRuleFinding) -> RuleMatch:
        return RuleMatch(
            rule_id=finding.rule_id,
            category_id=finding.category_id,
            message=finding.message,
            offset=finding.from_pos,
            length=finding.to_pos - finding.from_pos,
            replacements=finding.suggestions,
            short_message=finding.short_message,
            source=finding.source,
            category_name=finding.category_name,
            url=finding.url,
            priority=finding.priority,
            full_rule_id=finding.rule_id,
            tags=finding.tags,
            registration_order=finding.registration_order,
            original_error=finding.original_error,
            utf16_offset=finding.from_pos_utf16,
            utf16_length=finding.to_pos_utf16 - finding.from_pos_utf16,
        )

    @staticmethod
    def _xml_rule_priority(rule: Any | None) -> int:
        if rule is None:
            return 0
        russian = {"RU_DASH_RULE": 12, "RU_COMPOUNDS": 11,
                   "RUSSIAN_SIMPLE_REPLACE_RULE": 10, "RUSSIAN_SPECIFIC_CASE": 9,
                   "MORFOLOGIC_RULE_RU_RU_YO": 2, "MORFOLOGIC_RULE_RU_RU": 1,
                   "Word_root_repeat": -1, "PUNCT_DPT_2": -2,
                   "TOO_LONG_PARAGRAPH": -15}
        if rule.id in russian:
            return russian[rule.id]
        if rule.id.upper() == "TOO_LONG_SENTENCE":
            return -101
        if rule.prio:
            return rule.prio
        if rule.category_id == "REPETITIONS_STYLE":
            return -55
        if "STYLE" in rule.category_id:
            return -50
        return 0
