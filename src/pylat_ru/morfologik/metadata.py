"""src/pylat_ru/morfologik/metadata.py

Parser and validator for Morfologik dictionary metadata (.info files).
"""

from __future__ import annotations

import codecs
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Dict, List, Mapping, Optional, TextIO, Union

from pylat_ru.morfologik.errors import (
    InvalidMetadataError,
    UnsupportedEncoderError,
    UnsupportedEncodingError,
)

# Standard metadata property names defined by Morfologik
KEY_SEPARATOR = "fsa.dict.separator"
KEY_ENCODING = "fsa.dict.encoding"
KEY_ENCODER = "fsa.dict.encoder"
KEY_FREQUENCY_INCLUDED = "fsa.dict.frequency-included"
KEY_IGNORE_PUNCTUATION = "fsa.dict.ignore-punctuation"
KEY_IGNORE_NUMBERS = "fsa.dict.ignore-numbers"
KEY_IGNORE_CAMEL_CASE = "fsa.dict.ignore-camel-case"
KEY_IGNORE_ALL_UPPERCASE = "fsa.dict.ignore-all-uppercase"
KEY_IGNORE_DIACRITICS = "fsa.dict.ignore-diacritics"
KEY_CONVERT_CASE = "fsa.dict.convert-case"
KEY_SUPPORT_RUN_ON_WORDS = "fsa.dict.support-run-on-words"
KEY_INPUT_CONVERSION = "fsa.dict.input-conversion"
KEY_OUTPUT_CONVERSION = "fsa.dict.output-conversion"
KEY_REPLACEMENT_PAIRS = "fsa.dict.replacement-pairs"
KEY_EQUIVALENT_CHARS = "fsa.dict.equivalent-chars"
KEY_AUTHOR = "fsa.dict.author"
KEY_LICENSE = "fsa.dict.license"
KEY_CREATION_DATE = "fsa.dict.created-date"

SUPPORTED_ENCODERS = frozenset({"SUFFIX"})


@dataclass(frozen=True)
class DictionaryMetadata:
    """Immutable, typed container for parsed dictionary metadata."""

    separator: str
    separator_byte: int
    encoding: str
    encoder: str
    frequency_included: bool = False
    ignore_punctuation: bool = True
    ignore_numbers: bool = True
    ignore_camel_case: bool = True
    ignore_all_uppercase: bool = True
    ignore_diacritics: bool = True
    convert_case: bool = True
    support_run_on_words: bool = True
    input_conversion: Dict[str, str] = field(default_factory=dict)
    output_conversion: Dict[str, str] = field(default_factory=dict)
    raw_attributes: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Union[str, Path]) -> DictionaryMetadata:
        """Parse metadata from a .info file path."""
        p = Path(path)
        if not p.is_file():
            raise InvalidMetadataError(f"Metadata file not found: {p}")
        try:
            with open(p, "r", encoding="utf-8") as f:
                return cls.from_text(f.read(), source_name=str(p))
        except UnicodeDecodeError as e:
            raise InvalidMetadataError(f"Metadata file {p} is not valid UTF-8: {e}") from e

    @classmethod
    def from_text(cls, text: str, source_name: str = "<string>") -> DictionaryMetadata:
        """Parse metadata from raw properties text."""
        raw_map: Dict[str, str] = {}
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("!"):
                continue

            # Parse key=value or key:value
            sep_idx = -1
            for i, c in enumerate(line):
                if c in ("=", ":"):
                    sep_idx = i
                    break

            if sep_idx == -1:
                raise InvalidMetadataError(
                    f"Malformed property at {source_name}:{line_no}: missing '=' or ':' delimiter"
                )

            key = line[:sep_idx].strip()
            val = line[sep_idx + 1:].strip()
            if not key:
                raise InvalidMetadataError(
                    f"Empty property key at {source_name}:{line_no}"
                )
            raw_map[key] = val

        return cls.from_dict(raw_map, source_name=source_name)

    @classmethod
    def from_dict(cls, attrs: Mapping[str, str], source_name: str = "<dict>") -> DictionaryMetadata:
        """Validate and construct DictionaryMetadata from a property mapping."""
        # 1. Validate required properties
        missing = []
        for req in (KEY_SEPARATOR, KEY_ENCODING, KEY_ENCODER):
            if req not in attrs or not attrs[req].strip():
                missing.append(req)
        if missing:
            raise InvalidMetadataError(
                f"Missing required metadata properties in {source_name}: {', '.join(missing)}"
            )

        encoding_str = attrs[KEY_ENCODING].strip()
        # 2. Validate encoding
        try:
            codecs.lookup(encoding_str)
        except LookupError:
            raise UnsupportedEncodingError(
                f"Unsupported character encoding '{encoding_str}' in {source_name}"
            )

        # 3. Validate separator
        sep_str = attrs[KEY_SEPARATOR]
        if len(sep_str) != 1:
            raise InvalidMetadataError(
                f"Invalid separator '{sep_str}' in {source_name}: separator must be a single character"
            )
        try:
            sep_bytes = sep_str.encode(encoding_str)
            if len(sep_bytes) != 1:
                raise InvalidMetadataError(
                    f"Separator '{sep_str}' encodes to {len(sep_bytes)} bytes in {encoding_str}; must be exactly 1 byte"
                )
            sep_byte = sep_bytes[0]
        except Exception as e:
            raise InvalidMetadataError(
                f"Separator '{sep_str}' cannot be encoded in {encoding_str}: {e}"
            ) from e

        # 4. Validate encoder
        encoder_str = attrs[KEY_ENCODER].strip().upper()
        if encoder_str not in SUPPORTED_ENCODERS:
            raise UnsupportedEncoderError(
                f"Unsupported encoder '{encoder_str}' in {source_name}. Supported encoders: {sorted(SUPPORTED_ENCODERS)}"
            )

        # 5. Parse booleans with Morfologik defaults
        def _parse_bool(key: str, default: bool) -> bool:
            if key not in attrs:
                return default
            v = attrs[key].strip().lower()
            if v in ("true", "1", "yes"):
                return True
            if v in ("false", "0", "no"):
                return False
            raise InvalidMetadataError(
                f"Invalid boolean value for property '{key}' in {source_name}: '{attrs[key]}'"
            )

        freq_inc = _parse_bool(KEY_FREQUENCY_INCLUDED, False)
        ign_punct = _parse_bool(KEY_IGNORE_PUNCTUATION, True)
        ign_nums = _parse_bool(KEY_IGNORE_NUMBERS, True)
        ign_camel = _parse_bool(KEY_IGNORE_CAMEL_CASE, True)
        ign_upper = _parse_bool(KEY_IGNORE_ALL_UPPERCASE, True)
        ign_diacr = _parse_bool(KEY_IGNORE_DIACRITICS, True)
        conv_case = _parse_bool(KEY_CONVERT_CASE, True)
        run_on = _parse_bool(KEY_SUPPORT_RUN_ON_WORDS, True)

        # 6. Conversions
        def _parse_pairs(val_str: Optional[str]) -> Dict[str, str]:
            if not val_str:
                return {}
            res: Dict[str, str] = {}
            for part in val_str.split(","):
                part = part.strip()
                if not part:
                    continue
                if "/" not in part:
                    continue
                k, v = part.split("/", 1)
                res[k.strip()] = v.strip()
            return res

        in_conv = _parse_pairs(attrs.get(KEY_INPUT_CONVERSION))
        out_conv = _parse_pairs(attrs.get(KEY_OUTPUT_CONVERSION))

        return cls(
            separator=sep_str,
            separator_byte=sep_byte,
            encoding=encoding_str.lower(),
            encoder=encoder_str,
            frequency_included=freq_inc,
            ignore_punctuation=ign_punct,
            ignore_numbers=ign_nums,
            ignore_camel_case=ign_camel,
            ignore_all_uppercase=ign_upper,
            ignore_diacritics=ign_diacr,
            convert_case=conv_case,
            support_run_on_words=run_on,
            input_conversion=in_conv,
            output_conversion=out_conv,
            raw_attributes=dict(attrs),
        )
