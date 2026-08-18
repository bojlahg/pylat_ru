"""src/pylat_ru/tagset.py

Lossless representation and parsing of LanguageTool Russian part-of-speech (POS) tags.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set, Tuple, Union

ANIMACY_TAGS = frozenset({"Anim", "Inanim", "Inanimanim"})
GENDER_TAGS = frozenset({"Masc", "Fem", "Neut"})
NUMBER_TAGS = frozenset({"Sin", "PL"})
CASE_TAGS = frozenset({"Nom", "R", "2R", "D", "V", "T", "P", "2P", "Z"})
TENSE_TAGS = frozenset({"Past", "Real", "Fut", "INF"})
PERSON_TAGS = frozenset({"P1", "P2", "P3"})
VOICE_TAGS = frozenset({"DST", "STR"})
ASPECT_TAGS = frozenset({"IMPFV", "PFV", "2PFV"})
TRANSITIVITY_TAGS = frozenset({"TRANS", "INTR"})


@dataclass(frozen=True)
class RussianTag:
    """Lossless representation of a LanguageTool Russian POS tag.

    Attributes:
        raw: The exact, authoritative raw tag string from LanguageTool.
        parts: Tuple of colon-separated components, preserving empty slots (e.g. ('VB', 'INF', '')).
    """

    raw: str
    parts: Tuple[str, ...]

    def __str__(self) -> str:
        return self.raw

    def __repr__(self) -> str:
        return f"RussianTag({self.raw!r})"

    @property
    def pos(self) -> str:
        """Primary coarse part-of-speech prefix (e.g. 'NN', 'VB', 'ADJ', 'ADV')."""
        return self.parts[0] if self.parts else ""

    @property
    def animacy(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in ANIMACY_TAGS:
                return part
        return None

    @property
    def gender(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in GENDER_TAGS:
                return part
        return None

    @property
    def number(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in NUMBER_TAGS:
                return part
        return None

    @property
    def case(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in CASE_TAGS:
                return part
        return None

    @property
    def tense(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in TENSE_TAGS:
                return part
        return None

    @property
    def person(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in PERSON_TAGS:
                return part
        return None

    @property
    def voice(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in VOICE_TAGS:
                return part
        return None

    @property
    def aspect(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in ASPECT_TAGS:
                return part
        return None

    @property
    def transitivity(self) -> Optional[str]:
        for part in self.parts[1:]:
            if part in TRANSITIVITY_TAGS:
                return part
        return None

    @property
    def is_short(self) -> bool:
        return self.pos == "PT_Short" or "Short" in self.parts

    @property
    def is_comparative(self) -> bool:
        return "Comp" in self.parts

    @property
    def is_superlative(self) -> bool:
        return "Sup" in self.parts


def parse_tag(raw_tag: str) -> RussianTag:
    """Parse a raw LanguageTool POS tag string losslessly.

    Splitting by ':' strictly preserves empty tokens (e.g. 'VB:INF:' -> ('VB', 'INF', '')).
    """
    parts = tuple(raw_tag.split(":"))
    return RussianTag(raw=raw_tag, parts=parts)


def load_tags_file(tags_path: Union[str, Path]) -> List[RussianTag]:
    """Load and parse all tags from a tags_russian.txt file, preserving order and whitespace-stripped lines."""
    p = Path(tags_path)
    tags: List[RussianTag] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                tags.append(parse_tag(stripped))
    return tags
