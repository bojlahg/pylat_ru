"""Manual synthesizer overlay parser for LanguageTool synthesis matching ManualSynthesizer.java."""

from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union


class ManualSynthesizer:
    """Parses and queries manual synthesis mappings (e.g. added.txt, removed.txt).

    Format: three separated fields: <form> <lemma> <postag>
    Supports `#separatorRegExp=` line directives, `#` comments, and suffix decoding (`+`, `++`).
    """

    def __init__(self, source: Union[str, Path, io.IOBase]) -> None:
        self._mapping: Dict[Tuple[str, str], List[str]] = {}
        self._possible_tags: Set[str] = set()

        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.is_file():
                raise FileNotFoundError(f"Manual synthesis file not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                self._load(f)
        else:
            self._load(source)

    def _load(self, stream: io.IOBase) -> None:
        sep_regex = r"\t"
        for raw_line in stream:
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8")
            else:
                line = str(raw_line)

            line = line.strip()
            if line.startswith("#separatorRegExp="):
                sep_regex = line[len("#separatorRegExp=") :]
                continue

            if not line or line.startswith("#"):
                continue

            # Strip inline comment
            if "#" in line:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue

            parts = re.split(sep_regex, line)
            if len(parts) != 3:
                raise ValueError(
                    f"Expected 3 tab/regex-separated columns (form, lemma, postag), got {len(parts)} in line: {line!r}"
                )

            raw_form = parts[0].strip()
            lemma = parts[1].strip()
            pos_tag = parts[2].strip()

            decoded_form = self._decode_form(lemma, raw_form)
            key = (lemma, pos_tag)
            if key not in self._mapping:
                self._mapping[key] = []
            self._mapping[key].append(decoded_form)
            self._possible_tags.add(pos_tag)

    @staticmethod
    def _decode_form(lemma: str, form: str) -> str:
        """Decode suffix encoding (+, ++) into full inflected word form."""
        if form.startswith("++"):
            # Strip 1 char from lemma, append rest of form
            return lemma[:-1] + form[2:]
        if form.startswith("+"):
            # Append rest of form to full lemma
            return lemma + form[1:]
        return form

    def lookup(self, lemma: str, pos_tag: str) -> Optional[List[str]]:
        """Look up synthesized word forms for (lemma, pos_tag)."""
        forms = self._mapping.get((lemma, pos_tag))
        if forms is None:
            return None
        return list(forms)

    def get_possible_tags(self) -> Set[str]:
        """Return all unique POS tags encountered in this manual synthesizer."""
        return set(self._possible_tags)

    def __len__(self) -> int:
        return sum(len(forms) for forms in self._mapping.values())
