"""Multi-word expression tagger-chunker matching LanguageTool MultiWordChunker."""

from __future__ import annotations

import importlib.resources
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.disambiguation.errors import DisambiguationFormatError, DisambiguationResourceError


MAX_TOKENS_IN_MULTIWORD = 20
DEFAULT_SEPARATOR = "\t"


def _resolve_resource_path(resource_name: str) -> Path:
    """Resolve a multiwords resource path from package resources or fallback cleanly without broad catch-all."""
    p_str = resource_name.lstrip("/\\")
    res_name = p_str[3:] if p_str.startswith("ru/") else p_str

    try:
        res = importlib.resources.files("pylat_ru.resources.ru").joinpath(res_name)
        p = Path(str(res))
        if p.is_file():
            return p
    except (TypeError, ModuleNotFoundError, AttributeError):
        pass

    candidates = [
        Path(__file__).resolve().parent.parent / "resources" / "ru" / res_name,
        Path("src/pylat_ru/resources/ru") / res_name,
        Path("third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru") / res_name,
    ]
    for c in candidates:
        if c.is_file():
            return c

    raise DisambiguationResourceError(f"Multiwords resource '{resource_name}' not found.")


class MultiWordChunker:
    """Multiword tagger-chunker that identifies multi-token expressions.

    Port of LanguageTool org.languagetool.tagging.disambiguation.MultiWordChunker.
    Annotates expressions with '<TAG>' on start token and '</TAG>' on end token.
    """

    _cache: Dict[str, MultiWordChunker] = {}

    def __init__(
        self,
        resource_path: Optional[Union[str, Path]] = None,
        allow_first_capitalized: bool = False,
        allow_all_uppercase: bool = False,
        allow_titlecase: bool = False,
        default_tag: Optional[str] = None,
        is_remove_previous_tags: bool = False,
        add_ignore_spelling: bool = False,
    ) -> None:
        self.resource_path = resource_path or "ru/multiwords.txt"
        self.allow_first_capitalized = allow_first_capitalized
        self.allow_all_uppercase = allow_all_uppercase
        self.allow_titlecase = allow_titlecase
        self.default_tag = default_tag
        self.is_remove_previous_tags = is_remove_previous_tags
        self.add_ignore_spelling = add_ignore_spelling

        self._initialized = False
        self._m_start_space: Dict[str, int] = {}
        self._m_start_no_space: Dict[str, int] = {}
        self._m_full_space: Dict[str, AnalyzedToken] = {}
        self._m_full_no_space: Dict[str, AnalyzedToken] = {}

    @classmethod
    def get_instance(
        cls,
        resource_path: Optional[Union[str, Path]] = None,
        allow_first_capitalized: bool = False,
        allow_all_uppercase: bool = False,
        allow_titlecase: bool = False,
        default_tag: Optional[str] = None,
    ) -> MultiWordChunker:
        """Get or create a cached MultiWordChunker instance."""
        key = (
            str(resource_path or "ru/multiwords.txt"),
            allow_first_capitalized,
            allow_all_uppercase,
            allow_titlecase,
            default_tag,
        )
        cache_key = repr(key)
        if cache_key not in cls._cache:
            cls._cache[cache_key] = cls(
                resource_path=resource_path,
                allow_first_capitalized=allow_first_capitalized,
                allow_all_uppercase=allow_all_uppercase,
                allow_titlecase=allow_titlecase,
                default_tag=default_tag,
            )
        return cls._cache[cache_key]

    def _ensure_initialized(self) -> None:
        """Load and index multiword resources on first use."""
        if self._initialized:
            return

        lines = self._load_lines()
        separator = DEFAULT_SEPARATOR

        for line_idx, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            if line.startswith("#separatorRegExp="):
                separator = line.replace("#separatorRegExp=", "", 1)
                try:
                    re.compile(separator)
                except re.error as e:
                    raise DisambiguationFormatError(
                        f"Invalid #separatorRegExp on line {line_idx}: '{separator}': {e}"
                    ) from e
                continue
            if not line or line.startswith("#"):
                continue

            # Strip trailing inline comments
            if "#" in line:
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue

            parts = line.split(separator) if separator == "\t" else re.split(separator, line)
            if self.default_tag is None and len(parts) != 2:
                raise DisambiguationFormatError(
                    f"Invalid format in multiwords line {line_idx}: '{line}', expected phrase<TAB>tag"
                )
            if self.default_tag is not None and len(parts) != 1:
                raise DisambiguationFormatError(
                    f"Invalid format in multiwords line {line_idx}: '{line}', expected phrase"
                )

            original_string = parts[0].strip()
            tag = (self.default_tag if self.default_tag is not None else parts[1]).strip()

            if not original_string or not tag:
                raise DisambiguationFormatError(
                    f"Empty phrase or tag in multiwords line {line_idx}: '{line}'"
                )

            casing_variants = [original_string]
            contains_space = " " in original_string

            if self.allow_all_uppercase:
                upper = original_string.upper()
                if upper not in casing_variants:
                    casing_variants.append(upper)
            if self.allow_first_capitalized and len(original_string) > 0:
                first_cap = original_string[0].upper() + original_string[1:]
                if first_cap not in casing_variants:
                    casing_variants.append(first_cap)

            for casing_variant in casing_variants:
                if not contains_space:
                    first_char = casing_variant[:1]
                    self._m_start_no_space[first_char] = max(
                        self._m_start_no_space.get(first_char, 0), len(casing_variant)
                    )
                    self._m_full_no_space[casing_variant] = AnalyzedToken(
                        token=casing_variant, pos_tag=tag, lemma=original_string
                    )
                else:
                    tokens = casing_variant.split(" ")
                    first_token = tokens[0]
                    self._m_start_space[first_token] = max(
                        self._m_start_space.get(first_token, 0), len(tokens)
                    )
                    self._m_full_space[casing_variant] = AnalyzedToken(
                        token=casing_variant, pos_tag=tag, lemma=original_string
                    )

        self._initialized = True

    def _load_lines(self) -> List[str]:
        """Read multiword resource text lines with fail-closed resolution."""
        if isinstance(self.resource_path, Path) and self.resource_path.is_file():
            return self.resource_path.read_text(encoding="utf-8").splitlines()

        p = _resolve_resource_path(str(self.resource_path))
        return p.read_text(encoding="utf-8").splitlines()

    def disambiguate(self, input_sentence: AnalyzedSentence) -> AnalyzedSentence:
        """Run multiword chunking across the sentence."""
        self._ensure_initialized()

        an_tokens = [AnalyzedTokenReadings(t) for t in input_sentence.get_tokens()]
        n = len(an_tokens)

        for i in range(n):
            tok = an_tokens[i].token
            if len(tok) < 1:
                continue

            tok_builder = [tok]
            k = i + 1
            while k < n and not an_tokens[k].is_whitespace():
                tok_builder.append(an_tokens[k].token)
                k += 1
            tok_concat = "".join(tok_builder)

            # 1. Space-separated multiwords check
            target_first_tok = tok if tok in self._m_start_space else (tok_concat if tok_concat in self._m_start_space else None)
            if target_first_tok is not None:
                max_len = self._m_start_space[target_first_tok]
                key_builder: List[str] = []
                j = i
                len_counter = 0
                final_len = 0
                matched_at: Optional[AnalyzedToken] = None

                while j < n and (j - i) < MAX_TOKENS_IN_MULTIWORD:
                    if not an_tokens[j].is_whitespace():
                        key_builder.append(an_tokens[j].token)
                        key_str = "".join(key_builder)
                        if key_str in self._m_full_space:
                            matched_at = self._m_full_space[key_str]
                            final_len = j
                    else:
                        if j > 0 and not an_tokens[j - 1].is_whitespace():
                            key_builder.append(" ")
                            len_counter += 1
                        if len_counter == max_len:
                            break
                    j += 1

                if matched_at is not None:
                    tag = matched_at.pos_tag or ""
                    lemma = matched_at.lemma
                    if final_len == i:
                        an_tokens[i].add_reading(
                            AnalyzedToken(token=an_tokens[i].token, pos_tag=tag, lemma=lemma),
                            "MULTIWORD_CHUNKER",
                        )
                    else:
                        an_tokens[i].add_reading(
                            AnalyzedToken(token=an_tokens[i].token, pos_tag=f"<{tag}>", lemma=lemma),
                            "MULTIWORD_CHUNKER",
                        )
                        an_tokens[final_len].add_reading(
                            AnalyzedToken(token=an_tokens[final_len].token, pos_tag=f"</{tag}>", lemma=lemma),
                            "MULTIWORD_CHUNKER",
                        )
                    if self.add_ignore_spelling:
                        for m in range(i, final_len + 1):
                            an_tokens[m].ignore_spelling()

            # 2. No-space multiwords check
            if tok[:1] in self._m_start_no_space:
                j = i
                key_builder_nospace: List[str] = []
                while j < n and not an_tokens[j].is_whitespace() and (j - i) < MAX_TOKENS_IN_MULTIWORD:
                    key_builder_nospace.append(an_tokens[j].token)
                    key_str = "".join(key_builder_nospace)
                    if key_str in self._m_full_no_space:
                        at = self._m_full_no_space[key_str]
                        tag = at.pos_tag or ""
                        lemma = at.lemma
                        if i == j:
                            an_tokens[i].add_reading(
                                AnalyzedToken(token=an_tokens[i].token, pos_tag=tag, lemma=lemma),
                                "MULTIWORD_CHUNKER",
                            )
                        else:
                            an_tokens[i].add_reading(
                                AnalyzedToken(token=an_tokens[i].token, pos_tag=f"<{tag}>", lemma=lemma),
                                "MULTIWORD_CHUNKER",
                            )
                            an_tokens[j].add_reading(
                                AnalyzedToken(token=an_tokens[j].token, pos_tag=f"</{tag}>", lemma=lemma),
                                "MULTIWORD_CHUNKER",
                            )
                        if self.add_ignore_spelling:
                            for m in range(i, j + 1):
                                an_tokens[m].ignore_spelling()
                    j += 1

        return AnalyzedSentence(tokens=an_tokens, pre_disambig_tokens=input_sentence.get_tokens())
