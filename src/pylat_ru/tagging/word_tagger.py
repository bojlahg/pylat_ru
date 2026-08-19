"""Word-level taggers: MorfologikTagger, ManualTagger, and CombiningTagger."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, TextIO, Union

from pylat_ru.morfologik.dictionary import MorfologikDictionary
from pylat_ru.tagging.errors import ManualTaggerFormatError, TaggerResourceError


@dataclass(frozen=True)
class TaggedWord:
    """An immutable tagged word entry with a lemma and a POS tag.

    Matches LanguageTool org.languagetool.tagging.TaggedWord.
    """

    lemma: Optional[str]
    pos_tag: Optional[str]

    def __str__(self) -> str:
        lemma_str = self.lemma if self.lemma is not None else "null"
        tag_str = self.pos_tag if self.pos_tag is not None else "null"
        return f"[{lemma_str}]{tag_str}"


class WordTagger(Protocol):
    """Protocol for word-level morphological lookup taggers."""

    def tag(self, word: str) -> tuple[TaggedWord, ...]:
        """Look up all TaggedWord readings for the exact input word."""
        ...


class MorfologikTagger:
    """Word tagger wrapping native Morfologik dictionary lookup.

    Matches LanguageTool org.languagetool.tagging.MorfologikTagger.
    """

    def __init__(self, dictionary: MorfologikDictionary) -> None:
        self.dictionary = dictionary

    def tag(self, word: str) -> tuple[TaggedWord, ...]:
        """Look up morphological readings from the binary Morfologik dictionary."""
        entries = self.dictionary.lookup(word)
        return tuple(TaggedWord(lemma=e.stem, pos_tag=e.tag) for e in entries)


def _java_regex_split(pattern: re.Pattern[str], text: str) -> list[str]:
    """Split text by regular expression matching Java Pattern.split(text, 0) semantics.

    Java Pattern.split(text) characteristics preserved:
      1. Capturing groups in pattern are not returned as extra items in the split array.
      2. Trailing empty strings at the end of the split array are discarded.
    """
    result: list[str] = []
    last_end = 0
    for match in pattern.finditer(text):
        result.append(text[last_end : match.start()])
        last_end = match.end()
    result.append(text[last_end:])

    while len(result) > 1 and result[-1] == "":
        result.pop()

    return result


class ManualTagger:
    """Word tagger parsing plain-text dictionary files (added.txt, removed.txt).

    Matches LanguageTool org.languagetool.tagging.ManualTagger exact semantics:
      - UTF-8 encoded plain text with 3 columns: fullform, baseform, postag.
      - Default separator is tab character (\t).
      - Can be altered via '#separatorRegExp=<regex>' directive.
      - Empty lines and lines starting with '#' are ignored.
      - Trailing inline comments starting with '#' are stripped.
      - POS tags have whitespace trimmed.
      - Non-breaking spaces (\u00A0) raise ManualTaggerFormatError.
      - Invalid field counts or malformed regex directives raise ManualTaggerFormatError.
    """

    DEFAULT_SEPARATOR = "\t"

    def __init__(
        self,
        sources: Union[
            str,
            Path,
            TextIO,
            bytes,
            Iterable[Union[str, Path, TextIO, bytes]],
        ],
    ) -> None:
        self._map: Dict[str, List[TaggedWord]] = {}
        if isinstance(sources, (str, Path, bytes)) or hasattr(sources, "read"):
            self._load_source(sources)  # type: ignore[arg-type]
        else:
            for s in sources:
                self._load_source(s)

    def _load_source(self, source: Union[str, Path, TextIO, bytes]) -> None:
        """Parse a single manual dictionary stream, path, or bytes."""
        if isinstance(source, Path) or (
            isinstance(source, str) and "\n" not in source and Path(source).is_file()
        ):
            path = Path(source)
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                raise TaggerResourceError(
                    f"Failed to read manual tagger resource file '{path}': {e}"
                ) from e
            self._parse_text(content, source_name=str(path))
        elif isinstance(source, bytes):
            try:
                content = source.decode("utf-8")
            except Exception as e:
                raise ManualTaggerFormatError(
                    f"Failed to decode manual tagger bytes as UTF-8: {e}"
                ) from e
            self._parse_text(content, source_name="<bytes>")
        elif isinstance(source, str):
            self._parse_text(source, source_name="<string>")
        elif hasattr(source, "read"):
            content = source.read()
            if isinstance(content, bytes):
                content = content.decode("utf-8")
            self._parse_text(content, source_name="<stream>")
        else:
            raise TaggerResourceError(f"Unsupported manual tagger source type: {type(source)}")

    def _parse_text(self, text: str, source_name: str) -> None:
        """Parse manual tagger text following exact LanguageTool rules."""
        sep_pattern: Optional[re.Pattern[str]] = None
        lines = text.splitlines()

        for line_idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip(" \t\r\n")
            if not line:
                continue

            if line.startswith("#separatorRegExp="):
                raw_sep = line[len("#separatorRegExp=") :]
                if not raw_sep:
                    raise ManualTaggerFormatError(
                        f"Empty regular expression in '#separatorRegExp=' directive at Line {line_idx} in '{source_name}'"
                    )
                try:
                    sep_pattern = re.compile(raw_sep)
                except re.error as e:
                    raise ManualTaggerFormatError(
                        f"Invalid regular expression '{raw_sep}' in '#separatorRegExp=' directive at Line {line_idx} in '{source_name}': {e}"
                    ) from e
                continue

            if line.startswith("#"):
                continue

            if "\u00a0" in line:
                raise ManualTaggerFormatError(
                    f"Line {line_idx} in '{source_name}' contains a non-breaking space (\\u00A0), "
                    f"which is probably an error: {line}"
                )

            # Strip inline comment starting with # and trim (ASCII whitespace)
            clean_line = line.split("#", 1)[0].strip(" \t\r\n")
            if not clean_line:
                continue

            # Split fields by separator
            if sep_pattern is None:
                parts = clean_line.split("\t")
            else:
                try:
                    parts = _java_regex_split(sep_pattern, clean_line)
                except Exception as e:
                    raise ManualTaggerFormatError(
                        f"Error splitting line with regular expression '{sep_pattern.pattern}' at Line {line_idx} in '{source_name}': {e}"
                    ) from e

            if len(parts) != 3:
                raise ManualTaggerFormatError(
                    f"Invalid format at Line {line_idx} in '{source_name}': expected 3 fields, got {len(parts)} in '{line}'"
                )

            fullform = parts[0]
            baseform = parts[1]
            postag = parts[2].strip(" \t\r\n")

            entry = TaggedWord(lemma=baseform, pos_tag=postag)
            if fullform not in self._map:
                self._map[fullform] = []
            self._map[fullform].append(entry)

    def tag(self, word: str) -> tuple[TaggedWord, ...]:
        """Look up readings from the manual dictionary for word."""
        return tuple(self._map.get(word, ()))

    @property
    def entry_count(self) -> int:
        """Return total count of distinct fullforms."""
        return len(self._map)

    @property
    def total_readings_count(self) -> int:
        """Return total count of all TaggedWord readings across all fullforms."""
        return sum(len(readings) for readings in self._map.values())


class CombiningTagger:
    """Combines a base tagger (e.g. Morfologik), manual additions, and manual removals.

    Matches LanguageTool org.languagetool.tagging.CombiningTagger semantics:
      1. Manual additions (tagger2) are added FIRST.
      2. Base tagger (tagger1) is added SECOND (if overwriteWithSecondTagger is False or additions empty).
      3. Exact readings present in removal_tagger are removed.
    """

    def __init__(
        self,
        tagger1: WordTagger,
        tagger2: Optional[WordTagger] = None,
        removal_tagger: Optional[WordTagger] = None,
        overwrite_with_second: bool = False,
    ) -> None:
        self.tagger1 = tagger1
        self.tagger2 = tagger2
        self.removal_tagger = removal_tagger
        self.overwrite_with_second = overwrite_with_second

    def tag(self, word: str) -> tuple[TaggedWord, ...]:
        """Combine manual additions, base tagger readings, and apply removals."""
        result: List[TaggedWord] = []

        if self.tagger2 is not None:
            result.extend(self.tagger2.tag(word))

        if not self.overwrite_with_second or len(result) == 0:
            result.extend(self.tagger1.tag(word))

        if self.removal_tagger is not None:
            removals = self.removal_tagger.tag(word)
            if removals:
                removal_set = set(removals)
                result = [tw for tw in result if tw not in removal_set]

        return tuple(result)
