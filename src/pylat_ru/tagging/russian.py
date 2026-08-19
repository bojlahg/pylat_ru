"""Native Python implementation of RussianTagger and BaseTagger for LanguageTool Russian."""

from __future__ import annotations

import importlib.resources
from pathlib import Path
from typing import List, Optional, Sequence, Union

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.morfologik.dictionary import MorfologikDictionary
from pylat_ru.tagging.errors import TaggerResourceError
from pylat_ru.tagging.string_tools import is_mixed_case, uppercase_first_char
from pylat_ru.tagging.word_tagger import (
    CombiningTagger,
    ManualTagger,
    MorfologikTagger,
    TaggedWord,
    WordTagger,
)

# Literal acute vowel combining sequences used in RussianTagger.java
# Each is base Cyrillic vowel + U+0301 COMBINING ACUTE ACCENT
ACUTE_VOWELS = (
    "е\u0301",
    "о\u0301",
    "а\u0301",
    "у\u0301",
    "и\u0301",
    "ю\u0301",
    "ы\u0301",
    "э\u0301",
    "я\u0301",
)

# Literal replacements performed by RussianTagger.java on tokens with length > 1
NORMALIZATION_REPLACEMENTS = (
    ("о\u0301", "о"),
    ("а\u0301", "а"),
    ("е\u0301", "е"),
    ("у\u0301", "у"),
    ("и\u0301", "и"),
    ("ы\u0301", "ы"),
    ("э\u0301", "э"),
    ("ю\u0301", "ю"),
    ("я\u0301", "я"),
    ("о\u0300", "о"),
    ("а\u0300", "а"),
    ("е\u0300", "е"),
    ("у\u0300", "у"),
    ("\u045d", "и"),  # ѝ (Cyrillic Small Letter I with Grave) -> и
    ("ы\u0300", "ы"),
    ("э\u0300", "э"),
    ("ю\u0300", "ю"),
    ("я\u0300", "я"),
    ("\u02bc", "ъ"),  # ʼ (Modifier Letter Apostrophe) -> ъ
)


def _get_default_resource_path(resource_name: str) -> Path:
    """Resolve a default Russian resource file path from package resources."""
    try:
        # Use importlib.resources.files for Python >= 3.9
        res_dir = importlib.resources.files("pylat_ru.resources.ru")
        p = Path(str(res_dir.joinpath(resource_name)))
        if p.is_file():
            return p
    except Exception:
        pass

    # Fallback to local source path relative to this file
    local_path = (
        Path(__file__).resolve().parent.parent / "resources" / "ru" / resource_name
    )
    if local_path.is_file():
        return local_path

    raise TaggerResourceError(
        f"Default Russian tagger resource '{resource_name}' not found in package resources."
    )


def utf16_len(text: str) -> int:
    """Compute length in Java UTF-16 code units (where characters > U+FFFF count as 2)."""
    return sum(2 if ord(c) > 0xFFFF else 1 for c in text)


class RussianTagger:
    """Native Python implementation of LanguageTool's RussianTagger + BaseTagger morphology engine.

    Pipeline:
      1. RussianTagger normalization (acute/grave accents, modifier apostrophe)
      2. BaseTagger case fallback (exact -> lower -> uppercase-first -> unknown)
      3. Combining word tagger (manual additions -> binary dictionary -> manual removals)
      4. MayMissingYO chunk tagging
      5. AnalyzedTokenReadings output with exact raw POS tags and UTF-16 positions
    """

    _instance: Optional[RussianTagger] = None

    @classmethod
    def get_instance(cls) -> RussianTagger:
        """Get or create singleton RussianTagger instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(
        self,
        dict_path: Optional[Union[str, Path]] = None,
        info_path: Optional[Union[str, Path]] = None,
        manual_additions_paths: Optional[Sequence[Union[str, Path]]] = None,
        manual_removals_paths: Optional[Sequence[Union[str, Path]]] = None,
        tag_lowercase_with_uppercase: bool = True,
    ) -> None:
        self.tag_lowercase_with_uppercase = tag_lowercase_with_uppercase

        # 1. Resolve dictionary files
        d_path = Path(dict_path) if dict_path else _get_default_resource_path("russian.dict")
        i_path = Path(info_path) if info_path else _get_default_resource_path("russian.info")

        if not d_path.is_file():
            raise TaggerResourceError(f"Russian dictionary file not found: {d_path}")
        if not i_path.is_file():
            raise TaggerResourceError(f"Russian dictionary info file not found: {i_path}")

        self.dictionary = MorfologikDictionary.open(d_path, i_path)
        self.morfologik_tagger = MorfologikTagger(self.dictionary)

        # 2. Resolve manual additions files
        if manual_additions_paths is None:
            add_paths = [
                _get_default_resource_path("added.txt"),
                _get_default_resource_path("added_custom.txt"),
            ]
        else:
            add_paths = [Path(p) for p in manual_additions_paths]

        self.manual_additions = ManualTagger(add_paths)

        # 3. Resolve manual removals files
        if manual_removals_paths is None:
            rem_paths = [
                _get_default_resource_path("removed.txt"),
                _get_default_resource_path("removed_custom.txt"),
            ]
        else:
            rem_paths = [Path(p) for p in manual_removals_paths]

        self.manual_removals = ManualTagger(rem_paths)

        # 4. Combining tagger
        self.word_tagger: WordTagger = CombiningTagger(
            tagger1=self.morfologik_tagger,
            tagger2=self.manual_additions,
            removal_tagger=self.manual_removals,
            overwrite_with_second=False,
        )

    def get_analyzed_tokens(self, word: str) -> List[AnalyzedToken]:
        """Look up all AnalyzedToken readings for normalized word following BaseTagger case fallback."""
        lower_word = word.lower()
        is_lowercase = word == lower_word
        is_mixed = is_mixed_case(word)

        exact_readings = self.word_tagger.tag(word)
        exact_tokens = [
            AnalyzedToken(token=word, lemma=tw.lemma, pos_tag=tw.pos_tag)
            for tw in exact_readings
        ]

        if is_lowercase:
            lower_tokens = exact_tokens
        else:
            lower_readings = self.word_tagger.tag(lower_word)
            lower_tokens = [
                AnalyzedToken(token=word, lemma=tw.lemma, pos_tag=tw.pos_tag)
                for tw in lower_readings
            ]

        result: List[AnalyzedToken] = list(exact_tokens)

        if not is_lowercase and not is_mixed:
            result.extend(lower_tokens)

        if (
            self.tag_lowercase_with_uppercase
            and len(lower_tokens) == 0
            and len(exact_tokens) == 0
            and is_lowercase
        ):
            uc_word = uppercase_first_char(word)
            uc_readings = self.word_tagger.tag(uc_word)
            if uc_readings:
                result.extend(
                    AnalyzedToken(token=word, lemma=tw.lemma, pos_tag=tw.pos_tag)
                    for tw in uc_readings
                )

        if not result:
            result.append(AnalyzedToken(token=word, lemma=None, pos_tag=None))

        return result

    def tag(self, sentence_tokens: Sequence[str]) -> tuple[AnalyzedTokenReadings, ...]:
        """Perform Russian morphological analysis on a sequence of tokens.

        Matches LanguageTool RussianTagger.tag(List<String>) exact behavior.
        """
        token_readings: List[AnalyzedTokenReadings] = []
        pos = 0

        for raw_word in sentence_tokens:
            word = raw_word
            may_missing_yo = False

            if len(word) > 1:
                # Pre-normalization MayMissingYO candidate check
                if (
                    "ё" not in word
                    and "Ё" not in word
                    and ("е" in word or "Е" in word)
                    and not any(av in word for av in ACUTE_VOWELS)
                ):
                    may_missing_yo = True

                # Exact literal normalization sequence from RussianTagger.java
                for src, dst in NORMALIZATION_REPLACEMENTS:
                    word = word.replace(src, dst)

            analyzed_tokens = self.get_analyzed_tokens(word)
            atr = AnalyzedTokenReadings(readings=tuple(analyzed_tokens), start_pos=pos)

            if may_missing_yo:
                word_lc = word.lower().replace("е", "ё")
                if len(self.word_tagger.tag(word_lc)) == 0:
                    may_missing_yo = False

            if may_missing_yo:
                atr = AnalyzedTokenReadings(
                    readings=atr.readings,
                    start_pos=atr.start_pos,
                    chunk_tags=("MayMissingYO",),
                )

            token_readings.append(atr)
            pos += utf16_len(word)

        return tuple(token_readings)

    def tag_word(self, word: str) -> AnalyzedTokenReadings:
        """Convenience method to tag a single word."""
        return self.tag([word])[0]
