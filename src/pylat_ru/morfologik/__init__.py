"""src/pylat_ru/morfologik/__init__.py

Morfologik FSA reader, metadata parser, sequence encoders, and dictionary lookup.
"""

from pylat_ru.morfologik.dictionary import DictionaryEntry, MorfologikDictionary
from pylat_ru.morfologik.errors import (
    CorruptedFSAError,
    InvalidMetadataError,
    MalformedSequenceError,
    MorfologikError,
    UnsupportedEncoderError,
    UnsupportedEncodingError,
    UnsupportedFSAFormatError,
)
from pylat_ru.morfologik.fsa import CFSA2, FSA, read_fsa
from pylat_ru.morfologik.metadata import DictionaryMetadata
from pylat_ru.morfologik.sequence_encoder import (
    SequenceEncoder,
    TrimSuffixEncoder,
    get_sequence_encoder,
)

__all__ = [
    "CFSA2",
    "CorruptedFSAError",
    "DictionaryEntry",
    "DictionaryMetadata",
    "FSA",
    "InvalidMetadataError",
    "MalformedSequenceError",
    "MorfologikDictionary",
    "MorfologikError",
    "SequenceEncoder",
    "TrimSuffixEncoder",
    "UnsupportedEncoderError",
    "UnsupportedEncodingError",
    "UnsupportedFSAFormatError",
    "get_sequence_encoder",
    "read_fsa",
]
