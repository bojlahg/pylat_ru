"""tests/upstream/test_unification_synthetic_oracle_parity.py

Differential test suite validating 100% parity between pylat_ru RussianGrammarEngine
and the pinned Java LanguageTool Oracle across all synthetic unification pattern matching fixture cases.
Asserts rule metadata, match counts, UTF-16 and Python codepoint offsets, pattern spans, messages, and suggestions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_unification_synthetic.json"
MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "compat" / "oracle_manifest.json"

REQUIRED_SYNTHETIC_UNIFICATION_FEATURES = {
    "uni_feature_number",
    "uni_feature_gender",
    "uni_feature_case",
    "uni_feature_animacy",
    "uni_multi_feature",
    "uni_explicit_types",
    "uni_negation",
    "uni_neutral_elements",
    "multiple_unify_scopes",
    "success_then_fail_candidate",
    "fail_then_success_candidate",
    "repeated_calls_isolation",
    "finite_skip_unify",
    "infinite_skip_unify",
    "min_zero_unify",
    "max_quantifiers_unify",
    "and_group_unify",
    "or_group_unify",
    "previous_next_exceptions_unify",
    "spacebefore_unify",
    "chunk_unify",
    "raw_pos_unify",
    "antipattern_unify",
    "marker_spans_unify",
    "match_references_unify",
    "controlled_multi_reading_filtering",
    "controlled_rejected_reading_isolation",
    "controlled_equivalence_intersection",
    "controlled_missing_equivalence_value",
    "uni_positive_match",
    "uni_no_match",
}


def utf16_offset_to_codepoint_offset(text: str, utf16_offset: int) -> int:
    """Convert a UTF-16 code unit offset to Unicode codepoint index."""
    u16_count = 0
    for cp_idx, char in enumerate(text):
        if u16_count >= utf16_offset:
            return cp_idx
        u16_count += 2 if ord(char) > 0xFFFF else 1
    return len(text)


def load_oracle_manifest() -> Dict[str, Any]:
    """Load the trusted oracle manifest."""
    if not MANIFEST_PATH.is_file():
        pytest.fail(f"Oracle manifest not found at {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_data():
    assert FIXTURE_PATH.is_file(), f"Missing fixture file: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def synthetic_engine(fixture_data):
    xml_content = fixture_data.get("synthetic_rules_xml", "")
    loader = GrammarLoader()
    rules = loader.load_from_string(xml_content)
    return RussianGrammarEngine(rules=rules, loader=loader)


def test_unification_synthetic_fixture_integrity(fixture_data):
    """Verify oracle synthetic unification fixture metadata against oracle_manifest.json."""
    assert fixture_data.get("schema_version") == "1.0.0"
    manifest = load_oracle_manifest()
    meta = fixture_data.get("metadata", {})

    assert meta.get("pinned_lt_version") == manifest.get("pinned_version")
    assert meta.get("pinned_lt_commit") == manifest.get("pinned_commit")
    assert meta.get("corpus_version") == "1.0.0"
    assert meta.get("generator_operation") == "tools/generate_oracle_unification_fixtures.py"

    oracle_build_id = meta.get("oracle_build_id")
    trusted_builds = {b["build_id"]: b for b in manifest.get("trusted_oracle_builds", [])}
    assert oracle_build_id in trusted_builds, f"Untrusted build_id: {oracle_build_id}"

    expected_sha = trusted_builds[oracle_build_id]["jar_sha256"]
    assert meta.get("oracle_jar_sha256") == expected_sha

    cases = fixture_data.get("cases", [])
    assert meta.get("cases_count") == len(cases)

    # Assert distinct case IDs
    case_ids = [c["id"] for c in cases]
    assert len(set(case_ids)) == len(case_ids), "Duplicate synthetic case IDs found"


def test_synthetic_unification_feature_coverage(fixture_data):
    """Assert 100% coverage of required synthetic unification feature families."""
    feat_cov = fixture_data.get("feature_coverage", {})
    covered_families = set(feat_cov.keys())
    missing_families = REQUIRED_SYNTHETIC_UNIFICATION_FEATURES - covered_families
    assert missing_families == set(), f"Missing synthetic feature families: {missing_families}"

    for feat, case_ids in feat_cov.items():
        assert len(case_ids) > 0, f"Feature family '{feat}' has no associated test case IDs"


def test_synthetic_unification_cases_count(fixture_data):
    """Verify minimum required test cases in synthetic unification fixture (>= 150 cases)."""
    cases = fixture_data.get("cases", [])
    assert len(cases) >= 150, f"Expected at least 150 test cases, found {len(cases)}"


def test_synthetic_unification_oracle_parity_all_cases(fixture_data, synthetic_engine):
    """Verify exact full parity (count, order, offsets, pattern spans, message, suggestions) for all synthetic unification cases."""
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()
    engine = synthetic_engine

    cases = fixture_data.get("cases", [])
    mismatches: List[str] = []

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        target_rule_id = case["full_rule_id"]
        oracle_res = case["oracle_result"]

        rule = engine.get_rule(target_rule_id)
        if rule is None:
            mismatches.append(f"[{case_id}] Rule not found in engine: {target_rule_id}")
            continue

        sent = disambiguator.disambiguate_text(text)
        sent.text = text
        chunker.chunk(sent)

        act_matches = engine.check_rule(sent, rule)
        exp_matches = oracle_res.get("matches", [])

        if len(act_matches) != oracle_res["matches_count"]:
            mismatches.append(
                f"[{case_id}] ({target_rule_id}) Match count mismatch: expected {oracle_res['matches_count']}, got {len(act_matches)} for text {text!r}"
            )
            continue

        for i, (act_m, exp_m) in enumerate(zip(act_matches, exp_matches)):
            prefix = f"[{case_id}] ({target_rule_id}) Match {i}"

            # 1. Full rule ID
            if act_m.full_rule_id != target_rule_id:
                mismatches.append(f"{prefix} Full rule ID mismatch: expected {target_rule_id}, got {act_m.full_rule_id}")

            # 2. UTF-16 error/marker offsets
            if act_m.from_pos_utf16 != exp_m["from_utf16"] or act_m.to_pos_utf16 != exp_m["to_utf16"]:
                mismatches.append(
                    f"{prefix} marker UTF-16 offset mismatch: expected ({exp_m['from_utf16']}, {exp_m['to_utf16']}), got ({act_m.from_pos_utf16}, {act_m.to_pos_utf16})"
                )

            # 3. UTF-16 pattern offsets
            if act_m.pattern_from_pos_utf16 != exp_m["pattern_from_utf16"] or act_m.pattern_to_pos_utf16 != exp_m["pattern_to_utf16"]:
                mismatches.append(
                    f"{prefix} pattern UTF-16 offset mismatch: expected ({exp_m['pattern_from_utf16']}, {exp_m['pattern_to_utf16']}), got ({act_m.pattern_from_pos_utf16}, {act_m.pattern_to_pos_utf16})"
                )

            # 4. Unicode codepoint marker offsets
            if act_m.from_pos != exp_m["expected_from_codepoint"] or act_m.to_pos != exp_m["expected_to_codepoint"]:
                mismatches.append(
                    f"{prefix} marker codepoint offset mismatch: expected ({exp_m['expected_from_codepoint']}, {exp_m['expected_to_codepoint']}), got ({act_m.from_pos}, {act_m.to_pos})"
                )

            # 5. Unicode codepoint pattern offsets
            if act_m.pattern_from_pos != exp_m["expected_pattern_from_codepoint"] or act_m.pattern_to_pos != exp_m["expected_pattern_to_codepoint"]:
                mismatches.append(
                    f"{prefix} pattern codepoint offset mismatch: expected ({exp_m['expected_pattern_from_codepoint']}, {exp_m['expected_pattern_to_codepoint']}), got ({act_m.pattern_from_pos}, {act_m.pattern_to_pos})"
                )

            # 6. Exact message
            if act_m.message != exp_m["message"]:
                mismatches.append(f"{prefix} Message mismatch: expected {exp_m['message']!r}, got {act_m.message!r}")

            # 7. Exact short message
            exp_short = exp_m.get("short_message") or None
            act_short = act_m.short_message or None
            if exp_short and act_short != exp_short:
                mismatches.append(f"{prefix} Short message mismatch: expected {exp_short!r}, got {act_short!r}")

            # 8. Exact suggestions including order and duplicates
            if act_m.suggestions != exp_m["suggestions"]:
                mismatches.append(f"{prefix} Suggestions mismatch: expected {exp_m['suggestions']!r}, got {act_m.suggestions!r}")

    assert not mismatches, f"Synthetic unification oracle parity failures ({len(mismatches)}):\n" + "\n".join(mismatches[:25])
