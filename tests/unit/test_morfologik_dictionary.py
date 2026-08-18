"""tests/unit/test_morfologik_dictionary.py

Unit tests for MorfologikDictionary loading and lookup semantics.
"""

from pathlib import Path
import pytest

from pylat_ru.morfologik.dictionary import DictionaryEntry, MorfologikDictionary
from pylat_ru.morfologik.errors import InvalidMetadataError

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


def test_open_dictionary_success():
    """Verify MorfologikDictionary opens both morphological and synthesis dictionaries."""
    dict_path = RU_RESOURCE_DIR / "russian.dict"
    d = MorfologikDictionary.open(dict_path)
    assert d.encoding == "koi8-r"
    assert d.separator_char == "+"

    synth_path = RU_RESOURCE_DIR / "russian_synth.dict"
    sd = MorfologikDictionary.open(synth_path)
    assert sd.encoding == "koi8-r"


def test_open_dictionary_missing_files():
    """Verify FileNotFoundError / InvalidMetadataError on non-existent paths."""
    with pytest.raises(FileNotFoundError):
        MorfologikDictionary.open("non_existent_dict.dict")

    # If dict exists but info does not
    dict_path = RU_RESOURCE_DIR / "russian.dict"
    with pytest.raises(InvalidMetadataError):
        MorfologikDictionary.open(dict_path, info_path="non_existent_info.info")


def test_lookup_edge_cases():
    """Verify lookups with separator chars, unmappable chars, or unknown words."""
    dict_path = RU_RESOURCE_DIR / "russian.dict"
    d = MorfologikDictionary.open(dict_path)

    # Word containing separator
    assert d.lookup("слово+тест") == ()

    # Word with characters outside KOI8-R (e.g. Greek / Chinese)
    assert d.lookup("αβγδ") == ()
    assert d.lookup("你好") == ()

    # Unknown Russian word
    assert d.lookup("несуществующеедлинноеслово123") == ()


def test_lookup_stability_and_ordering():
    """Verify repeated lookups return identical results in identical deterministic order."""
    dict_path = RU_RESOURCE_DIR / "russian.dict"
    d = MorfologikDictionary.open(dict_path)

    word = "все"
    res1 = d.lookup(word)
    res2 = d.lookup(word)
    res3 = d.lookup(word)

    assert res1 == res2 == res3
    assert len(res1) > 1
    assert all(isinstance(e, DictionaryEntry) for e in res1)
