"""src/pylat_ru/morfologik/metadata.py

Parser and validator for Morfologik dictionary metadata (.info files).
"""

from __future__ import annotations

import codecs
import re
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
KEY_IGNORE_PUNCTUATION = "fsa.dict.speller.ignore-punctuation"
KEY_IGNORE_NUMBERS = "fsa.dict.speller.ignore-numbers"
KEY_IGNORE_CAMEL_CASE = "fsa.dict.speller.ignore-camel-case"
KEY_IGNORE_ALL_UPPERCASE = "fsa.dict.speller.ignore-all-uppercase"
KEY_IGNORE_DIACRITICS = "fsa.dict.speller.ignore-diacritics"
KEY_CONVERT_CASE = "fsa.dict.speller.convert-case"
KEY_SUPPORT_RUN_ON_WORDS = "fsa.dict.speller.runon-words"
KEY_LOCALE = "fsa.dict.speller.locale"
KEY_INPUT_CONVERSION = "fsa.dict.input-conversion"
KEY_OUTPUT_CONVERSION = "fsa.dict.output-conversion"
KEY_REPLACEMENT_PAIRS = "fsa.dict.speller.replacement-pairs"
KEY_EQUIVALENT_CHARS = "fsa.dict.speller.equivalent-chars"
KEY_AUTHOR = "fsa.dict.author"
KEY_LICENSE = "fsa.dict.license"
KEY_CREATION_DATE = "fsa.dict.created"

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
    replacement_pairs: Dict[str, List[str]] = field(default_factory=dict)
    equivalent_chars: Dict[str, List[str]] = field(default_factory=dict)
    locale: Optional[str] = None
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

        # 6. Conversions and speller pair attributes.
        #
        # Morfologik splits these attributes on ",\s*" and each element on " ",
        # requiring exactly two space-separated parts (DictionaryAttribute).
        def _split_pairs(key: str, val_str: Optional[str]) -> List[List[str]]:
            if val_str is None:
                return []
            pairs: List[List[str]] = []
            for part in re.split(r",\s*", val_str):
                part = part.strip()
                two = part.split(" ")
                if len(two) != 2:
                    raise InvalidMetadataError(
                        f"Attribute {key} is not in the proper format in {source_name}: {val_str}"
                    )
                pairs.append(two)
            return pairs

        def _parse_conversion(key: str) -> Dict[str, str]:
            res: Dict[str, str] = {}
            for src, dst in _split_pairs(key, attrs.get(key)):
                if src in res:
                    raise InvalidMetadataError(
                        f"Conversion cannot specify different values for the same input string in "
                        f"{source_name}: {src}"
                    )
                res[src] = dst
            return res

        in_conv = _parse_conversion(KEY_INPUT_CONVERSION)
        out_conv = _parse_conversion(KEY_OUTPUT_CONVERSION)

        replacement_pairs: Dict[str, List[str]] = {}
        for src, dst in _split_pairs(KEY_REPLACEMENT_PAIRS, attrs.get(KEY_REPLACEMENT_PAIRS)):
            replacement_pairs.setdefault(src, []).append(dst)

        equivalent_chars: Dict[str, List[str]] = {}
        for src, dst in _split_pairs(KEY_EQUIVALENT_CHARS, attrs.get(KEY_EQUIVALENT_CHARS)):
            if len(src) != 1 or len(dst) != 1:
                raise InvalidMetadataError(
                    f"Attribute {KEY_EQUIVALENT_CHARS} is not in the proper format in {source_name}: "
                    f"{attrs.get(KEY_EQUIVALENT_CHARS)}"
                )
            equivalent_chars.setdefault(src, []).append(dst)

        locale_value = attrs.get(KEY_LOCALE)
        locale_value = locale_value.strip() if locale_value else None

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
            replacement_pairs=replacement_pairs,
            equivalent_chars=equivalent_chars,
            locale=locale_value,
            raw_attributes=dict(attrs),
        )
