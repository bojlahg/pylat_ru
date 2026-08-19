"""Russian disambiguation subsystem for pylat_ru."""

from __future__ import annotations

from pylat_ru.disambiguation.errors import (
    DisambiguationError,
    DisambiguationFilterError,
    DisambiguationFormatError,
    DisambiguationResourceError,
)
from pylat_ru.disambiguation.filters import (
    DisambiguationFilter,
    NoDisambiguationRussianPartialPosTagFilter,
)
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.disambiguation.multiwords import MultiWordChunker
from pylat_ru.disambiguation.pattern_matcher import (
    PatternRuleMatcher,
    PatternToken,
    PatternTokenException,
    RuleMatchResult,
)
from pylat_ru.disambiguation.rules import (
    DisambiguatedExample,
    DisambiguationPatternRule,
    DisambiguationPatternRuleReplacer,
    DisambiguatorAction,
    MatchElement,
)
from pylat_ru.disambiguation.xml_loader import (
    DisambiguationRuleLoader,
    XmlRuleDisambiguator,
)

__all__ = [
    "DisambiguationError",
    "DisambiguationResourceError",
    "DisambiguationFormatError",
    "DisambiguationFilterError",
    "DisambiguationFilter",
    "NoDisambiguationRussianPartialPosTagFilter",
    "MultiWordChunker",
    "PatternToken",
    "PatternTokenException",
    "PatternRuleMatcher",
    "RuleMatchResult",
    "DisambiguatorAction",
    "MatchElement",
    "DisambiguatedExample",
    "DisambiguationPatternRule",
    "DisambiguationPatternRuleReplacer",
    "DisambiguationRuleLoader",
    "XmlRuleDisambiguator",
    "RussianHybridDisambiguator",
]
