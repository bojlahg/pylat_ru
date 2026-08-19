"""Morphology data model representing LanguageTool AnalyzedToken, AnalyzedTokenReadings, and AnalyzedSentence.

These classes capture the exact morphological readings, raw POS tag strings,
deterministic ordering, raw direct-tagger positions, chunk tags, whitespace mappings,
and sentence-level structures produced by the LanguageTool tagging and disambiguation pipeline.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Any, Iterator, List, Optional, Pattern, Sequence, Tuple, Union


SENT_START_TAG = "SENT_START"
SENT_END_TAG = "SENT_END"
PARAGRAPH_END_TAG = "PARA_END"


@dataclass(frozen=True)
class AnalyzedToken:
    """An immutable individual morphology reading for a surface token.

    Attributes:
        token: The surface word token.
        lemma: The base form / lemma, or None if unknown.
        pos_tag: The exact LanguageTool POS tag string, or None if unknown.
        is_whitespace_before: True if whitespace preceded this token.
    """

    token: str
    lemma: Optional[str] = None
    pos_tag: Optional[str] = None
    is_whitespace_before: bool = False

    @property
    def has_no_pos_tag(self) -> bool:
        """Return True if this token has no POS tag (e.g. unknown token)."""
        return self.pos_tag is None

    @property
    def has_no_tag(self) -> bool:
        """Alias for has_no_pos_tag to match LT AnalyzedToken API."""
        return self.pos_tag is None

    @property
    def lemma_or_token(self) -> str:
        """Return lemma if present and non-empty, otherwise token."""
        return self.lemma if (self.lemma is not None and self.lemma != "") else self.token

    def matches(self, other: AnalyzedToken) -> bool:
        """Check equality against another AnalyzedToken."""
        return (
            self.token == other.token
            and self.lemma == other.lemma
            and self.pos_tag == other.pos_tag
        )

    def to_short_string(self) -> str:
        """Return LanguageTool short string format: 'lemmaOrToken/posTag' or 'token'."""
        if self.pos_tag is None:
            return self.token
        return f"{self.lemma_or_token}/{self.pos_tag}"

    def __str__(self) -> str:
        return self.to_short_string()


@dataclass
class AnalyzedTokenReadings:
    """A container for all morphology readings of a single token.

    Attributes:
        readings: List of AnalyzedToken readings in deterministic order.
        start_pos: Character start position (or Java UTF-16 code units offset).
        chunk_tags: List of chunk tag names (e.g. ['MayMissingYO']).
        is_sentence_start: True if this is the artificial SENT_START pseudo-token.
        is_sentence_end: True if this token marks sentence end.
        is_paragraph_end: True if this token marks paragraph end.
        is_immunized: True if immunized against rules/antipatterns.
        is_ignore_spelling: True if spelling check should ignore this token.
        whitespace_before: Token string of preceding whitespace.
        pos_fix: Offset correction factor from stripped ignored characters.
        clean_token: Clean token used for dictionary lookup without accents.
        source_token: Original surface token from input text.
    """

    readings: List[AnalyzedToken]
    start_pos: int
    chunk_tags: List[str] = field(default_factory=list)
    is_sentence_start: bool = False
    is_sentence_end: bool = False
    is_paragraph_end: bool = False
    is_immunized: bool = False
    is_ignore_spelling: bool = False
    whitespace_before: Optional[str] = None
    pos_fix: int = 0
    clean_token: Optional[str] = None
    source_token: Optional[str] = None

    def __init__(
        self,
        readings: Union[Sequence[AnalyzedToken], AnalyzedToken, AnalyzedTokenReadings],
        start_pos: Optional[int] = None,
        chunk_tags: Optional[Sequence[str]] = None,
        is_sentence_start: bool = False,
        is_sentence_end: bool = False,
        is_paragraph_end: bool = False,
        is_immunized: bool = False,
        is_ignore_spelling: bool = False,
        whitespace_before: Optional[str] = None,
        pos_fix: int = 0,
        clean_token: Optional[str] = None,
        source_token: Optional[str] = None,
    ) -> None:
        if isinstance(readings, AnalyzedTokenReadings):
            src = readings
            self.readings = list(src.readings)
            self.start_pos = start_pos if start_pos is not None else src.start_pos
            self.chunk_tags = list(chunk_tags if chunk_tags is not None else src.chunk_tags)
            self.is_sentence_start = src.is_sentence_start or is_sentence_start
            self.is_sentence_end = src.is_sentence_end or is_sentence_end
            self.is_paragraph_end = src.is_paragraph_end or is_paragraph_end
            self.is_immunized = src.is_immunized or is_immunized
            self.is_ignore_spelling = src.is_ignore_spelling or is_ignore_spelling
            ws_val = whitespace_before if whitespace_before is not None else src.whitespace_before
            self.whitespace_before = ws_val if ws_val is not None else ""
            self.is_whitespace_before = bool(self.whitespace_before and self.whitespace_before.isspace())
            self.pos_fix = pos_fix or src.pos_fix
            self.clean_token = clean_token or src.clean_token
            self.source_token = source_token or src.source_token
        elif isinstance(readings, AnalyzedToken):
            self.readings = [readings]
            self.start_pos = start_pos if start_pos is not None else 0
            self.chunk_tags = list(chunk_tags) if chunk_tags is not None else []
            self.is_sentence_start = is_sentence_start or (readings.pos_tag == SENT_START_TAG)
            self.is_sentence_end = is_sentence_end or (readings.pos_tag == SENT_END_TAG)
            self.is_paragraph_end = is_paragraph_end or (readings.pos_tag == PARAGRAPH_END_TAG)
            self.is_immunized = is_immunized
            self.is_ignore_spelling = is_ignore_spelling
            self.whitespace_before = whitespace_before if whitespace_before is not None else ""
            self.is_whitespace_before = bool(self.whitespace_before and self.whitespace_before.isspace())
            self.pos_fix = pos_fix
            self.clean_token = clean_token
            self.source_token = source_token
        else:
            self.readings = list(readings)
            self.start_pos = start_pos if start_pos is not None else 0
            self.chunk_tags = list(chunk_tags) if chunk_tags is not None else []
            self.is_sentence_start = is_sentence_start or (
                len(self.readings) > 0 and any(r.pos_tag == SENT_START_TAG for r in self.readings)
            )
            self.is_sentence_end = is_sentence_end or (
                len(self.readings) > 0 and any(r.pos_tag == SENT_END_TAG for r in self.readings)
            )
            self.is_paragraph_end = is_paragraph_end or (
                len(self.readings) > 0 and any(r.pos_tag == PARAGRAPH_END_TAG for r in self.readings)
            )
            self.is_immunized = is_immunized
            self.is_ignore_spelling = is_ignore_spelling
            self.whitespace_before = whitespace_before if whitespace_before is not None else ""
            self.is_whitespace_before = bool(self.whitespace_before and self.whitespace_before.isspace())
            self.pos_fix = pos_fix
            self.clean_token = clean_token
            self.source_token = source_token

    @classmethod
    def create_null_token(
        cls,
        token: str,
        start_pos: int,
        source_token: Optional[str] = None,
        clean_token: Optional[str] = None,
        pos_fix: int = 0,
    ) -> AnalyzedTokenReadings:
        """Create an AnalyzedTokenReadings containing a single null/unknown reading."""
        null_reading = AnalyzedToken(token=token, lemma=None, pos_tag=None)
        return cls(
            readings=[null_reading],
            start_pos=start_pos,
            source_token=source_token or token,
            clean_token=clean_token or token,
            pos_fix=pos_fix,
        )

    @classmethod
    def create_sentence_start_token(cls, start_pos: int = 0) -> AnalyzedTokenReadings:
        """Create the artificial SENT_START token reading."""
        start_reading = AnalyzedToken(token="", lemma=None, pos_tag=SENT_START_TAG)
        return cls(
            readings=[start_reading],
            start_pos=start_pos,
            is_sentence_start=True,
            source_token="",
            clean_token="",
        )

    @property
    def clean_token(self) -> str:
        """Return clean token if set, otherwise token surface string."""
        return self._clean_token if self._clean_token is not None else self.token

    @clean_token.setter
    def clean_token(self, val: Optional[str]) -> None:
        self._clean_token = val

    @property
    def token(self) -> str:
        """Return surface token string."""
        if self.source_token is not None:
            return self.source_token
        if self.readings and self.readings[0].token:
            return self.readings[0].token
        return ""

    def is_whitespace(self) -> bool:
        """Return True if token is empty or represents pure whitespace matching Java LT."""
        tok = self.token
        return len(tok) == 0 or tok.isspace()

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

    def has_reading(self) -> bool:
        """Return True if there is at least one non-null reading."""
        return len(self.readings) > 0 and not self.is_pos_tag_unknown

    def get_readings_length(self) -> int:
        """Return number of readings."""
        return len(self.readings)

    def get_analyzed_token(self, index: int) -> AnalyzedToken:
        """Return AnalyzedToken at index."""
        return self.readings[index]

    def set_whitespace_before(self, prev_token: str) -> None:
        """Set whitespace before token matching Java LT AnalyzedTokenReadings.setWhitespaceBefore."""
        is_ws = bool(prev_token and prev_token.isspace())
        self.is_whitespace_before = is_ws
        self.whitespace_before = prev_token if is_ws else ""
        self.readings = [
            dataclasses.replace(r, is_whitespace_before=is_ws) for r in self.readings
        ]

    def add_reading(self, reading: AnalyzedToken, rule_id: Optional[str] = None) -> None:
        """Add a reading to this token matching Java LT AnalyzedTokenReadings.addReading."""
        l: List[AnalyzedToken] = []
        if self.readings:
            l.extend(self.readings[:-1])
            last_r = self.readings[-1]
            if last_r.pos_tag is not None:
                l.append(last_r)
        if reading.is_whitespace_before != self.is_whitespace_before:
            reading = dataclasses.replace(reading, is_whitespace_before=self.is_whitespace_before)
        l.append(reading)
        self.readings = l
        if len(reading.token) > len(self.token):
            self.source_token = reading.token
        if any(r.pos_tag == SENT_END_TAG for r in self.readings):
            self.is_sentence_end = True
        if any(r.pos_tag == SENT_START_TAG for r in self.readings):
            self.is_sentence_start = True
        if any(r.pos_tag == PARAGRAPH_END_TAG for r in self.readings):
            self.is_paragraph_end = True

    def remove_reading(
        self,
        reading_or_tag_regex: Union[AnalyzedToken, str, Pattern[str]],
        rule_id: Optional[str] = None,
    ) -> None:
        """Remove reading(s) matching exact AnalyzedToken or POS tag regex pattern.

        Matches Java LT removeReading:
        - If SENT_END reading was removed, restores it via set_sentence_end().
        - If PARAGRAPH_END reading was removed, restores it via set_paragraph_end().
        - If removing leaves 0 readings, creates a single null reading with the ORIGINAL token surface.
        """
        orig_token_surface = self.token or (self.source_token or "")
        removed_sent_end = False
        removed_para_end = False
        l: List[AnalyzedToken] = []

        if isinstance(reading_or_tag_regex, AnalyzedToken):
            target = reading_or_tag_regex
            for r in self.readings:
                if not r.matches(target):
                    l.append(r)
                else:
                    if r.pos_tag == SENT_END_TAG:
                        removed_sent_end = True
                    if r.pos_tag == PARAGRAPH_END_TAG:
                        removed_para_end = True
        else:
            p = (
                re.compile(reading_or_tag_regex)
                if isinstance(reading_or_tag_regex, str)
                else reading_or_tag_regex
            )
            for r in self.readings:
                if r.pos_tag is not None and p.fullmatch(r.pos_tag):
                    if r.pos_tag == SENT_END_TAG:
                        removed_sent_end = True
                    if r.pos_tag == PARAGRAPH_END_TAG:
                        removed_para_end = True
                else:
                    l.append(r)

        if not l:
            null_tok = AnalyzedToken(
                token=orig_token_surface,
                lemma=None,
                pos_tag=None,
                is_whitespace_before=self.is_whitespace_before,
            )
            l.append(null_tok)

        self.readings = l
        if removed_sent_end:
            self.is_sentence_end = False
            self.set_sentence_end(True)
        if removed_para_end:
            self.is_paragraph_end = False
            self.set_paragraph_end(True)

    def set_sentence_end(self, value: bool = True) -> None:
        """Mark this token as sentence end matching Java LT setSentEnd()."""
        if value:
            if not any(r.pos_tag == SENT_END_TAG for r in self.readings):
                lemma = self.readings[0].lemma if self.readings else None
                sent_end = AnalyzedToken(token=self.token, lemma=lemma, pos_tag=SENT_END_TAG)
                self.add_reading(sent_end, "")
        else:
            self.is_sentence_end = False
            self.readings = [r for r in self.readings if r.pos_tag != SENT_END_TAG]

    def set_paragraph_end(self, value: bool = True) -> None:
        """Mark this token as paragraph end matching Java LT setParagraphEnd()."""
        if value:
            if not any(r.pos_tag == PARAGRAPH_END_TAG for r in self.readings):
                lemma = self.readings[0].lemma if self.readings else None
                para_end = AnalyzedToken(token=self.token, lemma=lemma, pos_tag=PARAGRAPH_END_TAG)
                self.add_reading(para_end, "")
        else:
            self.is_paragraph_end = False
            self.readings = [r for r in self.readings if r.pos_tag != PARAGRAPH_END_TAG]

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

    def immunize(self, line_number: Optional[int] = None) -> None:
        """Mark this token as immunized."""
        self.is_immunized = True

    def ignore_spelling(self) -> None:
        """Mark this token to ignore spelling check."""
        self.is_ignore_spelling = True

    def get_readings(self) -> List[AnalyzedToken]:
        """Return list of readings."""
        return list(self.readings)

    def to_short_string(self, delimiter: str = ",") -> str:
        """Format token and readings: 'token[reading1,reading2,...]'."""
        if self.is_sentence_start:
            return "<S>"
        if not self.readings or self.is_pos_tag_unknown:
            return f"{self.token}[{self.token}]"
        # Format readings, filtering out SENT_END from ordinary short string display unless only reading
        visible_readings = [r for r in self.readings if r.pos_tag != SENT_END_TAG]
        if not visible_readings:
            visible_readings = self.readings
        readings_str = delimiter.join(r.to_short_string() for r in visible_readings)
        return f"{self.token}[{readings_str}]"

    def to_string(self, delimiter: str = ",", include_chunks: bool = True) -> str:
        """Format token with chunk tags: 'token[reading1,reading2,...|chunks]'."""
        base = self.to_short_string(delimiter)
        if include_chunks and self.chunk_tags:
            chunks_str = "|".join(self.chunk_tags)
            if base.endswith("]"):
                base = base[:-1] + f",{chunks_str}]"
        if self.is_immunized:
            if base.endswith("]"):
                base = base[:-1] + "{!}]"
        return base

    def __iter__(self) -> Iterator[AnalyzedToken]:
        return iter(self.readings)

    def __len__(self) -> int:
        return len(self.readings)

    def __getitem__(self, index: int) -> AnalyzedToken:
        return self.readings[index]

    def __str__(self) -> str:
        return self.to_string(delimiter=",", include_chunks=True)


class AnalyzedSentence:
    """A sentence that has been tokenized, tagged, and analyzed.

    Attributes:
        tokens: Full sequence of AnalyzedTokenReadings (including SENT_START and whitespace).
        pre_disambig_tokens: Snapshot of tokens before disambiguation.
        non_blank_tokens: Sequence of AnalyzedTokenReadings without whitespace tokens.
        wh_positions: Mapping from non-blank index to original token index in tokens.
    """

    def __init__(
        self,
        tokens: Sequence[AnalyzedTokenReadings],
        pre_disambig_tokens: Optional[Sequence[AnalyzedTokenReadings]] = None,
    ) -> None:
        self.tokens: List[AnalyzedTokenReadings] = [
            AnalyzedTokenReadings(t) for t in tokens
        ]
        self.pre_disambig_tokens: List[AnalyzedTokenReadings] = (
            [AnalyzedTokenReadings(t) for t in pre_disambig_tokens]
            if pre_disambig_tokens is not None
            else [AnalyzedTokenReadings(t) for t in tokens]
        )

        wh_positions: List[int] = []
        non_blank: List[AnalyzedTokenReadings] = []
        for i, t in enumerate(self.tokens):
            if i == 0 or not t.is_whitespace():
                wh_positions.append(i)
                non_blank.append(t)

        self.wh_positions: List[int] = wh_positions
        self.non_blank_tokens: List[AnalyzedTokenReadings] = non_blank

    def get_tokens(self) -> List[AnalyzedTokenReadings]:
        """Return all tokens including whitespace and SENT_START."""
        return self.tokens

    def get_pre_disambig_tokens(self) -> List[AnalyzedTokenReadings]:
        """Return pre-disambiguation tokens."""
        return self.pre_disambig_tokens

    def get_tokens_without_whitespace(self) -> List[AnalyzedTokenReadings]:
        """Return non-blank tokens (excluding whitespace, including SENT_START)."""
        return self.non_blank_tokens

    def get_non_whitespace_token_count(self) -> int:
        """Return count of non-whitespace tokens."""
        return len(self.non_blank_tokens)

    def get_original_position(self, non_wh_pos: int) -> int:
        """Map non-whitespace token index to original token array index."""
        if 0 <= non_wh_pos < len(self.wh_positions):
            return self.wh_positions[non_wh_pos]
        return non_wh_pos

    def get_text(self) -> str:
        """Reconstruct original text from token surface strings."""
        return "".join(t.token for t in self.tokens if not t.is_sentence_start)

    def to_short_string(self, reading_delimiter: str = ",") -> str:
        """Return string representation without chunk tags."""
        return self.to_string(reading_delimiter=reading_delimiter, include_chunks=False)

    def to_string(
        self, reading_delimiter: str = ",", include_chunks: bool = True
    ) -> str:
        """Return string representation of analyzed sentence matching LanguageTool."""
        parts: List[str] = []
        for t in self.tokens:
            if t.is_whitespace():
                parts.append(t.token)
            else:
                parts.append(t.to_string(delimiter=reading_delimiter, include_chunks=include_chunks))
        return "".join(parts)

    def copy(self) -> AnalyzedSentence:
        """Create a deep copy of this AnalyzedSentence."""
        return AnalyzedSentence(
            tokens=[AnalyzedTokenReadings(t) for t in self.tokens],
            pre_disambig_tokens=[AnalyzedTokenReadings(t) for t in self.pre_disambig_tokens],
        )

    def __str__(self) -> str:
        return self.to_string(reading_delimiter=",", include_chunks=True)

    def __repr__(self) -> str:
        return f"AnalyzedSentence({self.to_short_string()})"
