"""src/pylat_ru/tokenization/offsets.py

Lossless span representations and UTF-16 / Python code-point offset accounting.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass(frozen=True)
class TextSpan:
    """Base immutable representation of a text span with exact offsets."""

    text: str
    start: int
    end: int
    utf16_start: int
    utf16_end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(
                f"Invalid code-point offsets: start={self.start}, end={self.end}"
            )
        if self.utf16_start < 0 or self.utf16_end < self.utf16_start:
            raise ValueError(
                f"Invalid UTF-16 offsets: utf16_start={self.utf16_start}, utf16_end={self.utf16_end}"
            )
        if len(self.text) != (self.end - self.start):
            raise ValueError(
                f"Text length ({len(self.text)}) does not match span length "
                f"({self.end - self.start}) for text={self.text!r}"
            )

    @property
    def length(self) -> int:
        """Code-point length in Python characters."""
        return self.end - self.start

    @property
    def utf16_length(self) -> int:
        """Length in Java UTF-16 code units."""
        return self.utf16_end - self.utf16_start


@dataclass(frozen=True)
class SentenceSpan(TextSpan):
    """Represents a segmented sentence within a larger text."""


@dataclass(frozen=True)
class TokenSpan(TextSpan):
    """Represents a segmented word, punctuation, or whitespace token."""


class Utf16CodePointMapper:
    """Efficient O(N) mapper between Python code points and Java UTF-16 code units."""

    def __init__(self, text: str) -> None:
        self._text = text
        n = len(text)
        # cp_to_utf16[i] stores UTF-16 offset of code-point index i
        self._cp_to_utf16: List[int] = [0] * (n + 1)
        self._has_non_bmp = False

        utf16_count = 0
        for i, ch in enumerate(text):
            self._cp_to_utf16[i] = utf16_count
            code = ord(ch)
            if code > 0xFFFF:
                utf16_count += 2  # surrogate pair in UTF-16
                self._has_non_bmp = True
            else:
                utf16_count += 1
        self._cp_to_utf16[n] = utf16_count
        self._total_utf16 = utf16_count

    @property
    def has_non_bmp(self) -> bool:
        """True if the text contains characters outside the Basic Multilingual Plane (BMP)."""
        return self._has_non_bmp

    @property
    def total_utf16_length(self) -> int:
        """Total length of the text in Java UTF-16 code units."""
        return self._total_utf16

    def codepoint_to_utf16(self, cp_offset: int) -> int:
        """Convert a Python code-point offset to Java UTF-16 code unit offset."""
        if cp_offset < 0:
            raise IndexError(f"Negative code-point offset: {cp_offset}")
        if cp_offset >= len(self._cp_to_utf16):
            # Clamp or calculate beyond length if needed
            return self._total_utf16 + (cp_offset - len(self._text))
        return self._cp_to_utf16[cp_offset]

    def utf16_to_codepoint(self, utf16_offset: int) -> int:
        """Convert a Java UTF-16 code unit offset to Python code-point offset."""
        if utf16_offset < 0:
            raise IndexError(f"Negative UTF-16 offset: {utf16_offset}")
        if not self._has_non_bmp:
            return utf16_offset
        idx = bisect.bisect_right(self._cp_to_utf16, utf16_offset) - 1
        return max(0, min(idx, len(self._text)))


def tokens_to_spans(
    tokens: Sequence[str],
    *,
    base_offset: int = 0,
    base_utf16_offset: int = 0,
    mapper: Optional[Utf16CodePointMapper] = None,
) -> tuple[TokenSpan, ...]:
    """Convert an ordered sequence of contiguous token strings into TokenSpans.

    Offsets are strictly cumulative and do not use substring searching.
    """
    spans: List[TokenSpan] = []
    current_cp = base_offset
    current_utf16 = base_utf16_offset

    for token in tokens:
        t_len = len(token)
        end_cp = current_cp + t_len
        if mapper is not None:
            utf16_start = mapper.codepoint_to_utf16(current_cp)
            utf16_end = mapper.codepoint_to_utf16(end_cp)
        else:
            # Fast-path calculation
            utf16_len = 0
            for ch in token:
                utf16_len += 2 if ord(ch) > 0xFFFF else 1
            utf16_start = current_utf16
            utf16_end = current_utf16 + utf16_len

        spans.append(
            TokenSpan(
                text=token,
                start=current_cp,
                end=end_cp,
                utf16_start=utf16_start,
                utf16_end=utf16_end,
            )
        )
        current_cp = end_cp
        current_utf16 = utf16_end

    return tuple(spans)


def sentences_to_spans(
    sentences: Sequence[str],
    mapper: Optional[Utf16CodePointMapper] = None,
) -> tuple[SentenceSpan, ...]:
    """Convert an ordered sequence of contiguous sentence strings into SentenceSpans."""
    spans: List[SentenceSpan] = []
    current_cp = 0
    current_utf16 = 0

    for sentence in sentences:
        s_len = len(sentence)
        end_cp = current_cp + s_len
        if mapper is not None:
            utf16_start = mapper.codepoint_to_utf16(current_cp)
            utf16_end = mapper.codepoint_to_utf16(end_cp)
        else:
            utf16_len = 0
            for ch in sentence:
                utf16_len += 2 if ord(ch) > 0xFFFF else 1
            utf16_start = current_utf16
            utf16_end = current_utf16 + utf16_len

        spans.append(
            SentenceSpan(
                text=sentence,
                start=current_cp,
                end=end_cp,
                utf16_start=utf16_start,
                utf16_end=utf16_end,
            )
        )
        current_cp = end_cp
        current_utf16 = utf16_end

    return tuple(spans)


def validate_spans_invariants(
    spans: Sequence[TextSpan],
    full_text: str,
    base_offset: int = 0,
) -> None:
    """Validate ordering, non-overlap, completeness, and source text equality invariants."""
    if not spans:
        if full_text:
            raise ValueError(f"Empty spans for non-empty text (len={len(full_text)})")
        return

    # Check concatenation matches full_text
    concatenated = "".join(s.text for s in spans)
    if concatenated != full_text:
        raise ValueError(
            f"Spans concatenation mismatch: got {len(concatenated)} chars, expected {len(full_text)}"
        )

    # Check contiguous monotonic bounds
    prev_end = base_offset
    prev_utf16_end = spans[0].utf16_start
    for idx, s in enumerate(spans):
        if s.start != prev_end:
            raise ValueError(
                f"Span {idx} start ({s.start}) does not equal previous end ({prev_end})"
            )
        if s.utf16_start != prev_utf16_end:
            raise ValueError(
                f"Span {idx} utf16_start ({s.utf16_start}) does not equal previous utf16_end ({prev_utf16_end})"
            )
        # Slicing invariant
        local_start = s.start - base_offset
        local_end = s.end - base_offset
        if full_text[local_start:local_end] != s.text:
            raise ValueError(
                f"Span {idx} text mismatch: full_text[{local_start}:{local_end}] != {s.text!r}"
            )
        prev_end = s.end
        prev_utf16_end = s.utf16_end

    if prev_end != base_offset + len(full_text):
        raise ValueError(
            f"Final span end ({prev_end}) does not match expected ({base_offset + len(full_text)})"
        )
