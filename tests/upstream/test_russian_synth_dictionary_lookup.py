"""tests/upstream/test_russian_synth_dictionary_lookup.py

Upstream parity tests for Russian synthesis dictionary (russian_synth.dict).
Compares low-level synthesis lookup outputs against committed oracle fixtures.
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
SYNTH_SAMPLE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "oracle_russian_synth_sample.json"


@pytest.fixture(scope="module")
def synth_dictionary() -> MorfologikDictionary:
    synth_path = RU_RESOURCE_DIR / "russian_synth.dict"
    return MorfologikDictionary.open(synth_path)


def test_oracle_synth_sample_parity(synth_dictionary: MorfologikDictionary):
    """Verify exact synthesis query outputs against committed oracle fixture."""
    assert SYNTH_SAMPLE_FIXTURE.is_file(), f"Missing fixture {SYNTH_SAMPLE_FIXTURE}"
    with open(SYNTH_SAMPLE_FIXTURE, "r", encoding="utf-8") as f:
        fixture_data = json.load(f)

    expected_queries = fixture_data.get("queries", {})
    assert len(expected_queries) > 0

    for query_key, expected_forms in expected_queries.items():
        lemma, pos_tag = query_key.split("|", 1)
        actual_forms = list(synth_dictionary.synthesize(lemma, pos_tag))
        assert actual_forms == expected_forms, f"Mismatch for synthesis query '{query_key}'"


def test_specific_synth_examples(synth_dictionary: MorfologikDictionary):
    """Verify specific Russian synthesis examples required by Task 0002."""
    # 1. семья (Nom) -> семья
    res_nom = synth_dictionary.synthesize("семья", "NN:Inanim:Fem:Sin:Nom")
    assert res_nom == ("семья",)

    # 2. семья (Gen / R) -> семьи
    res_gen = synth_dictionary.synthesize("семья", "NN:Inanim:Fem:Sin:R")
    assert res_gen == ("семьи",)

    # 3. дом (Nom Plural) -> дома
    res_dom_pl = synth_dictionary.synthesize("дом", "NN:Inanim:Masc:PL:Nom")
    assert res_dom_pl == ("дома",)

    # 4. Unknown lemma/tag returns empty tuple
    unknown_res = synth_dictionary.synthesize("абвгдежзийклмноп123", "NN:Inanim:Fem:Sin:Nom")
    assert unknown_res == ()
