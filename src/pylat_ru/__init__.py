"""pylat_ru: Native Python reimplementation of the Russian LanguageTool pipeline.

This library aims for upstream semantic compatibility with LanguageTool's
Russian grammar checking pipeline, without requiring Java, JRE, LanguageTool
server, Natasha, pymorphy, or another external NLP runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Mapping, Sequence

from pylat_ru.analysis import (
    AnalyzedSentence,
    AnalyzedToken,
    AnalyzedTokenReadings,
)
from pylat_ru.disambiguation import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.match_filters import filter_rule_matches
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

    Runs the accepted Russian analysis pipeline, XML grammar rules, and the
    15 Python-native Java-rule equivalents implemented by Task 0011.
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

    def check(self, text: str) -> List[RuleMatch]:
        """Check Russian text without Java or an external NLP runtime."""
        if not text:
            return []
        return filter_rule_matches(self._collect_matches(text), text)

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
