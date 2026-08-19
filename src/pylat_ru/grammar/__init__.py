"""src/pylat_ru/grammar/__init__.py

XML Grammar Rule Engine for LanguageTool Russian.
"""

from pylat_ru.grammar.classifier import classify_rule_element
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.errors import (
    GrammarError,
    GrammarFormatError,
    GrammarResourceError,
    GrammarRuleDisabledError,
    UnsupportedGrammarFeatureError,
)
from pylat_ru.grammar.formatter import TemplateFormatter
from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.matcher import (
    CompiledPattern,
    CompiledPatternToken,
    CompiledRuleVariant,
    expand_rule_into_variants,
    filter_subsumed_rule_matches,
)
from pylat_ru.grammar.model import (
    Example,
    ExecutionState,
    GrammarRule,
    MatchReference,
    MessageTemplate,
    Pattern,
    PatternToken,
    PatternTokenException,
    RuleBlocker,
    RuleMatchResult,
    SuggestionTemplate,
)

__all__ = [
    "RussianGrammarEngine",
    "GrammarLoader",
    "GrammarRule",
    "RuleMatchResult",
    "ExecutionState",
    "RuleBlocker",
    "Pattern",
    "PatternToken",
    "PatternTokenException",
    "MatchReference",
    "MessageTemplate",
    "SuggestionTemplate",
    "Example",
    "TemplateFormatter",
    "CompiledPattern",
    "CompiledPatternToken",
    "CompiledRuleVariant",
    "expand_rule_into_variants",
    "filter_subsumed_rule_matches",
    "classify_rule_element",
    "GrammarError",
    "GrammarFormatError",
    "GrammarResourceError",
    "UnsupportedGrammarFeatureError",
    "GrammarRuleDisabledError",
]
