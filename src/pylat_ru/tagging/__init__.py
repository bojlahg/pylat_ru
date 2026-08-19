"""Tagging subsystem for LanguageTool Russian morphology."""

from __future__ import annotations

from pylat_ru.tagging.errors import (
    ManualTaggerFormatError,
    TaggerCompatibilityError,
    TaggerError,
    TaggerResourceError,
)
from pylat_ru.tagging.russian import RussianTagger
from pylat_ru.tagging.string_tools import (
    change_first_char_case,
    is_all_uppercase,
    is_capitalized_word,
    is_mixed_case,
    is_not_all_lowercase,
    lowercase_first_char,
    uppercase_first_char,
)
from pylat_ru.tagging.word_tagger import (
    CombiningTagger,
    ManualTagger,
    MorfologikTagger,
    TaggedWord,
    WordTagger,
)

__all__ = [
    "RussianTagger",
    "TaggedWord",
    "WordTagger",
    "MorfologikTagger",
    "ManualTagger",
    "CombiningTagger",
    "TaggerError",
    "TaggerResourceError",
    "ManualTaggerFormatError",
    "TaggerCompatibilityError",
    "is_all_uppercase",
    "is_not_all_lowercase",
    "is_capitalized_word",
    "is_mixed_case",
    "change_first_char_case",
    "uppercase_first_char",
    "lowercase_first_char",
]
