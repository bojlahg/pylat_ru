"""Unit tests for the native Morfologik speller port (morfologik-stemming 2.1.9)."""

from __future__ import annotations

import pytest

from pylat_ru.morfologik.metadata import DictionaryMetadata
from pylat_ru.morfologik.speller import (
    FREQ_RANGES,
    HMatrix,
    MAX_WORD_LENGTH,
    Speller,
    TrieFSA,
    apply_replacements,
    build_plain_text_dictionary,
)
from pylat_ru.spelling import load_binary_dictionary


@pytest.fixture(scope="module")
def ru_speller() -> Speller:
    return Speller(load_binary_dictionary("ru_RU"), 1)


def test_dictionary_metadata_parses_pinned_speller_attributes() -> None:
    metadata = load_binary_dictionary("ru_RU").metadata
    assert metadata.encoding == "koi8-r"
    assert metadata.separator == "+"
    assert metadata.encoder == "SUFFIX"
    assert metadata.frequency_included is True
    assert metadata.support_run_on_words is True
    assert metadata.ignore_diacritics is False
    # Not declared in ru_RU.info, so the Morfologik defaults apply.
    assert metadata.convert_case is True
    assert metadata.ignore_all_uppercase is True
    assert metadata.ignore_camel_case is True
    assert metadata.ignore_numbers is True
    assert metadata.ignore_punctuation is True
    assert metadata.equivalent_chars == {}
    assert metadata.replacement_pairs["тс"] == ["ц"]
    assert metadata.replacement_pairs["е"] == ["ё", "я", "и"]
    assert metadata.replacement_pairs["тся"] == ["ться"]


def test_replacement_maps_split_by_target_length(ru_speller: Speller) -> None:
    # Targets of length 1 and 2 become any-to-one / any-to-two maps; longer
    # targets stay in replacementsTheRest and drive getAllReplacements().
    assert ru_speller._replacements_any_to_one["ё"] == ["е", "о", "йо"]
    assert ru_speller._replacements_any_to_two["нн"] == ["н"]
    assert ru_speller._replacements_the_rest == {"тся": ["ться"], "ться": ["тся"]}


def test_get_all_replacements_expands_only_long_pairs(ru_speller: Speller) -> None:
    assert ru_speller.get_all_replacements("учится", 0, 0) == ["учится", "учиться"]
    assert ru_speller.get_all_replacements("слово", 0, 0) == ["слово"]


def test_is_in_dictionary_and_frequency(ru_speller: Speller) -> None:
    assert ru_speller.is_in_dictionary("слово") is True
    assert ru_speller.is_in_dictionary("каждя") is False
    assert 0 <= ru_speller.get_frequency("слово") < FREQ_RANGES
    assert ru_speller.get_frequency("каждя") == 0


def test_is_misspelled_applies_dictionary_flags(ru_speller: Speller) -> None:
    assert ru_speller.is_misspelled("каждя") is True
    assert ru_speller.is_misspelled("каждая") is False
    # ignore-all-uppercase and ignore-numbers are on by default.
    assert ru_speller.is_misspelled("КАЖДЯ") is False
    assert ru_speller.is_misspelled("12345") is False
    assert ru_speller.is_misspelled("!") is False
    # convert-case accepts a capitalized form of a lowercase dictionary word.
    assert ru_speller.is_misspelled("Слово") is False
    # A word outside the koi8-r dictionary charset can never be found.
    assert ru_speller.is_misspelled("ко́т") is True


def test_find_replacement_candidates_are_ordered_by_weighted_distance(ru_speller: Speller) -> None:
    candidates = ru_speller.find_replacement_candidates("каждя")
    assert [c.word for c in candidates] == ["дождя", "кадя", "каждая", "вождя"]
    assert [c.distance for c in candidates] == sorted(c.distance for c in candidates)
    for candidate in candidates:
        expected = candidate.orig_distance * FREQ_RANGES + FREQ_RANGES - ru_speller.get_frequency(candidate.word) - 1
        assert candidate.distance == expected
    assert all(c.word != "каждя" for c in candidates)


def test_run_on_word_candidates(ru_speller: Speller) -> None:
    assert "ка ждя" in ru_speller.replace_run_on_words("каждя")
    assert ru_speller.replace_run_on_words("слово") == []


def test_edit_distance_bound_is_respected() -> None:
    dictionary = load_binary_dictionary("ru_RU")
    assert Speller(dictionary, 1).find_replacements("здраствуйти") == []
    assert "здравствуйте" in Speller(dictionary, 2).find_replacements("здраствуйти")


def test_case_helpers_follow_java_semantics(ru_speller: Speller) -> None:
    assert ru_speller.is_all_uppercase("СЛОВО") is True
    assert ru_speller.is_all_uppercase("Слово") is False
    assert ru_speller.is_mixed_case("СлОвО") is True
    assert ru_speller.is_mixed_case("Слово") is False
    assert ru_speller.is_not_capitalized_word("слово") is True
    assert ru_speller.is_not_capitalized_word("Слово") is False
    # Speller.isCamelCase requires an uppercase first char, a lowercase second
    # char, and at least one more uppercase letter later in the word.
    assert ru_speller.is_camel_case("СлОво") is True
    assert ru_speller.is_camel_case("Слово") is False
    assert ru_speller.is_camel_case("слово") is False


def test_apply_replacements_is_a_no_op_without_conversion_pairs() -> None:
    assert apply_replacements("слово", {}) == "слово"
    assert apply_replacements("aXbXc", {"X": "-"}) == "a-b-c"


def test_hmatrix_band_initialization() -> None:
    matrix = HMatrix(1, MAX_WORD_LENGTH)
    assert matrix.row_length == MAX_WORD_LENGTH + 2
    assert matrix.column_height == 5
    assert matrix.get(0, 0) == 0
    matrix.set(2, 3, 7)
    assert matrix.get(2, 3) == 7


def test_trie_fsa_matches_sorted_byte_sequences() -> None:
    fsa = TrieFSA([b"ab", b"abc", b"b"])
    from pylat_ru.morfologik.fsa import EXACT_MATCH, NO_MATCH, SEQUENCE_IS_A_PREFIX

    assert fsa.match(b"ab")[0] == EXACT_MATCH
    assert fsa.match(b"abc")[0] == EXACT_MATCH
    assert fsa.match(b"z")[0] == NO_MATCH
    assert fsa.match(b"")[0] == SEQUENCE_IS_A_PREFIX
    root = fsa.get_root_node()
    labels = []
    arc = fsa.get_first_arc(root)
    while arc:
        labels.append(fsa.get_arc_label(arc))
        arc = fsa.get_next_arc(arc)
    assert labels == sorted(labels)


def test_plain_text_dictionary_uses_utf8_bytes_with_binary_metadata() -> None:
    metadata = load_binary_dictionary("ru_RU").metadata
    dictionary = build_plain_text_dictionary([b"Facebook", b"Ford"], metadata)
    speller = Speller(dictionary, 1)
    # Upstream builds the runtime FSA from UTF-8 bytes while the metadata still
    # declares koi8-r, so only ASCII entries are reachable.  This asymmetry is
    # reproduced faithfully rather than corrected.
    assert speller.is_in_dictionary("Ford") is True
    cyrillic = build_plain_text_dictionary(["слово".encode("utf-8")], metadata)
    assert Speller(cyrillic, 1).is_in_dictionary("слово") is False


def test_multibyte_dictionary_encoding_is_refused() -> None:
    metadata = DictionaryMetadata.from_text(
        "fsa.dict.separator=+\nfsa.dict.encoding=utf-8\nfsa.dict.encoder=SUFFIX\n"
    )
    from pylat_ru.morfologik.errors import UnsupportedEncodingError

    with pytest.raises(UnsupportedEncodingError):
        Speller(build_plain_text_dictionary([b"a"], metadata), 1)
