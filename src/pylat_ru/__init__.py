"""pylat_ru: Native Python reimplementation of the Russian LanguageTool pipeline.

This library aims for upstream semantic compatibility with LanguageTool's
Russian grammar checking pipeline, without requiring Java, JRE, LanguageTool
server, Natasha, pymorphy, or another external NLP runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

from pylat_ru.morfologik import (
    DictionaryEntry,
    MorfologikDictionary,
)
from pylat_ru.tagset import RussianTag, parse_tag

__version__ = "0.1.0a0"
__all__ = [
    "__version__",
    "DictionaryEntry",
    "LanguageToolRU",
    "MorfologikDictionary",
    "RuleMatch",
    "RussianTag",
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


class LanguageToolRU:
    """Russian LanguageTool pipeline interface (Python-native).

    Note: At Task 0001, the pipeline components (tagger, disambiguator,
    synthesizer, rule engine) are not yet implemented.
    """

    def __init__(self, disabled_rules: Sequence[str] | None = None) -> None:
        self.disabled_rules = set(disabled_rules or [])

    def check(self, text: str) -> List[RuleMatch]:
        """Check the given Russian text.

        Raises:
            NotImplementedError: Pipeline implementation begins in subsequent tasks.
        """
        raise NotImplementedError(
            "pylat_ru Russian pipeline implementation is in progress. "
            "Rule engine and linguistic pipelines will be implemented in subsequent tasks."
        )
