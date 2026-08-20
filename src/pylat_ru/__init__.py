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
        context = self.java_rules_engine.analyze(text)
        results: List[RuleMatch] = []
        ordering: list[tuple[int, int, int, RuleMatch]] = []

        for native in self.java_rules_engine.check_context(context):
            public = self._native_to_public(native)
            ordering.append((native.from_pos, -native.priority, native.registration_order, public))

        xml_order_base = len(self.java_rules_engine.rules)
        for unit in context.sentences:
            for finding in self.grammar_engine.check_sentence(unit.analyzed):
                rule = self.grammar_engine.get_rule(finding.full_rule_id)
                priority = (rule.prio or 0) if rule else 0
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
                )
                source_order = rule.source_order_index if rule else 0
                ordering.append((public.offset, -priority, xml_order_base + source_order, public))

        # JLanguageTool's full check surface cleans overlapping matches after
        # all rule families have run.  Direct per-rule checks intentionally do
        # not use this stage (e.g. both sides of a badly spaced comma).
        selected: list[tuple[int, int, int, RuleMatch]] = []
        for item in sorted(ordering, key=lambda value: (value[1], -value[3].length, -value[2], value[0])):
            candidate = item[3]
            candidate_end = candidate.offset + candidate.length
            if any(candidate.offset < kept.offset + kept.length and kept.offset < candidate_end for *_, kept in selected):
                continue
            selected.append(item)
        selected.sort(key=lambda item: (item[0], item[1], item[2], item[3].length))
        results.extend(item[3] for item in selected)
        return results

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
        )
