"""synthesis/manual.py

Manual synthesis overlay loader matching LanguageTool org.languagetool.synthesis.ManualSynthesizer.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, TextIO, Tuple, Union

from pylat_ru.synthesis.errors import ManualSynthesizerFormatError, SynthesisResourceError
from pylat_ru.utils import java_regex_split


class ManualSynthesizer:
    """Manual synthesizer overlay parsing plain-text dictionary files (added.txt, removed.txt).

    Matches LanguageTool org.languagetool.synthesis.ManualSynthesizer exact semantics:
      - UTF-8 encoded plain text with 3 columns: form, lemma, pos_tag.
      - Plain-text contains full forms (not encoded suffix syntax).
      - Default separator is tab character (\\t).
      - Can be altered via '#separatorRegExp=<regex>' directive.
      - Empty lines and lines starting with '#' are ignored.
      - Trailing inline comments starting with '#' are stripped.
      - Line is trimmed before splitting.
      - Non-breaking spaces (\\u00A0) raise ManualSynthesizerFormatError.
      - Invalid field counts or malformed regex directives raise ManualSynthesizerFormatError.
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
        self._mapping: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self._possible_tags: Set[str] = set()

        if isinstance(sources, (str, Path, bytes)) or hasattr(sources, "read"):
            self._load_source(sources)  # type: ignore[arg-type]
        else:
            for s in sources:
                self._load_source(s)

    def _load_source(self, source: Union[str, Path, TextIO, bytes]) -> None:
        """Parse a single manual synthesis stream, path, or bytes."""
        if isinstance(source, Path) or (
            isinstance(source, str) and "\n" not in source and Path(source).is_file()
        ):
            path = Path(source)
            if not path.is_file():
                raise SynthesisResourceError(
                    f"Manual synthesizer resource file not found: '{path}'"
                )
            try:
                content = path.read_text(encoding="utf-8")
            except Exception as e:
                raise SynthesisResourceError(
                    f"Failed to read manual synthesizer resource file '{path}': {e}"
                ) from e
            self._parse_text(content, source_name=str(path))
        elif isinstance(source, str) and "\n" not in source and not Path(source).is_file() and "/" not in source and "\\" not in source and source.endswith(".txt"):
            path = Path(source)
            raise SynthesisResourceError(
                f"Manual synthesizer resource file not found: '{path}'"
            )
        elif isinstance(source, bytes):
            try:
                content = source.decode("utf-8")
            except Exception as e:
                raise ManualSynthesizerFormatError(
                    f"Failed to decode manual synthesizer bytes as UTF-8: {e}"
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
            raise SynthesisResourceError(
                f"Unsupported manual synthesizer source type: {type(source)}"
            )

    def _parse_text(self, text: str, source_name: str) -> None:
        """Parse manual synthesizer text following exact LanguageTool rules."""
        sep_pattern: Optional[re.Pattern[str]] = None
        lines = text.splitlines()

        for line_idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip(" \t\r\n")
            if not line:
                continue

            if line.startswith("#separatorRegExp="):
                raw_sep = line[len("#separatorRegExp=") :]
                if not raw_sep:
                    raise ManualSynthesizerFormatError(
                        f"Empty regular expression in '#separatorRegExp=' directive at Line {line_idx} in '{source_name}'"
                    )
                try:
                    sep_pattern = re.compile(raw_sep)
                except re.error as e:
                    raise ManualSynthesizerFormatError(
                        f"Invalid regular expression '{raw_sep}' in '#separatorRegExp=' directive at Line {line_idx} in '{source_name}': {e}"
                    ) from e
                continue

            if line.startswith("#"):
                continue

            if "\u00a0" in line:
                raise ManualSynthesizerFormatError(
                    f"Line {line_idx} in '{source_name}' contains a non-breaking space (\\u00A0), "
                    f"which is probably an error: {line}"
                )

            # Strip trailing inline comments and whitespace
            clean_line = line.split("#", 1)[0].strip(" \t\r\n")
            if not clean_line:
                continue

            # Split fields by separator
            if sep_pattern is None:
                parts = clean_line.split("\t")
            else:
                try:
                    parts = java_regex_split(sep_pattern, clean_line)
                except Exception as e:
                    raise ManualSynthesizerFormatError(
                        f"Error splitting line with regular expression '{sep_pattern.pattern}' at Line {line_idx} in '{source_name}': {e}"
                    ) from e

            if len(parts) != 3:
                raise ManualSynthesizerFormatError(
                    f"Invalid format at Line {line_idx} in '{source_name}': expected 3 fields, got {len(parts)} in '{line}'"
                )

            form = parts[0]
            lemma = parts[1]
            pos_tag = parts[2]

            self._mapping[(lemma, pos_tag)].append(form)
            self._possible_tags.add(pos_tag)

    def lookup(self, lemma: str, pos_tag: str) -> Optional[List[str]]:
        """Look up all synthesized forms for (lemma, pos_tag) pair."""
        forms = self._mapping.get((lemma, pos_tag))
        if forms is not None:
            return list(forms)
        return None

    def get_possible_tags(self) -> Set[str]:
        """Return all unique POS tags present in this manual dictionary."""
        return set(self._possible_tags)

    def __len__(self) -> int:
        """Number of distinct (lemma, pos_tag) pairs."""
        return len(self._mapping)

    def __contains__(self, key: Tuple[str, str]) -> bool:
        return key in self._mapping
