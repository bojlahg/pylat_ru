"""tests/test_synthesizer_subsystem.py

Comprehensive tests for RussianSynthesizer, BaseSynthesizer, Roman number formatting,
manual overlays, regex synthesis, null-lemma handling, case sensitivity, and error handling.
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path
import pytest

from pylat_ru.analysis import AnalyzedToken
from pylat_ru.synthesis import (
    BaseSynthesizer,
    RussianSynthesizer,
    SynthesisResourceError,
    Synthesizer,
    get_roman_number,
    int_to_roman,
)


def test_roman_conversion():
    """Verify integer to Roman numeral conversion matching Roman.sor."""
    assert int_to_roman(1) == "I"
    assert int_to_roman(4) == "IV"
    assert int_to_roman(9) == "IX"
    assert int_to_roman(123) == "CXXIII"
    assert int_to_roman(1984) == "MCMLXXXIV"
    assert int_to_roman(2024) == "MMXXIV"
    assert int_to_roman(3999) == "MMMCMXCIX"

    # get_roman_number wrapper
    assert get_roman_number("123") == "CXXIII"
    assert get_roman_number("  45  ") == "XLV"
    assert get_roman_number("not_a_number") == "not_a_number"
    assert get_roman_number("-5") == "-5"


def test_russian_synthesizer_singleton():
    """Verify singleton instance behavior."""
    s1 = RussianSynthesizer.get_instance()
    s2 = RussianSynthesizer.INSTANCE()
    s3 = RussianSynthesizer.get_instance()
    assert s1 is s2
    assert s1 is s3
    assert isinstance(s1, Synthesizer)
    assert isinstance(s1, BaseSynthesizer)


def test_exact_synthesis():
    """Verify exact POS tag synthesis on standard vocabulary."""
    synth = RussianSynthesizer.get_instance()

    # Nouns
    assert synth.synthesize("семья", "NN:Inanim:Fem:Sin:Nom") == ["семья"]
    assert synth.synthesize("семья", "NN:Inanim:Fem:Sin:R") == ["семьи"]
    assert synth.synthesize("дом", "NN:Inanim:Masc:PL:Nom") == ["дома"]
    assert synth.synthesize("дом", "NN:Inanim:Masc:Sin:Nom") == ["дом"]

    # Verbs
    forms_inf = synth.synthesize("бежать", "VB:INF:INTR:IMPFV")
    assert "бежать" in forms_inf

    # Adjectives
    forms_adj = synth.synthesize("красивый", "ADJ:Posit:Fem:Nom")
    assert "красивая" in forms_adj

    # Trailing empty colon tag
    forms_blukat = synth.synthesize("блукать", "VB:INF:")
    assert forms_blukat == ["блукать"]


def test_null_lemma_and_case_sensitivity():
    """Verify AnalyzedToken with lemma=None returns empty array for lemma-dependent tags, but processes special numbers."""
    synth = RussianSynthesizer.get_instance()

    # AnalyzedToken with lemma=None for standard synthesis
    tok_null = AnalyzedToken("семья", lemma=None, pos_tag="NN:Inanim:Fem:Sin:Nom")
    assert synth.synthesize(tok_null, "NN:Inanim:Fem:Sin:Nom") == []
    assert synth.synthesize(tok_null, "NN:Inanim:Fem:.*", pos_tag_is_regex=True) == []

    # AnalyzedToken with lemma=None for special number tags
    tok_num_null = AnalyzedToken("123", lemma=None, pos_tag="NUM")
    assert synth.synthesize(tok_num_null, "_spell_number_") == ["123"]
    assert synth.synthesize(tok_num_null, "_spell_number_:feminine") == ["feminine 123"]
    assert synth.synthesize(tok_num_null, "_spell_number_:Roman") == ["CXXIII"]

    # Case sensitivity: uppercase "Семья" has no entry in dictionary
    assert synth.synthesize("Семья", "NN:Inanim:Fem:Sin:Nom") == []
    assert synth.synthesize("семья", "NN:Inanim:Fem:Sin:Nom") == ["семья"]


def test_regex_synthesis():
    """Verify regex-based synthesis across tags_russian.txt in deterministic order."""
    synth = RussianSynthesizer.get_instance()

    # Regex on noun forms
    forms_semya = synth.synthesize("семья", "NN:Inanim:Fem:.*", pos_tag_is_regex=True)
    assert len(forms_semya) == 13
    assert forms_semya[0] == "семьям"
    assert "семья" in forms_semya
    assert "семьи" in forms_semya
    assert "семью" in forms_semya

    # Regex on verb forms
    forms_begat = synth.synthesize("бежать", "VB:.*", pos_tag_is_regex=True)
    assert len(forms_begat) >= 15
    assert "бежим" in forms_begat
    assert "бежал" in forms_begat
    assert "бегут" in forms_begat


def test_predicate_synthesis():
    """Verify synthesize_for_pos_tags with custom predicates."""
    synth = RussianSynthesizer.get_instance()

    # Match only plural nominative tags
    forms = synth.synthesize_for_pos_tags(
        "дом", lambda t: t.startswith("NN:") and ":PL:Nom" in t
    )
    assert forms == ["дома"]


def test_manual_additions():
    """Verify manual additions from added.txt take effect."""
    synth = RussianSynthesizer.get_instance()

    # мадам from added.txt
    assert synth.synthesize("мадам", "NN:Name:Fem:PL") == ["мадам"]

    # шлифмашина from added.txt
    assert synth.synthesize("шлифмашина", "NN:Inanim:Masc:Sin:Nom") == ["шлифмашина"]


def test_manual_removals():
    """Verify manual removals from removed.txt filter out obsolete readings."""
    synth = RussianSynthesizer.get_instance()

    # дерево (PL R) binary dict contains "деревьев" (and originally "дерев" which is in removed.txt)
    forms_derevo = synth.synthesize("дерево", "NN:Inanim:Neut:PL:R")
    assert "деревьев" in forms_derevo
    assert "дерев" not in forms_derevo

    # втэк (Masc Sin Nom) binary dict contains "втэк", removed.txt removes it
    assert synth.synthesize("втэк", "NN:Inanim:Masc:Sin:Nom") == []

    # может (PARENTHESIS) binary dict contains "может", removed.txt removes it
    assert synth.synthesize("может", "PARENTHESIS") == []


def test_special_number_tags():
    """Verify _spell_number_ tags."""
    synth = RussianSynthesizer.get_instance()

    tok = AnalyzedToken("123", lemma="123", pos_tag="NUM")
    assert synth.synthesize(tok, "_spell_number_") == ["123"]
    assert synth.synthesize(tok, "_spell_number_:feminine") == ["feminine 123"]
    assert synth.synthesize(tok, "_spell_number_:Roman") == ["CXXIII"]


def test_special_number_exact_vs_regex_mode():
    """Verify exact special tag mode (pos_tag_is_regex=False) vs regexp mode (pos_tag_is_regex=True)."""
    synth = RussianSynthesizer.get_instance()

    # In exact mode (pos_tag_is_regex=False), special tags format the number
    assert synth.synthesize("123", "_spell_number_", pos_tag_is_regex=False) == ["123"]
    assert synth.synthesize("123", "_spell_number_:feminine", pos_tag_is_regex=False) == ["feminine 123"]
    assert synth.synthesize("123", "_spell_number_:Roman", pos_tag_is_regex=False) == ["CXXIII"]

    # In regex mode (pos_tag_is_regex=True), special tags are treated as POS regexes and return []
    assert synth.synthesize("123", "_spell_number_", pos_tag_is_regex=True) == []
    assert synth.synthesize("123", "_spell_number_:feminine", pos_tag_is_regex=True) == []
    assert synth.synthesize("123", "_spell_number_:Roman", pos_tag_is_regex=True) == []

    # AnalyzedToken with lemma=None:
    tok_null = AnalyzedToken("123", lemma=None, pos_tag="NUM")
    assert synth.synthesize(tok_null, "_spell_number_:Roman", pos_tag_is_regex=False) == ["CXXIII"]
    assert synth.synthesize(tok_null, "_spell_number_:Roman", pos_tag_is_regex=True) == []


def test_invalid_regex_error_message():
    """Verify exact LanguageTool error message on invalid regex pattern."""
    synth = RussianSynthesizer.get_instance()
    tok = AnalyzedToken("слово", lemma="слово", pos_tag="TAG")

    with pytest.raises(RuntimeError) as exc_info:
        synth.synthesize(tok, "[invalid_regex(", pos_tag_is_regex=True)

    expected_msg = "Error trying to synthesize POS tag [invalid_regex( (posTagRegExp: true) from token слово"
    assert expected_msg in str(exc_info.value)


def test_utility_methods():
    """Verify get_pos_tag_correction and get_target_pos_tag."""
    synth = RussianSynthesizer.get_instance()

    assert synth.get_pos_tag_correction("TAG:123") == "TAG:123"
    assert synth.get_target_pos_tag(["TAG1", "TAG2", "TAG3"], "DEFAULT") == "TAG3"
    assert synth.get_target_pos_tag([], "DEFAULT") == "DEFAULT"


def test_missing_resource_fail_closed(tmp_path: Path):
    """Verify missing dictionary or tags file raises SynthesisResourceError."""
    fake_dict = tmp_path / "missing.dict"
    fake_tags = tmp_path / "missing_tags.txt"

    with pytest.raises(SynthesisResourceError):
        RussianSynthesizer(resource_path=fake_dict, tag_file_path=fake_tags)


def test_thread_safety():
    """Verify concurrent queries across multiple threads."""
    synth = RussianSynthesizer.get_instance()

    def query(lemma: str, tag: str) -> list[str]:
        return synth.synthesize(lemma, tag, pos_tag_is_regex=tag.endswith(".*"))

    queries = [
        ("семья", "NN:Inanim:Fem:Sin:Nom"),
        ("семья", "NN:Inanim:Fem:.*"),
        ("дом", "NN:Inanim:Masc:PL:Nom"),
        ("бежать", "VB:.*"),
        ("красивый", "ADJ:Short:.*"),
        ("123", "_spell_number_:Roman"),
    ] * 20

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(query, q[0], q[1]) for q in queries]
        results = [f.result() for f in futures]

    assert len(results) == len(queries)
    assert all(len(r) > 0 for r in results)
