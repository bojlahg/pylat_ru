"""src/pylat_ru/morfologik/speller.py

Native Python port of ``morfologik.speller.Speller`` (morfologik-stemming 2.1.9),
the spelling engine used by LanguageTool 6.8 through ``MorfologikSpeller``.

The port implements K. Oflazer's error-tolerant finite-state recognition, which
is what upstream uses to produce spelling verdicts and ranked suggestions.  It
deliberately mirrors the pinned Java control flow -- including its cut-off edit
distance band, replacement-pair machinery, run-on word search, and frequency
weighting -- so that observable suggestion text and ordering match.

Development note: the pinned Java sources this file is derived from are recorded
in ``third_party/languagetool/UPSTREAM.json`` and
``third_party/morfologik/UPSTREAM.json``.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pylat_ru.morfologik.dictionary import MorfologikDictionary
from pylat_ru.morfologik.errors import UnsupportedEncodingError
from pylat_ru.morfologik.fsa import (
    EXACT_MATCH,
    FSA,
    SEQUENCE_IS_A_PREFIX,
    ByteSequenceIterator,
)
from pylat_ru.morfologik.metadata import DictionaryMetadata

# morfologik.speller.Speller constants
MAX_WORD_LENGTH = 120
FREQ_RANGES = ord("Z") - ord("A") + 1
FIRST_RANGE_CODE = ord("A")
UPPER_SEARCH_LIMIT = 15
MIN_WORD_LENGTH = 4
MAX_RECURSION_LEVEL = 6

_LETTER_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo"})
_ALPHABETIC_CATEGORIES = frozenset({"Lu", "Ll", "Lt", "Lm", "Lo", "Nl"})


def is_letter(ch: str) -> bool:
    """Equivalent of ``Character.isLetter``."""
    return unicodedata.category(ch) in _LETTER_CATEGORIES


def is_lower_case(ch: str) -> bool:
    """Equivalent of ``Character.isLowerCase``."""
    return unicodedata.category(ch) == "Ll"


def is_upper_case(ch: str) -> bool:
    """Equivalent of ``Character.isUpperCase``."""
    return unicodedata.category(ch) == "Lu"


def is_digit(ch: str) -> bool:
    """Equivalent of ``Character.isDigit``."""
    return unicodedata.category(ch) == "Nd"


def is_alphabetic(ch: str) -> bool:
    """Equivalent of ``morfologik.speller.Speller.isAlphabetic``."""
    return unicodedata.category(ch) in _ALPHABETIC_CATEGORIES


def char_to_upper(ch: str) -> str:
    """Equivalent of ``Character.toUpperCase(char)`` (single-char mapping only)."""
    upper = ch.upper()
    return upper if len(upper) == 1 else ch


def char_to_lower(ch: str) -> str:
    """Equivalent of ``Character.toLowerCase(char)`` (single-char mapping only)."""
    lower = ch.lower()
    return lower if len(lower) == 1 else ch


def apply_replacements(word: str, replacements: Dict[str, str]) -> str:
    """Port of ``DictionaryLookup.applyReplacements``."""
    if not replacements:
        return word
    builder = word
    for key, value in replacements.items():
        index = builder.find(key)
        while index != -1:
            builder = builder[:index] + value + builder[index + len(key):]
            index = builder.find(key, index + len(value))
    return builder


class TrieFSA(FSA):
    """Minimal FSA over a set of byte sequences, used for runtime plain-text dictionaries.

    LanguageTool builds an in-memory Morfologik FSA from ``spelling.txt`` at
    runtime (``MorfologikMultiSpeller.getDictionary``).  A deterministic trie with
    arcs kept in ascending unsigned-label order exposes the same traversal order
    as the serialized automaton built from lexically sorted input, which is what
    the speller search and candidate ordering depend on.
    """

    def __init__(self, sequences: Iterable[bytes]) -> None:
        # node 0 is reserved for "no node" exactly as in the binary formats
        self._labels: List[List[int]] = [[]]     # per node: arc labels
        self._targets: List[List[int]] = [[]]    # per node: destination node or 0
        self._final: List[List[bool]] = [[]]     # per node: arc is final
        self._children: List[Dict[int, int]] = [{}]
        self._root = self._new_node()
        for seq in sequences:
            self._add(seq)
        self._sort_arcs()

    def _new_node(self) -> int:
        self._labels.append([])
        self._targets.append([])
        self._final.append([])
        self._children.append({})
        return len(self._labels) - 1

    def _add(self, seq: bytes) -> None:
        if not seq:
            return
        node = self._root
        for i, label in enumerate(seq):
            last = i == len(seq) - 1
            child = self._children[node].get(label)
            if child is None:
                child = self._new_node()
                self._children[node][label] = child
                self._labels[node].append(label)
                self._targets[node].append(child)
                self._final[node].append(last)
            elif last:
                self._final[node][self._labels[node].index(label)] = True
            node = child

    def _sort_arcs(self) -> None:
        for node in range(len(self._labels)):
            if len(self._labels[node]) < 2:
                continue
            order = sorted(range(len(self._labels[node])), key=lambda i: self._labels[node][i])
            self._labels[node] = [self._labels[node][i] for i in order]
            self._targets[node] = [self._targets[node][i] for i in order]
            self._final[node] = [self._final[node][i] for i in order]
        # Terminal nodes (no outgoing arcs) are represented as target 0.
        for node in range(len(self._targets)):
            for i, target in enumerate(self._targets[node]):
                if target != 0 and not self._labels[target]:
                    self._targets[node][i] = 0

    # Arcs are encoded as (node << 16) | arc_index + 1 so that 0 means "no arc".
    @staticmethod
    def _arc(node: int, index: int) -> int:
        return (node << 16) | (index + 1)

    @staticmethod
    def _split(arc: int) -> Tuple[int, int]:
        return arc >> 16, (arc & 0xFFFF) - 1

    def get_root_node(self) -> int:
        return self._root

    def get_first_arc(self, node: int) -> int:
        if node == 0 or not self._labels[node]:
            return 0
        return self._arc(node, 0)

    def get_next_arc(self, arc: int) -> int:
        node, index = self._split(arc)
        if index + 1 >= len(self._labels[node]):
            return 0
        return self._arc(node, index + 1)

    def get_arc(self, node: int, label: int) -> int:
        if node == 0:
            return 0
        labels = self._labels[node]
        for i, value in enumerate(labels):
            if value == label:
                return self._arc(node, i)
        return 0

    def get_arc_label(self, arc: int) -> int:
        node, index = self._split(arc)
        return self._labels[node][index]

    def is_arc_final(self, arc: int) -> bool:
        node, index = self._split(arc)
        return self._final[node][index]

    def is_arc_terminal(self, arc: int) -> bool:
        node, index = self._split(arc)
        return self._targets[node][index] == 0

    def get_end_node(self, arc: int) -> int:
        node, index = self._split(arc)
        return self._targets[node][index]

    def get_sequences(self, node: Optional[int] = None) -> Iterable[bytes]:
        return ByteSequenceIterator(self, node)

    def match(self, sequence: bytes, start_node: Optional[int] = None) -> Tuple[int, int, int]:
        from pylat_ru.morfologik.fsa import AUTOMATON_HAS_PREFIX, NO_MATCH

        node = self._root if start_node is None else start_node
        if node == 0:
            return NO_MATCH, 0, node
        for i, byte in enumerate(sequence):
            arc = self.get_arc(node, byte)
            if arc != 0:
                if i + 1 == len(sequence) and self.is_arc_final(arc):
                    return EXACT_MATCH, i + 1, node
                if self.is_arc_terminal(arc):
                    return AUTOMATON_HAS_PREFIX, i + 1, node
                node = self.get_end_node(arc)
            else:
                if i > 0:
                    return AUTOMATON_HAS_PREFIX, i, node
                return NO_MATCH, 0, node
        return SEQUENCE_IS_A_PREFIX, len(sequence), node


class HMatrix:
    """Port of ``morfologik.speller.HMatrix``."""

    __slots__ = ("p", "row_length", "column_height", "edit_distance")

    def __init__(self, distance: int, max_length: int) -> None:
        self.row_length = max_length + 2
        self.column_height = 2 * distance + 3
        self.edit_distance = distance
        size = self.row_length * self.column_height
        self.p = [0] * size
        for i in range(self.row_length - distance - 1):
            self.p[i] = distance + 1
            self.p[size - i - 1] = distance + 1
        for j in range(2 * distance + 1):
            self.p[j * self.row_length] = distance + 1 - j
            self.p[min(size - 1, (j + distance + 1) * self.row_length + j)] = j

    def get(self, i: int, j: int) -> int:
        return self.p[(j - i + self.edit_distance + 1) * self.row_length + j]

    def set(self, i: int, j: int, value: int) -> None:
        self.p[(j - i + self.edit_distance + 1) * self.row_length + j] = value


@dataclass(frozen=True)
class CandidateData:
    """Port of ``Speller.CandidateData``: distance folds in the frequency range."""

    word: str
    orig_distance: int
    distance: int

    def get_word(self) -> str:
        return self.word

    def get_distance(self) -> int:
        return self.distance


class Speller:
    """Port of ``morfologik.speller.Speller`` for single-byte dictionary charsets."""

    def __init__(self, dictionary: MorfologikDictionary, edit_distance: int = 1) -> None:
        self.dictionary = dictionary
        self.fsa: FSA = dictionary.fsa
        self.metadata: DictionaryMetadata = dictionary.metadata
        self.edit_distance = edit_distance
        self.h_matrix = HMatrix(edit_distance, MAX_WORD_LENGTH)
        self.root_node = self.fsa.get_root_node()
        if self.root_node == 0:
            raise ValueError("Dictionary must have at least the root node.")
        self.encoding = self.metadata.encoding
        self._byte_to_char = self._build_byte_table(self.encoding)
        self.separator_byte = self.metadata.separator_byte
        self.separator_char = self.metadata.separator
        self.contains_separators = True
        self._effect_edit_distance = 0
        self._word_processed: str = ""
        self._word_len = 0
        self._candidate: List[str] = []
        self._replacements_any_to_one: Dict[str, List[str]] = {}
        self._replacements_any_to_two: Dict[str, List[str]] = {}
        self._replacements_the_rest: Dict[str, List[str]] = {}
        self._create_replacements_maps()
        self._frequency_cache: Dict[str, int] = {}
        self._in_dictionary_cache: Dict[str, bool] = {}
        # Decoding CFSA2 arcs is the hot path of findRepl.  The automaton is
        # immutable and LanguageTool builds a fresh Speller per suggestion
        # request, so the decoded arc table is cached on the shared dictionary.
        # `contains_separators` is the only speller state it depends on.
        self._arc_cache_store = getattr(dictionary, "_speller_arc_cache", None)
        if self._arc_cache_store is None:
            self._arc_cache_store = {True: {}, False: {}}
            setattr(dictionary, "_speller_arc_cache", self._arc_cache_store)
        # Equality reduces to identity unless the dictionary declares equivalent
        # characters or diacritics folding (the Russian dictionaries declare neither).
        self._simple_equality = not self.metadata.equivalent_chars and not self.metadata.ignore_diacritics

    # ------------------------------------------------------------------ setup

    @staticmethod
    def _build_byte_table(encoding: str) -> List[Optional[str]]:
        """Decode every byte value once.

        The pinned Russian speller dictionaries use ``koi8-r``.  A multi-byte or
        partially mapped charset would need the incremental decoder branch of
        ``findRepl`` (malformed-sequence backtracking); rather than silently
        approximate it, such a dictionary is refused.
        """
        try:
            decoded = bytes(range(256)).decode(encoding)
        except (UnicodeDecodeError, LookupError) as exc:
            raise UnsupportedEncodingError(
                f"Speller requires a complete single-byte dictionary encoding, got {encoding!r}"
            ) from exc
        if len(decoded) != 256:
            raise UnsupportedEncodingError(
                f"Speller requires a complete single-byte dictionary encoding, got {encoding!r}"
            )
        return list(decoded)

    def _create_replacements_maps(self) -> None:
        for key, values in self.metadata.replacement_pairs.items():
            for value in values:
                if len(value) == 1:
                    self._replacements_any_to_one.setdefault(value, []).append(key)
                elif len(value) == 2:
                    self._replacements_any_to_two.setdefault(value, []).append(key)
                else:
                    self._replacements_the_rest.setdefault(key, []).append(value)

    # ------------------------------------------------------------- dictionary

    def _locale_lower(self, text: str) -> str:
        return text.lower()

    def _locale_upper(self, text: str) -> str:
        return text.upper()

    def _encode(self, word: str) -> Optional[bytes]:
        try:
            return word.encode(self.encoding)
        except (UnicodeEncodeError, LookupError):
            return None

    def is_in_dictionary(self, word: str) -> bool:
        cached = self._in_dictionary_cache.get(word)
        if cached is not None:
            return cached
        result = self._is_in_dictionary_uncached(word)
        if len(self._in_dictionary_cache) < 200000:
            self._in_dictionary_cache[word] = result
        return result

    def _is_in_dictionary_uncached(self, word: str) -> bool:
        word_bytes = self._encode(word)
        if word_bytes is None:
            return False
        kind, _, node = self.fsa.match(word_bytes, self.root_node)
        if self.contains_separators and kind == EXACT_MATCH:
            self.contains_separators = self.separator_char in word
            self._in_dictionary_cache.clear()
        if kind == EXACT_MATCH and not self.contains_separators:
            return True
        return (
            self.contains_separators
            and kind == SEQUENCE_IS_A_PREFIX
            and len(word_bytes) > 0
            and self.fsa.get_arc(node, self.separator_byte) != 0
        )

    def is_misspelled(self, word: str) -> bool:
        word_to_check = word
        if self.metadata.input_conversion:
            word_to_check = apply_replacements(word, self.metadata.input_conversion)
        if not word_to_check:
            return False
        alphabetic = len(word_to_check) != 1 or is_alphabetic(word_to_check[0])
        if self.metadata.ignore_punctuation and not alphabetic:
            return False
        if self.metadata.ignore_numbers and not contains_no_digit(word_to_check):
            return False
        if self.metadata.ignore_camel_case and self.is_camel_case(word_to_check):
            return False
        if self.metadata.ignore_all_uppercase and alphabetic and self.is_all_uppercase(word_to_check):
            return False
        if self.is_in_dictionary(word_to_check):
            return False
        if self.metadata.convert_case:
            if not self.is_mixed_case(word_to_check):
                if self.is_in_dictionary(self._locale_lower(word_to_check)):
                    return False
                if self.is_all_uppercase(word_to_check) and self.is_in_dictionary(
                    self._initial_uppercase(word_to_check)
                ):
                    return False
        return True

    def _initial_uppercase(self, word: str) -> str:
        return word[:1] + self._locale_lower(word[1:])

    def get_frequency(self, word: str) -> int:
        cached = self._frequency_cache.get(word)
        if cached is not None:
            return cached
        value = self._get_frequency_uncached(word)
        if len(self._frequency_cache) < 200000:
            self._frequency_cache[word] = value
        return value

    def _get_frequency_uncached(self, word: str) -> int:
        if not self.metadata.frequency_included:
            return 0
        word_bytes = self._encode(word)
        if word_bytes is None:
            return 0
        kind, _, node = self.fsa.match(word_bytes, self.root_node)
        if kind == SEQUENCE_IS_A_PREFIX:
            arc = self.fsa.get_arc(node, self.separator_byte)
            if arc != 0 and not self.fsa.is_arc_final(arc):
                for sequence in self.fsa.get_sequences(self.fsa.get_end_node(arc)):
                    return sequence[-1] - FIRST_RANGE_CODE
        return 0

    def converts_case(self) -> bool:
        return self.metadata.convert_case

    # ------------------------------------------------------------ run-on words

    def replace_run_on_word_candidates(self, original: str) -> List[CandidateData]:
        candidates: List[CandidateData] = []
        word_to_check = original
        if self.metadata.input_conversion:
            word_to_check = apply_replacements(original, self.metadata.input_conversion)
        if not self.is_in_dictionary(word_to_check) and self.metadata.support_run_on_words:
            for i in range(1, len(word_to_check)):
                prefix = word_to_check[:i]
                suffix = word_to_check[i:]
                if self.is_in_dictionary(suffix) or (
                    not self.is_not_capitalized_word(suffix)
                    and self.is_in_dictionary(self._locale_lower(suffix))
                ):
                    if self.is_in_dictionary(prefix):
                        self._add_replacement(candidates, prefix + " " + suffix)
                    elif is_upper_case(prefix[0]) and self.is_in_dictionary(self._locale_lower(prefix)):
                        self._add_replacement(candidates, prefix + " " + suffix)
        return candidates

    def replace_run_on_words(self, original: str) -> List[str]:
        return [candidate.word for candidate in self.replace_run_on_word_candidates(original)]

    def _add_replacement(self, candidates: List[CandidateData], replacement: str) -> None:
        if not self.metadata.output_conversion:
            candidates.append(self._candidate_data(replacement, 1))
        else:
            candidates.append(
                self._candidate_data(
                    apply_replacements(replacement, self.metadata.output_conversion), 1
                )
            )

    def _candidate_data(self, word: str, distance: int) -> CandidateData:
        weighted = distance * FREQ_RANGES + FREQ_RANGES - self.get_frequency(word) - 1
        return CandidateData(word=word, orig_distance=distance, distance=weighted)

    # --------------------------------------------------------- replacement set

    def get_all_replacements(self, text: str, from_index: int, level: int) -> List[str]:
        replaced: List[str] = []
        if level > MAX_RECURSION_LEVEL:
            replaced.append(text)
            return replaced
        builder = text
        index = MAX_WORD_LENGTH
        key = ""
        key_length = 0
        found = False
        for aux_key in self._replacements_the_rest:
            aux_index = builder.find(aux_key, from_index)
            if aux_index > -1 and (aux_index < index or (aux_index == index and not len(aux_key) < key_length)):
                index = aux_index
                key = aux_key
                key_length = len(aux_key)
        if index < MAX_WORD_LENGTH:
            for rep in self._replacements_the_rest[key]:
                if not found:
                    replaced.extend(self.get_all_replacements(text, index + len(key), level + 1))
                    found = True
                ind = builder.find(rep, max(0, from_index - len(rep) + 1))
                if len(rep) > len(key) and ind > -1 and (ind == index or ind == index - len(rep) + 1):
                    continue
                mutated = builder[:index] + rep + builder[index + len(key):]
                replaced.extend(self.get_all_replacements(mutated, index + len(rep), level + 1))
        if not found:
            replaced.append(builder)
        return replaced

    # --------------------------------------------------------------- candidates

    def find_similar_word_candidates(self, word: str) -> List[CandidateData]:
        return self._find_replacement_candidates(word, True)

    def find_similar_words(self, word: str) -> List[str]:
        return [candidate.word for candidate in self.find_similar_word_candidates(word)]

    def find_replacement_candidates(self, word: str) -> List[CandidateData]:
        return self._find_replacement_candidates(word, False)

    def find_replacements(self, word: str) -> List[str]:
        return [candidate.word for candidate in self.find_replacement_candidates(word)]

    def _find_replacement_candidates(self, word: str, even_if_in_dictionary: bool) -> List[CandidateData]:
        if self.metadata.input_conversion:
            word = apply_replacements(word, self.metadata.input_conversion)

        candidates: List[CandidateData] = []
        if 0 < len(word) < MAX_WORD_LENGTH and (
            not self.is_in_dictionary(word) or even_if_in_dictionary
        ):
            words_to_check: List[str] = []
            if self._replacements_the_rest is not None and len(word) > 1:
                for word_checked in self.get_all_replacements(word, 0, 0):
                    if self.is_in_dictionary(word_checked):
                        candidates.append(self._candidate_data(word_checked, 0))
                    else:
                        lower_word = self._locale_lower(word_checked)
                        upper_word = self._locale_upper(word_checked)
                        if self.is_in_dictionary(lower_word):
                            candidates.append(self._candidate_data(lower_word, 0))
                        if self.is_in_dictionary(upper_word):
                            candidates.append(self._candidate_data(upper_word, 0))
                        if len(lower_word) > 1:
                            first_upper = char_to_upper(lower_word[0]) + lower_word[1:]
                            if self.is_in_dictionary(first_upper):
                                candidates.append(self._candidate_data(first_upper, 0))
                    words_to_check.append(word_checked)
            else:
                words_to_check.append(word)

            i = 1
            for word_checked in words_to_check:
                i += 1
                if i > UPPER_SEARCH_LIMIT:
                    break
                self._word_processed = word_checked
                self._word_len = len(word_checked)
                if self._word_len < MIN_WORD_LENGTH and i > 2:
                    break
                self._candidate = [""] * MAX_WORD_LENGTH
                self._effect_edit_distance = (
                    self._word_len - 1 if self._word_len <= self.edit_distance else self.edit_distance
                )
                # NOTE: upstream deliberately does not reset the H matrix between
                # words to check; LanguageTool compensates by building a fresh
                # Speller for every suggestion request (MorfologikSpeller#getSuggestions).
                self._find_repl(candidates, 0, self.fsa.get_root_node(), 0, 0)

        candidates.sort(key=lambda candidate: candidate.distance)

        seen = set()
        result: List[CandidateData] = []
        for candidate in candidates:
            replaced = apply_replacements(candidate.word, self.metadata.output_conversion)
            if replaced not in seen and replaced != word:
                seen.add(replaced)
                result.append(
                    CandidateData(
                        word=replaced,
                        orig_distance=candidate.orig_distance,
                        distance=candidate.distance,
                    )
                )
            seen.add(replaced)
        return result

    def _arcs_of(self, node: int) -> Tuple[Tuple[Optional[str], bool, bool, int, bool], ...]:
        """Decoded outgoing arcs of ``node`` as (char, final, terminal, end node, before separator)."""
        table_cache = self._arc_cache_store[self.contains_separators]
        cached = table_cache.get(node)
        if cached is not None:
            return cached
        fsa = self.fsa
        table = self._byte_to_char
        entries: List[Tuple[Optional[str], bool, bool, int, bool]] = []
        arc = fsa.get_first_arc(node)
        while arc != 0:
            terminal = fsa.is_arc_terminal(arc)
            end_node = 0 if terminal else fsa.get_end_node(arc)
            before_separator = False
            if self.contains_separators and not terminal:
                sep_arc = fsa.get_arc(end_node, self.separator_byte)
                before_separator = sep_arc != 0 and not fsa.is_arc_terminal(sep_arc)
            entries.append(
                (
                    table[fsa.get_arc_label(arc)],
                    fsa.is_arc_final(arc),
                    terminal,
                    end_node,
                    before_separator,
                )
            )
            arc = fsa.get_next_arc(arc)
        result = tuple(entries)
        table_cache[node] = result
        return result

    def _find_repl(
        self,
        candidates: List[CandidateData],
        depth: int,
        node: int,
        word_index: int,
        cand_index: int,
    ) -> None:
        candidate = self._candidate
        if cand_index >= MAX_WORD_LENGTH:
            return
        eed = self._effect_edit_distance
        word_len = self._word_len
        h_matrix = self.h_matrix
        contains_separators = self.contains_separators
        separator_char = self.separator_char
        length_at_end = abs(word_len - 1 - word_index) <= eed
        for decoded, is_final, is_terminal, end_node, before_separator in self._arcs_of(node):
            if decoded is None:
                # unmappable characters are silently discarded
                continue
            candidate[cand_index] = decoded
            is_end_of_candidate = (is_final or before_separator) and length_at_end
            arc_not_terminal = not is_terminal and not (
                contains_separators and decoded == separator_char
            )

            # replacement "any to two"
            length_replacement = self._match_any_to_two(word_index, cand_index)
            if length_replacement > 0:
                if is_end_of_candidate:
                    dist = h_matrix.get(depth - 1, depth - 1)
                    if dist <= eed:
                        extra = abs(word_len - 1 - (word_index + length_replacement - 2))
                        if extra > 0:
                            dist += extra
                        if dist <= eed:
                            candidates.append(
                                self._candidate_data("".join(candidate[: cand_index + 1]), dist)
                            )
                if arc_not_terminal:
                    x = h_matrix.get(depth, depth)
                    h_matrix.set(depth, depth, h_matrix.get(depth - 1, depth - 1))
                    self._find_repl(
                        candidates,
                        max(0, depth),
                        end_node,
                        word_index + length_replacement - 1,
                        cand_index + 1,
                    )
                    h_matrix.set(depth, depth, x)

            # replacement "any to one"
            length_replacement = self._match_any_to_one(word_index, cand_index)
            if length_replacement > 0:
                if is_end_of_candidate:
                    dist = h_matrix.get(depth, depth)
                    if dist <= eed:
                        extra = abs(word_len - 1 - (word_index + length_replacement - 1))
                        if extra > 0:
                            dist += extra
                        if dist <= eed:
                            candidates.append(
                                self._candidate_data("".join(candidate[: cand_index + 1]), dist)
                            )
                if arc_not_terminal:
                    self._find_repl(
                        candidates,
                        depth,
                        end_node,
                        word_index + length_replacement,
                        cand_index + 1,
                    )

            # general
            if self.cuted(depth, word_index, cand_index) <= eed:
                if is_end_of_candidate:
                    dist = self.ed(
                        word_len - 1 - (word_index - depth),
                        depth,
                        word_len - 1,
                        cand_index,
                    )
                    if dist <= eed:
                        candidates.append(
                            self._candidate_data("".join(candidate[: cand_index + 1]), dist)
                        )
                if arc_not_terminal:
                    self._find_repl(
                        candidates,
                        depth + 1,
                        end_node,
                        word_index + 1,
                        cand_index + 1,
                    )

    def _is_arc_not_terminal(self, arc: int, cand_index: int) -> bool:
        return not self.fsa.is_arc_terminal(arc) and not (
            self.contains_separators and self._candidate[cand_index] == self.separator_char
        )

    def _is_end_of_candidate(self, arc: int, word_index: int) -> bool:
        return (self.fsa.is_arc_final(arc) or self._is_before_separator(arc)) and (
            abs(self._word_len - 1 - word_index) <= self._effect_edit_distance
        )

    def _is_before_separator(self, arc: int) -> bool:
        if self.contains_separators:
            if self.fsa.is_arc_terminal(arc):
                return False
            arc1 = self.fsa.get_arc(self.fsa.get_end_node(arc), self.separator_byte)
            return arc1 != 0 and not self.fsa.is_arc_terminal(arc1)
        return False

    def ed(self, i: int, j: int, word_index: int, cand_index: int) -> int:
        word = self._word_processed
        candidate = self._candidate
        matrix = self.h_matrix
        p = matrix.p
        row = matrix.row_length
        base = matrix.edit_distance + 1
        x = word[word_index]
        y = candidate[cand_index]
        if x == y or (not self._simple_equality and self._are_equal(x, y)):
            result = p[(j - i + base) * row + j]
        elif (
            word_index > 0
            and cand_index > 0
            and x == candidate[cand_index - 1]
            and word[word_index - 1] == y
        ):
            a = p[(j - i + base) * row + j - 1]
            b = p[(j - i - 1 + base) * row + j]
            c = p[(j + 1 - i + base) * row + j + 1]
            result = 1 + min(a, b, c)
        else:
            a = p[(j - i + base) * row + j]
            b = p[(j - i - 1 + base) * row + j]
            c = p[(j + 1 - i + base) * row + j + 1]
            result = 1 + min(a, b, c)
        p[(j - i + base) * row + j + 1] = result
        return result

    def _are_equal(self, x: str, y: str) -> bool:
        if x == y:
            return True
        equivalent = self.metadata.equivalent_chars
        if equivalent:
            chars = equivalent.get(x)
            if chars is not None and y in chars:
                return True
        if self.metadata.ignore_diacritics:
            xn = unicodedata.normalize("NFD", x)
            yn = unicodedata.normalize("NFD", y)
            if xn[0] == yn[0]:
                return True
            if self.metadata.convert_case and is_letter(xn[0]):
                test_needed = is_lower_case(xn[0]) != is_lower_case(yn[0])
                if test_needed:
                    return char_to_lower(xn[0]) == char_to_lower(yn[0])
            return xn[0] == yn[0]
        return False

    def cuted(self, depth: int, word_index: int, cand_index: int) -> int:
        eed = self._effect_edit_distance
        lower = max(0, depth - eed)
        upper = min(self._word_len - 1 - (word_index - depth), depth + eed)
        min_ed = eed + 1
        wi = word_index + lower - depth
        ed = self.ed
        for i in range(lower, upper + 1):
            d = ed(i, depth, wi, cand_index)
            if d < min_ed:
                min_ed = d
            wi += 1
        return min_ed

    def _match_any_to_one(self, word_index: int, cand_index: int) -> int:
        reps = self._replacements_any_to_one.get(self._candidate[cand_index])
        if reps:
            word = self._word_processed
            for rep in reps:
                i = 0
                while i < len(rep) and (word_index + i) < self._word_len and rep[i] == word[word_index + i]:
                    i += 1
                if i == len(rep):
                    return i
        return 0

    def _match_any_to_two(self, word_index: int, cand_index: int) -> int:
        if cand_index > 0 and cand_index < MAX_WORD_LENGTH and word_index > 0:
            two_char = self._candidate[cand_index - 1] + self._candidate[cand_index]
            reps = self._replacements_any_to_two.get(two_char)
            if reps:
                word = self._word_processed
                for rep in reps:
                    if (
                        len(rep) == 2
                        and word_index < self._word_len
                        and self._candidate[cand_index - 1] == word[word_index - 1]
                        and self._candidate[cand_index] == word[word_index]
                    ):
                        return 0  # unnecessary replacements
                    i = 0
                    while (
                        i < len(rep)
                        and (word_index - 1 + i) < self._word_len
                        and rep[i] == word[word_index - 1 + i]
                    ):
                        i += 1
                    if i == len(rep):
                        return i
        return 0

    # ------------------------------------------------------------ case helpers

    def is_all_uppercase(self, text: str) -> bool:
        for ch in text:
            if is_letter(ch) and is_lower_case(ch):
                return False
        return True

    def is_not_all_lowercase(self, text: str) -> bool:
        for ch in text:
            if is_letter(ch) and not is_lower_case(ch):
                return True
        return False

    def is_not_capitalized_word(self, text: str) -> bool:
        if text and is_upper_case(text[0]):
            for ch in text[1:]:
                if is_letter(ch) and not is_lower_case(ch):
                    return True
            return False
        return True

    def is_mixed_case(self, text: str) -> bool:
        return (
            not self.is_all_uppercase(text)
            and self.is_not_capitalized_word(text)
            and self.is_not_all_lowercase(text)
        )

    def is_camel_case(self, text: str) -> bool:
        return (
            bool(text)
            and not self.is_all_uppercase(text)
            and self.is_not_capitalized_word(text)
            and is_upper_case(text[0])
            and (not len(text) > 1 or is_lower_case(text[1]))
            and self.is_not_all_lowercase(text)
        )


def contains_no_digit(text: str) -> bool:
    """Port of ``Speller.containsNoDigit``."""
    for ch in text:
        if is_digit(ch):
            return False
    return True


def build_plain_text_dictionary(
    lines: Sequence[bytes], metadata: DictionaryMetadata
) -> MorfologikDictionary:
    """Build the runtime dictionary LanguageTool creates from plain-text word lists."""
    ordered = sorted(set(lines))
    fsa = TrieFSA(ordered)
    return MorfologikDictionary(fsa=fsa, metadata=metadata)
