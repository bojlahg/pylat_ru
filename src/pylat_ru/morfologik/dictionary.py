"""src/pylat_ru/morfologik/dictionary.py

High-level dictionary interface for morphological and synthesis lookups over Morfologik FSAs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Union

from pylat_ru.morfologik.errors import InvalidMetadataError
from pylat_ru.morfologik.fsa import FSA, SEQUENCE_IS_A_PREFIX, read_fsa
from pylat_ru.morfologik.metadata import DictionaryMetadata
from pylat_ru.morfologik.sequence_encoder import SequenceEncoder, get_sequence_encoder


@dataclass(frozen=True)
class DictionaryEntry:
    """A single decoded entry from a morphological or synthesis dictionary."""

    stem: Optional[str]
    tag: Optional[str]
    raw_sequence: Optional[bytes] = None

    def __repr__(self) -> str:
        return f"DictionaryEntry(stem={self.stem!r}, tag={self.tag!r})"


class MorfologikDictionary:
    """Morfologik dictionary encapsulating an FSA, metadata, and sequence decoder."""

    def __init__(
        self,
        fsa: FSA,
        metadata: DictionaryMetadata,
        sequence_encoder: Optional[SequenceEncoder] = None,
    ) -> None:
        self.fsa = fsa
        self.metadata = metadata
        self.encoder = sequence_encoder or get_sequence_encoder(metadata.encoder)
        self.encoding = metadata.encoding
        self.separator_byte = metadata.separator_byte
        self.separator_char = metadata.separator
        self._prefix_bytes = self.encoder.prefix_bytes()

    @classmethod
    def open(
        cls,
        dict_path: Union[str, Path],
        info_path: Optional[Union[str, Path]] = None,
    ) -> MorfologikDictionary:
        """Load and instantiate a dictionary from a .dict file and optional .info file."""
        dp = Path(dict_path)
        if not dp.is_file():
            raise FileNotFoundError(f"Dictionary file not found: {dp}")

        if info_path is None:
            ip = dp.with_suffix(".info")
            if not ip.is_file():
                raise InvalidMetadataError(
                    f"Accompanying metadata file not found: expected {ip}"
                )
        else:
            ip = Path(info_path)
            if not ip.is_file():
                raise InvalidMetadataError(f"Metadata file not found: {ip}")

        metadata = DictionaryMetadata.from_file(ip)
        fsa = read_fsa(dp)
        return cls(fsa=fsa, metadata=metadata)

    def lookup(self, word: str) -> Tuple[DictionaryEntry, ...]:
        """Perform exact morphological lookup for a word.

        Returns:
            Tuple of DictionaryEntry objects with decoded stems and tags in deterministic order.
            Returns empty tuple if the word is not in the dictionary.
        """
        # Separator character can never be part of a valid input word
        if self.separator_char in word:
            return ()

        # Encode word into dictionary encoding (e.g. KOI8-R)
        try:
            word_bytes = word.encode(self.encoding)
        except (UnicodeEncodeError, LookupError):
            # Input word cannot be represented in dictionary charset
            return ()

        match_kind, _, node = self.fsa.match(word_bytes)
        if match_kind != SEQUENCE_IS_A_PREFIX:
            return ()

        # Follow separator arc
        sep_arc = self.fsa.get_arc(node, self.separator_byte)
        if sep_arc == 0 or self.fsa.is_arc_final(sep_arc):
            return ()

        dest_node = self.fsa.get_destination_node_offset(sep_arc)
        if dest_node == 0:
            return ()

        entries: List[DictionaryEntry] = []
        for seq in self.fsa.get_sequences(dest_node):
            # Sequence structure: {trimCode}{stemSuffix}+{tag}
            # Find the separator splitting stem transformation and tag
            sep_idx = -1
            for i in range(self._prefix_bytes, len(seq)):
                if seq[i] == self.separator_byte:
                    sep_idx = i
                    break

            if sep_idx != -1:
                encoded_stem = seq[:sep_idx]
                tag_bytes = seq[sep_idx + 1:]
            else:
                encoded_stem = seq
                tag_bytes = b""

            # Decode stem bytes
            stem_bytes = self.encoder.decode(word_bytes, encoded_stem)
            stem = stem_bytes.decode(self.encoding, errors="replace")
            tag = tag_bytes.decode(self.encoding, errors="replace") if tag_bytes else None

            entries.append(DictionaryEntry(stem=stem, tag=tag, raw_sequence=seq))

        return tuple(entries)

    def synthesize(self, lemma: str, pos_tag: str) -> Tuple[str, ...]:
        """Perform synthesis lookup for a lemma and target POS tag.

        In LanguageTool's BaseSynthesizer, synthesis queries use the key format:
            lemma + "|" + pos_tag
        and return the decoded stem of each matching entry.

        Returns:
            Tuple of synthesized word forms.
        """
        key = f"{lemma}|{pos_tag}"
        entries = self.lookup(key)
        results: List[str] = []
        for e in entries:
            if e.stem is not None:
                results.append(e.stem)
        return tuple(results)
