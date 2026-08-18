"""tests/unit/test_morfologik_metadata.py

Unit tests for Morfologik dictionary metadata parser (.info).
"""

from pathlib import Path
import pytest

from pylat_ru.morfologik.errors import (
    InvalidMetadataError,
    UnsupportedEncoderError,
    UnsupportedEncodingError,
)
from pylat_ru.morfologik.metadata import DictionaryMetadata

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RU_RESOURCE_DIR = (
    REPO_ROOT
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
)


def test_parse_real_russian_info():
    """Verify parsing of real pinned russian.info file."""
    info_path = RU_RESOURCE_DIR / "russian.info"
    meta = DictionaryMetadata.from_file(info_path)
    assert meta.separator == "+"
    assert meta.separator_byte == ord("+")
    assert meta.encoding == "koi8-r"
    assert meta.encoder == "SUFFIX"
    assert meta.frequency_included is False
    assert "fsa.dict.separator" in meta.raw_attributes
    assert "fsa.dict.encoding" in meta.raw_attributes
    assert "fsa.dict.encoder" in meta.raw_attributes


def test_parse_real_russian_synth_info():
    """Verify parsing of real pinned russian_synth.info file."""
    info_path = RU_RESOURCE_DIR / "russian_synth.info"
    meta = DictionaryMetadata.from_file(info_path)
    assert meta.separator == "+"
    assert meta.separator_byte == ord("+")
    assert meta.encoding == "koi8-r"
    assert meta.encoder == "SUFFIX"


def test_parse_missing_required_keys():
    """Verify error on missing required properties."""
    with pytest.raises(InvalidMetadataError, match="Missing required metadata"):
        DictionaryMetadata.from_text("fsa.dict.separator=+\n")

    with pytest.raises(InvalidMetadataError, match="Missing required metadata"):
        DictionaryMetadata.from_text("fsa.dict.encoding=koi8-r\n")

    with pytest.raises(InvalidMetadataError, match="Missing required metadata"):
        DictionaryMetadata.from_text("fsa.dict.separator=+\nfsa.dict.encoding=koi8-r\n")


def test_parse_invalid_separator():
    """Verify error on multi-character or invalid separator."""
    # Multi-character separator
    with pytest.raises(InvalidMetadataError, match="single character"):
        DictionaryMetadata.from_text(
            "fsa.dict.separator=++\nfsa.dict.encoding=koi8-r\nfsa.dict.encoder=SUFFIX\n"
        )


def test_parse_unsupported_encoder():
    """Verify error on unsupported encoder type."""
    with pytest.raises(UnsupportedEncoderError, match="Unsupported encoder 'PREFIX'"):
        DictionaryMetadata.from_text(
            "fsa.dict.separator=+\nfsa.dict.encoding=koi8-r\nfsa.dict.encoder=PREFIX\n"
        )


def test_parse_unsupported_encoding():
    """Verify error on invalid/unsupported charset encoding."""
    with pytest.raises(UnsupportedEncodingError, match="Unsupported character encoding"):
        DictionaryMetadata.from_text(
            "fsa.dict.separator=+\nfsa.dict.encoding=unknown-charset-12345\nfsa.dict.encoder=SUFFIX\n"
        )


def test_parse_comments_and_custom_attributes():
    """Verify comments, empty lines, and unknown/custom properties are retained."""
    text = """
    # This is a comment
    ! Another comment
    fsa.dict.separator=+
    fsa.dict.encoding=koi8-r
    fsa.dict.encoder=SUFFIX
    fsa.dict.frequency-included=true
    custom.property.name=custom_value
    """
    meta = DictionaryMetadata.from_text(text)
    assert meta.frequency_included is True
    assert meta.raw_attributes.get("custom.property.name") == "custom_value"
