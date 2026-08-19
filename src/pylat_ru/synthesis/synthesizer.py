"""LanguageTool synthesis subsystem and RussianSynthesizer implementation."""

from __future__ import annotations

import re
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, List, Optional, Sequence, Set, Union

from pylat_ru.analysis import AnalyzedToken
from pylat_ru.morfologik.dictionary import MorfologikDictionary
from pylat_ru.synthesis.manual import ManualSynthesizer
from pylat_ru.synthesis.roman import get_roman_number


class Synthesizer(ABC):
    """Abstract interface for word form synthesis matching LanguageTool Synthesizer.java."""

    SPELLNUMBER_TAG = "_spell_number_"
    SPELLNUMBER_FEMININE_TAG = "_spell_number_:feminine"
    SPELLNUMBER_ROMAN_TAG = "_spell_number_:Roman"

    @abstractmethod
    def synthesize(
        self,
        token: Union[AnalyzedToken, str],
        pos_tag: str,
        pos_tag_is_regex: bool = False,
    ) -> List[str]:
        """Synthesize word form(s) from an AnalyzedToken (or lemma) and target POS tag."""
        ...

    @abstractmethod
    def synthesize_for_pos_tags(
        self, lemma: str, tag_predicate: Callable[[str], bool]
    ) -> List[str]:
        """Synthesize word form(s) for all POS tags matching the predicate."""
        ...

    @abstractmethod
    def lookup(self, lemma: str, pos_tag: str) -> List[str]:
        """Low-level lookup combining binary dictionary and manual overlays."""
        ...

    @abstractmethod
    def get_pos_tag_correction(self, pos_tag: str) -> str:
        """Language-specific POS tag correction."""
        ...

    @abstractmethod
    def get_target_pos_tag(self, pos_tags: Sequence[str], default_tag: str) -> str:
        """Resolve target POS tag from a list of tags or fallback to default."""
        ...

    @abstractmethod
    def get_spelled_number(self, num_str: str) -> str:
        """Convert number string to spelled words."""
        ...

    @abstractmethod
    def get_roman_number(self, num_str: str) -> str:
        """Convert number string to Roman numerals."""
        ...


class BaseSynthesizer(Synthesizer):
    """Base synthesizer implementation matching LanguageTool BaseSynthesizer.java."""

    def __init__(
        self,
        resource_path: Union[str, Path],
        tag_file_path: Union[str, Path],
        language_code: str = "ru",
        added_path: Optional[Union[str, Path]] = None,
        removed_path: Optional[Union[str, Path]] = None,
        do_not_synth_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self.language_code = language_code
        self.resource_path = Path(resource_path)
        self.tag_file_path = Path(tag_file_path)

        if not self.resource_path.is_file():
            raise FileNotFoundError(f"Synthesis dictionary not found: {self.resource_path}")
        self.dictionary = MorfologikDictionary.open(self.resource_path)

        self.manual_synthesizer: Optional[ManualSynthesizer] = None
        if added_path is not None and Path(added_path).is_file():
            self.manual_synthesizer = ManualSynthesizer(added_path)

        self.removal_synthesizer: Optional[ManualSynthesizer] = None
        if removed_path is not None and Path(removed_path).is_file():
            self.removal_synthesizer = ManualSynthesizer(removed_path)

        self.removal_synthesizer2: Optional[ManualSynthesizer] = None
        if do_not_synth_path is not None and Path(do_not_synth_path).is_file():
            self.removal_synthesizer2 = ManualSynthesizer(do_not_synth_path)

        self._possible_tags: Optional[List[str]] = None
        self._lock = threading.Lock()

    def _init_possible_tags(self) -> None:
        """Lazily load and cache possible POS tags from tags file and manual additions."""
        if self._possible_tags is not None:
            return
        with self._lock:
            if self._possible_tags is not None:
                return
            tags: List[str] = []
            if self.tag_file_path.is_file():
                with open(self.tag_file_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        tags.append(line)

            if self.manual_synthesizer is not None:
                tag_set = set(tags)
                for manual_tag in self.manual_synthesizer.get_possible_tags():
                    if manual_tag not in tag_set:
                        tags.append(manual_tag)
                        tag_set.add(manual_tag)

            self._possible_tags = tags

    def is_exception(self, form: str) -> bool:
        """Check if form is an exception that should be removed. Default False."""
        return False

    def remove_exceptions(self, forms: Sequence[str]) -> List[str]:
        """Filter out forms matching is_exception."""
        return [f for f in forms if not self.is_exception(f)]

    def lookup(self, lemma: str, pos_tag: str) -> List[str]:
        """Lookup word forms combining Morfologik FSA with manual additions and removals."""
        results = list(self.dictionary.synthesize(lemma, pos_tag))

        if self.manual_synthesizer is not None:
            manual_forms = self.manual_synthesizer.lookup(lemma, pos_tag)
            if manual_forms:
                results.extend(manual_forms)

        if self.removal_synthesizer is not None:
            removal_forms = self.removal_synthesizer.lookup(lemma, pos_tag)
            if removal_forms:
                rem_set = set(removal_forms)
                results = [f for f in results if f not in rem_set]

        if self.removal_synthesizer2 is not None:
            removal_forms2 = self.removal_synthesizer2.lookup(lemma, pos_tag)
            if removal_forms2:
                rem_set2 = set(removal_forms2)
                results = [f for f in results if f not in rem_set2]

        return results

    def synthesize(
        self,
        token: Union[AnalyzedToken, str],
        pos_tag: str,
        pos_tag_is_regex: bool = False,
    ) -> List[str]:
        """Synthesize word form(s) matching LanguageTool BaseSynthesizer.synthesize."""
        if isinstance(token, str):
            tok_str = token
            lemma = token
        else:
            tok_str = token.token
            lemma = token.lemma if token.lemma is not None else token.token

        if pos_tag == self.SPELLNUMBER_TAG:
            return [self.get_spelled_number(tok_str)]

        if pos_tag == self.SPELLNUMBER_FEMININE_TAG:
            return [self.get_spelled_number(f"feminine {tok_str}")]

        if pos_tag == self.SPELLNUMBER_ROMAN_TAG:
            return [self.get_roman_number(tok_str)]

        if pos_tag_is_regex:
            try:
                pattern = re.compile(pos_tag)
            except Exception as e:
                raise RuntimeError(
                    f"Error trying to synthesize POS tag {pos_tag} (posTagRegExp: true) from token {tok_str}"
                ) from e

            return self.synthesize_for_pos_tags(
                lemma, lambda t: pattern.fullmatch(t) is not None
            )

        forms = self.lookup(lemma, pos_tag)
        return self.remove_exceptions(forms)

    def synthesize_for_pos_tags(
        self, lemma: str, tag_predicate: Callable[[str], bool]
    ) -> List[str]:
        """Synthesize word forms for all possible POS tags matching predicate."""
        self._init_possible_tags()
        results: List[str] = []
        if self._possible_tags is not None:
            for tag in self._possible_tags:
                if tag_predicate(tag):
                    forms = self.lookup(lemma, tag)
                    results.extend(forms)
        return self.remove_exceptions(results)

    def get_pos_tag_correction(self, pos_tag: str) -> str:
        return pos_tag

    def get_target_pos_tag(self, pos_tags: Sequence[str], default_tag: str) -> str:
        if not pos_tags:
            return default_tag
        return pos_tags[-1]

    def get_spelled_number(self, num_str: str) -> str:
        return num_str

    def get_roman_number(self, num_str: str) -> str:
        return get_roman_number(num_str)


def _resolve_resource(filename: str) -> Path:
    """Resolve resource path from package resources or third_party directory."""
    pkg_path = Path(__file__).resolve().parent.parent / "resources" / "ru" / filename
    if pkg_path.is_file():
        return pkg_path

    third_party_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "third_party"
        / "languagetool"
        / "languagetool-language-modules"
        / "ru"
        / "src"
        / "main"
        / "resources"
        / "org"
        / "languagetool"
        / "resource"
        / "ru"
        / filename
    )
    if third_party_path.is_file():
        return third_party_path

    return pkg_path


class RussianSynthesizer(BaseSynthesizer):
    """Russian word form synthesizer matching org.languagetool.synthesis.ru.RussianSynthesizer."""

    _instance: Optional[RussianSynthesizer] = None
    _instance_lock = threading.Lock()

    def __init__(
        self,
        resource_path: Optional[Union[str, Path]] = None,
        tag_file_path: Optional[Union[str, Path]] = None,
        added_path: Optional[Union[str, Path]] = None,
        removed_path: Optional[Union[str, Path]] = None,
    ) -> None:
        dict_p = resource_path if resource_path is not None else _resolve_resource("russian_synth.dict")
        tags_p = tag_file_path if tag_file_path is not None else _resolve_resource("tags_russian.txt")
        add_p = added_path if added_path is not None else _resolve_resource("added.txt")
        rem_p = removed_path if removed_path is not None else _resolve_resource("removed.txt")

        super().__init__(
            resource_path=dict_p,
            tag_file_path=tags_p,
            language_code="ru",
            added_path=add_p,
            removed_path=rem_p,
        )

    @classmethod
    def get_instance(cls) -> RussianSynthesizer:
        """Return singleton instance of RussianSynthesizer matching RussianSynthesizer.INSTANCE."""
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance


# Canonical singleton alias matching Java LT RussianSynthesizer.INSTANCE
RussianSynthesizer.INSTANCE = RussianSynthesizer.get_instance  # type: ignore[attr-defined]
