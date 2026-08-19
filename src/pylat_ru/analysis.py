"""Morphology data model representing LanguageTool AnalyzedToken and AnalyzedTokenReadings.

These immutable classes capture the exact morphological readings, raw POS tag strings,
deterministic ordering, raw direct-tagger positions, and chunk tags produced by
the LanguageTool tagging and disambiguation pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, Optional, Pattern, Sequence, Union


@dataclass(frozen=True)
class AnalyzedToken:
    """An immutable individual morphology reading for a surface token.

    Attributes:
        token: The surface word token (normalized according to pipeline stage).
        lemma: The base form / lemma, or None if unknown.
        pos_tag: The exact LanguageTool POS tag string, or None if unknown.
    """

    token: str
    lemma: Optional[str] = None
    pos_tag: Optional[str] = None

    @property
    def has_no_pos_tag(self) -> bool:
        """Return True if this token has no POS tag (e.g. unknown token)."""
        return self.pos_tag is None

    @property
    def lemma_or_token(self) -> str:
        """Return lemma if present, otherwise token."""
        return self.lemma if self.lemma is not None else self.token

    def matches(self, other: AnalyzedToken) -> bool:
        """Check equality against another AnalyzedToken."""
        return (
            self.token == other.token
            and self.lemma == other.lemma
            and self.pos_tag == other.pos_tag
        )

    def __str__(self) -> str:
        lemma_str = self.lemma if self.lemma is not None else "null"
        tag_str = self.pos_tag if self.pos_tag is not None else "null"
        return f"{self.token}/[{lemma_str}]{tag_str}"


@dataclass(frozen=True)
class AnalyzedTokenReadings:
    """An immutable container for all morphology readings of a single token.

    Attributes:
        readings: Immutable sequence of AnalyzedToken readings in deterministic order.
        start_pos: Accumulated raw direct-tagger start position (Java UTF-16 code units).
        chunk_tags: Immutable tuple of chunk tag names (e.g. ('MayMissingYO',)).
    """

    readings: tuple[AnalyzedToken, ...]
    start_pos: int
    chunk_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.readings, tuple):
            object.__setattr__(self, "readings", tuple(self.readings))
        if not isinstance(self.chunk_tags, tuple):
            object.__setattr__(self, "chunk_tags", tuple(self.chunk_tags))

    @classmethod
    def create_null_token(cls, token: str, start_pos: int) -> AnalyzedTokenReadings:
        """Create an AnalyzedTokenReadings containing a single null/unknown reading."""
        null_reading = AnalyzedToken(token=token, lemma=None, pos_tag=None)
        return cls(readings=(null_reading,), start_pos=start_pos)

    @property
    def token(self) -> str:
        """Return surface token string from the first reading, or empty string."""
        return self.readings[0].token if self.readings else ""

    @property
    def is_pos_tag_unknown(self) -> bool:
        """Return True if this token has only one unknown reading with no lemma and no pos_tag."""
        return (
            len(self.readings) == 1
            and self.readings[0].lemma is None
            and self.readings[0].pos_tag is None
        )

    @property
    def is_tagged(self) -> bool:
        """Return True if at least one reading has a non-null POS tag."""
        return any(r.pos_tag is not None for r in self.readings)

    def has_pos_tag(self, tag: str) -> bool:
        """Return True if any reading has exact POS tag."""
        return any(r.pos_tag == tag for r in self.readings)

    def has_pos_tag_and_lemma(self, tag: str, lemma: str) -> bool:
        """Return True if any reading has both exact POS tag and exact lemma."""
        return any(r.pos_tag == tag and r.lemma == lemma for r in self.readings)

    def has_lemma(self, lemma: str) -> bool:
        """Return True if any reading has exact lemma."""
        return any(r.lemma == lemma for r in self.readings)

    def has_any_lemma(self, *lemmas: str) -> bool:
        """Return True if any reading has a lemma matching any of the candidates."""
        lemma_set = set(lemmas)
        return any(r.lemma in lemma_set for r in self.readings)

    def has_pos_tag_starting_with(self, prefix: str) -> bool:
        """Return True if any reading has a POS tag starting with prefix."""
        return any(
            r.pos_tag is not None and r.pos_tag.startswith(prefix)
            for r in self.readings
        )

    def matches_pos_tag_regex(self, pattern: Union[str, Pattern[str]]) -> bool:
        """Return True if any reading's POS tag matches regex pattern."""
        p = re.compile(pattern) if isinstance(pattern, str) else pattern
        return any(
            r.pos_tag is not None and p.search(r.pos_tag) is not None
            for r in self.readings
        )

    def matches_chunk_regex(self, pattern: Union[str, Pattern[str]]) -> bool:
        """Return True if any chunk tag matches regex pattern."""
        p = re.compile(pattern) if isinstance(pattern, str) else pattern
        return any(p.search(ct) is not None for ct in self.chunk_tags)

    def reading_with_tag_regex(
        self, pattern: Union[str, Pattern[str]]
    ) -> Optional[AnalyzedToken]:
        """Return the first reading whose POS tag matches regex pattern, or None."""
        p = re.compile(pattern) if isinstance(pattern, str) else pattern
        for r in self.readings:
            if r.pos_tag is not None and p.search(r.pos_tag) is not None:
                return r
        return None

    def reading_with_lemma(self, lemma: str) -> Optional[AnalyzedToken]:
        """Return the first reading with exact lemma, or None."""
        for r in self.readings:
            if r.lemma == lemma:
                return r
        return None

    def __iter__(self) -> Iterator[AnalyzedToken]:
        return iter(self.readings)

    def __len__(self) -> int:
        return len(self.readings)

    def __getitem__(self, index: int) -> AnalyzedToken:
        return self.readings[index]

    def __str__(self) -> str:
        readings_str = "|".join(str(r) for r in self.readings)
        if self.chunk_tags:
            return f"{readings_str} <{','.join(self.chunk_tags)}>"
        return readings_str
