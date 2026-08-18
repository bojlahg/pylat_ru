"""tests/upstream/test_russian_dictionary_lookup.py

Upstream parity tests for Russian morphological dictionary (russian.dict).
Compares low-level lookup outputs against committed oracle fixtures.
"""

import json
from pathlib import Path
import pytest

from pylat_ru.morfologik.dictionary import MorfologikDictionary

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
DICT_SAMPLE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "oracle_russian_dict_sample.json"


@pytest.fixture(scope="module")
def ru_dictionary() -> MorfologikDictionary:
    dict_path = RU_RESOURCE_DIR / "russian.dict"
    return MorfologikDictionary.open(dict_path)


def test_oracle_sample_parity(ru_dictionary: MorfologikDictionary):
    """Verify exact ordered (stem, tag) outputs against committed oracle fixture."""
    assert DICT_SAMPLE_FIXTURE.is_file(), f"Missing fixture {DICT_SAMPLE_FIXTURE}"
    with open(DICT_SAMPLE_FIXTURE, "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    expected_words = fixture_data.get("words", {})
    assert len(expected_words) > 0

    for word, expected_readings in expected_words.items():
        actual_entries = ru_dictionary.lookup(word)
        actual_readings = [{"stem": e.stem, "tag": e.tag} for e in actual_entries]
        assert actual_readings == expected_readings, f"Mismatch for word '{word}'"


def test_specific_candidate_words(ru_dictionary: MorfologikDictionary):
    """Verify specific candidate words mentioned in Task 0002 / RussianTaggerTest."""
    # 1. 'дом' has Nom and Acc readings
    dom_entries = ru_dictionary.lookup("дом")
    dom_tags = [e.tag for e in dom_entries]
    assert "NN:Inanim:Masc:Sin:Nom" in dom_tags
    assert "NN:Inanim:Masc:Sin:V" in dom_tags
    assert all(e.stem == "дом" for e in dom_entries)

    # 2. 'смешалось' has neuter past verb reading
    smesh_entries = ru_dictionary.lookup("смешалось")
    assert len(smesh_entries) == 1
    assert smesh_entries[0].stem == "смешаться"
    assert smesh_entries[0].tag == "VB:Past:INTR:PFV:Neut"

    # 3. 'блукать' has infinitive verb reading with empty trailing slot
    bluk_entries = ru_dictionary.lookup("блукать")
    assert len(bluk_entries) == 1
    assert bluk_entries[0].stem == "блукать"
    assert bluk_entries[0].tag == "VB:INF:"

    # 4. Unknown word returns empty tuple
    unknown_entries = ru_dictionary.lookup("абвгдежзийклмноп123")
    assert unknown_entries == ()
