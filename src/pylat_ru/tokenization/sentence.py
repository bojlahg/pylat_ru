"""src/pylat_ru/tokenization/sentence.py

Native Russian sentence tokenizer matching LanguageTool v6.8 SRXSentenceTokenizer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pylat_ru.tokenization.offsets import SentenceSpan, validate_spans_invariants
from pylat_ru.tokenization.srx import (
    SRXSegmenter,
    load_russian_srx_rule_manager,
)


class RussianSentenceTokenizer:
    """Russian sentence tokenizer matching pinned LanguageTool v6.8 SRX behavior.

    In default mode (single_line_breaks_marks_paragraph=False), uses ru_two
    (paragraph breaks require two or more line breaks).
    In single-line mode (single_line_breaks_marks_paragraph=True), uses ru_one
    (each single line break marks a paragraph).
    """

    def __init__(
        self,
        single_line_breaks_marks_paragraph: bool = False,
        *,
        rules_json_path: Optional[Path] = None,
    ) -> None:
        self._single_line_mode = bool(single_line_breaks_marks_paragraph)
        self._mode = "ru_one" if self._single_line_mode else "ru_two"
        self._rule_manager = load_russian_srx_rule_manager(
            mode=self._mode,
            rules_json_path=rules_json_path,
        )
        self._segmenter = SRXSegmenter(self._rule_manager)

    @property
    def single_line_breaks_marks_paragraph(self) -> bool:
        """True if a single line break marks a paragraph boundary (ru_one mode)."""
        return self._single_line_mode

    @property
    def mode(self) -> str:
        """SRX language code mode ('ru_two' or 'ru_one')."""
        return self._mode

    def tokenize(self, text: str) -> tuple[str, ...]:
        """Split text into sentence strings, preserving exact whitespace and punctuation."""
        if not text:
            return ()
        sentences = self._segmenter.tokenize(text)
        return sentences

    def tokenize_spans(self, text: str) -> tuple[SentenceSpan, ...]:
        """Split text into SentenceSpans with exact code-point and UTF-16 offsets."""
        if not text:
            return ()
        spans = self._segmenter.tokenize_spans(text)
        validate_spans_invariants(spans, text)
        return spans
