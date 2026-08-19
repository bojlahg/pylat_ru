"""src/pylat_ru/tokenization/__init__.py

Public tokenization APIs for Russian sentence and word tokenization with exact offsets.
"""

from __future__ import annotations

from pylat_ru.tokenization.errors import (
    SRXFormatError,
    SRXRuleCompilationError,
    TokenizationError,
    UnsupportedSRXFeatureError,
    WordTokenizationError,
)
from pylat_ru.tokenization.offsets import (
    SentenceSpan,
    TextSpan,
    TokenSpan,
    Utf16CodePointMapper,
    sentences_to_spans,
    tokens_to_spans,
    validate_spans_invariants,
)
from pylat_ru.tokenization.sentence import RussianSentenceTokenizer
from pylat_ru.tokenization.srx import (
    SRXRule,
    SRXRuleManager,
    SRXRuleMatcher,
    SRXSegmenter,
    load_russian_srx_rule_manager,
)
from pylat_ru.tokenization.word import (
    RussianWordTokenizer,
    join_emails,
    join_urls,
    split_by_delimiters,
)

__all__ = [
    "RussianSentenceTokenizer",
    "RussianWordTokenizer",
    "TextSpan",
    "SentenceSpan",
    "TokenSpan",
    "Utf16CodePointMapper",
    "tokens_to_spans",
    "sentences_to_spans",
    "validate_spans_invariants",
    "SRXRule",
    "SRXRuleManager",
    "SRXRuleMatcher",
    "SRXSegmenter",
    "load_russian_srx_rule_manager",
    "TokenizationError",
    "SRXFormatError",
    "SRXRuleCompilationError",
    "UnsupportedSRXFeatureError",
    "WordTokenizationError",
    "split_by_delimiters",
    "join_emails",
    "join_urls",
]
