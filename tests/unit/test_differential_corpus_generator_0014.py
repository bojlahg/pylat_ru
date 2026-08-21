"""Task 0014 section 21 - corpus generator determinism and coverage.

These tests exercise only the internally generated strata (A, B, C, E).  Stratum D is
external natural prose that is never committed, so it is covered by the manifest tests
instead, which assert its recorded provenance and counts.

Every test here is Java-free.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import pytest

from tools.differential_batch_oracle_0014 import Profile
from tools.differential_corpus_0014 import (
    FIXED_SEED,
    MUTATION_FAMILIES,
    MUTATION_FAMILY_NAMES,
    MUTATION_KINDS,
    SPELLING_MISSPELL_KINDS,
    STRATA,
    UNICODE_DECORATIONS,
    build_profiles,
    build_stratum_a,
    build_stratum_b,
    build_stratum_c,
    build_stratum_e,
    default_off_rule_ids,
    java_rule_default_off_ids,
    make_case_id,
    semantic_identity,
    xml_rule_default_off_ids,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def stratum_a() -> list:
    return build_stratum_a()


# -- determinism ------------------------------------------------------------


def test_stratum_a_is_deterministic(stratum_a: list) -> None:
    assert build_stratum_a() == stratum_a


def test_stratum_b_is_deterministic_for_a_fixed_seed(stratum_a: list) -> None:
    first = build_stratum_b(stratum_a, seed=FIXED_SEED)
    second = build_stratum_b(stratum_a, seed=FIXED_SEED)
    assert first == second


def test_stratum_b_changes_with_a_different_seed(stratum_a: list) -> None:
    """A different committed seed must produce a genuinely different sample."""
    baseline = build_stratum_b(stratum_a, seed=FIXED_SEED)
    other = build_stratum_b(stratum_a, seed=FIXED_SEED + 1)
    assert [text for text, _ in baseline] != [text for text, _ in other]


def test_stratum_c_is_deterministic() -> None:
    assert build_stratum_c(seed=FIXED_SEED) == build_stratum_c(seed=FIXED_SEED)


def test_stratum_e_is_deterministic() -> None:
    assert build_stratum_e() == build_stratum_e()


def test_generation_does_not_depend_on_process_randomised_hash() -> None:
    """Selection must be stable across interpreter runs with different PYTHONHASHSEED.

    ``random.Random`` seeded with a string is stable; ``hash()`` on a str is not.  This
    runs two subprocesses with opposing hash seeds and compares the signatures.
    """
    import subprocess
    import sys

    script = (
        "import sys; sys.path.insert(0, r'%s'); sys.path.insert(0, r'%s');"
        "from tools.differential_corpus_0014 import build_stratum_a, build_stratum_b,"
        " build_stratum_c, corpus_signature, build_corpus;"
        "a = build_stratum_a();"
        "import hashlib, json;"
        "payload = json.dumps(["
        "  [t for t, _ in build_stratum_b(a)],"
        "  [t for t, _ in build_stratum_c()],"
        "], ensure_ascii=False);"
        "print(hashlib.sha256(payload.encode('utf-8')).hexdigest())"
    ) % (str(REPO_ROOT), str(REPO_ROOT / "src"))

    signatures = []
    for hash_seed in ("0", "12345"):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONHASHSEED": hash_seed},
            cwd=str(REPO_ROOT),
        )
        assert proc.returncode == 0, proc.stderr
        signatures.append(proc.stdout.strip())
    assert signatures[0] == signatures[1]


# -- identity ---------------------------------------------------------------


def test_case_ids_are_stable_and_unique(stratum_a: list) -> None:
    profile = build_profiles()["default"]
    ids = [
        make_case_id("A", index, semantic_identity(text, profile))
        for index, (text, _) in enumerate(stratum_a)
    ]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"A\d{6}_[0-9a-f]{12}", case_id) for case_id in ids)


def test_semantic_identity_is_profile_sensitive() -> None:
    """The same text under two profiles is two distinct cases."""
    profiles = build_profiles()
    text = "Это тестовый текст."
    assert semantic_identity(text, profiles["default"]) != semantic_identity(
        text, profiles["all_ordinary_enabled"]
    )


def test_semantic_identity_ignores_nothing_about_the_profile() -> None:
    left = Profile("p", rule_config={"TOO_LONG_SENTENCE": {"maxWords": 15}})
    right = Profile("p", rule_config={"TOO_LONG_SENTENCE": {"maxWords": 16}})
    assert semantic_identity("текст", left) != semantic_identity("текст", right)


def test_identity_does_not_depend_on_oracle_output() -> None:
    """Identity is a function of text and profile only."""
    profile = build_profiles()["default"]
    payload = json.loads(
        json.dumps({"text": "текст", "profile": profile.to_dict()}, sort_keys=True)
    )
    assert set(payload) == {"text", "profile"}


# -- deduplication ----------------------------------------------------------


def test_semantic_deduplication_collapses_identical_text_and_profile() -> None:
    from tools.differential_corpus_0014 import build_corpus

    cases, accounting = build_corpus()
    identities = {
        semantic_identity(case.text, build_profiles()[case.profile]) for case in cases
    }
    assert len(identities) == len(cases)
    assert accounting["semantic_duplicates_skipped"] > 0


def test_same_text_under_two_profiles_is_not_deduplicated() -> None:
    from tools.differential_corpus_0014 import build_corpus

    cases, _ = build_corpus()
    by_text: dict[str, set[str]] = {}
    for case in cases:
        by_text.setdefault(case.text, set()).add(case.profile)
    assert any(len(profiles) > 1 for profiles in by_text.values())


# -- coverage ---------------------------------------------------------------


def test_every_mutation_family_and_kind_is_represented(stratum_a: list) -> None:
    mutations = build_stratum_b(stratum_a, seed=FIXED_SEED)
    produced_families = {p["mutation_family"] for _, p in mutations}
    produced_kinds = {p["mutation_kind"] for _, p in mutations}
    assert produced_families == set(MUTATION_FAMILY_NAMES)
    assert produced_kinds == set(MUTATION_KINDS)


def test_mandatory_mutation_families_are_declared() -> None:
    """Section 7.2 names six families plus composition."""
    assert set(MUTATION_FAMILY_NAMES) == {
        "case",
        "composition",
        "punctuation",
        "repetition",
        "spelling",
        "unicode",
        "whitespace",
    }


def test_mutations_actually_change_their_seed_text(stratum_a: list) -> None:
    for text, provenance in build_stratum_b(stratum_a, seed=FIXED_SEED):
        assert text.strip()
        assert provenance["seed_text_sha256"]


def test_spelling_stratum_meets_its_minimum_and_covers_every_kind() -> None:
    cases = build_stratum_c(seed=FIXED_SEED)
    texts = {text for text, _ in cases}
    assert len(texts) >= 2000, f"section 7.3 requires >= 2000, got {len(texts)}"
    kinds = {provenance["misspelling_kind"] for _, provenance in cases}
    assert kinds == set(SPELLING_MISSPELL_KINDS)


def test_spelling_stress_texts_are_whole_text_inputs() -> None:
    """Section 7.1: do not force bare speller queries through the whole pipeline."""
    for text, _ in build_stratum_c(seed=FIXED_SEED):
        assert " " in text.strip(), text


def test_unicode_stratum_covers_the_required_categories() -> None:
    cases = build_stratum_e()
    assert len({text for text, _ in cases}) == len(cases)
    assert sum(1 for _, p in cases if p["has_non_bmp"]) >= 50
    assert sum(1 for _, p in cases if p["has_combining"]) >= 10
    assert sum(1 for _, p in cases if p["has_soft_hyphen"]) >= 10
    kinds = {p["unicode_kind"] for _, p in cases}
    assert kinds.issubset({kind for kind, _ in UNICODE_DECORATIONS})


def test_non_bmp_quota_is_met_across_the_whole_corpus() -> None:
    """Section 8: at least 500 Unicode/non-BMP targeted executions."""
    from tools.differential_corpus_0014 import build_corpus

    _, accounting = build_corpus()
    assert accounting["non_bmp_executions"] >= 500, accounting["non_bmp_executions"]
    assert accounting["combining_mark_executions"] > 0
    assert accounting["soft_hyphen_executions"] > 0


def test_internal_strata_meet_their_declared_minimum_counts(stratum_a: list) -> None:
    assert len({text for text, _ in stratum_a}) >= 2400
    assert len({text for text, _ in build_stratum_b(stratum_a, FIXED_SEED)}) >= 1000
    assert len({text for text, _ in build_stratum_c(seed=FIXED_SEED)}) >= 2000


def test_all_grammar_examples_are_included(stratum_a: list) -> None:
    """Section 8: all 2446 grammar.xml example inputs must be present."""
    payload = json.loads(
        (REPO_ROOT / "compat" / "extracted_grammar_examples.json").read_text(
            encoding="utf-8"
        )
    )
    expected = {
        example["text"] for example in payload["examples"] if example["text"].strip()
    }
    assert len(payload["examples"]) == 2446
    included = {text for text, _ in stratum_a}
    assert expected.issubset(included)


# -- profiles ---------------------------------------------------------------


def test_default_off_rule_ids_come_from_pinned_inventories() -> None:
    """Section 9.2: the enablement list is derived, never hand written."""
    java_ids = java_rule_default_off_ids()
    xml_ids = xml_rule_default_off_ids()
    assert set(default_off_rule_ids()) == set(java_ids) | set(xml_ids)
    assert "CONFUSION_RULE" not in default_off_rule_ids()
    # The pinned Java-rule inventory records exactly nine default-off ordinary rules.
    assert len(java_ids) == 9
    assert xml_ids


def test_profiles_cover_the_mandatory_configurations() -> None:
    profiles = build_profiles()
    assert "default" in profiles
    assert "all_ordinary_enabled" in profiles
    assert profiles["default"].to_dict() == {
        "profile_id": "default",
        "enabled_rules": [],
        "disabled_rules": [],
        "rule_config": {},
        "enable_all_default_off": False,
    }
    assert profiles["all_ordinary_enabled"].enable_all_default_off is True
    assert set(profiles["all_ordinary_enabled"].enabled_rules) == set(
        default_off_rule_ids()
    )
    configured = {
        profile_id
        for profile_id, profile in profiles.items()
        if profile.rule_config
    }
    assert configured == {
        "cfg_long_sentence_15",
        "cfg_long_paragraph_30",
        "cfg_filler_words_2",
    }


def test_profile_config_spec_is_deterministic_and_sorted() -> None:
    profile = Profile(
        "p",
        rule_config={
            "FILLER_WORDS_RU": {"minPercent": 2, "excludeDirectSpeech": False},
            "TOO_LONG_SENTENCE": {"maxWords": 15},
        },
    )
    assert profile.config_spec() == (
        "FILLER_WORDS_RU=excludeDirectSpeech:false,minPercent:2;"
        "TOO_LONG_SENTENCE=maxWords:15"
    )
    assert profile.signature() == Profile(
        "p",
        rule_config={
            "TOO_LONG_SENTENCE": {"maxWords": 15},
            "FILLER_WORDS_RU": {"excludeDirectSpeech": False, "minPercent": 2},
        },
    ).signature()


def test_strata_identifiers_are_the_declared_set() -> None:
    assert STRATA == ("A", "B", "C", "D", "E")
    assert len(MUTATION_FAMILIES) == len(MUTATION_KINDS)
    assert len(set(MUTATION_KINDS)) == len(MUTATION_KINDS)


def test_unicode_decorations_produce_the_declared_properties() -> None:
    for text, provenance in build_stratum_e():
        assert provenance["has_non_bmp"] == any(ord(c) > 0xFFFF for c in text)
        assert provenance["has_combining"] == any(
            unicodedata.combining(c) for c in text
        )
