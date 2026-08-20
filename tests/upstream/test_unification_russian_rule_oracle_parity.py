"""tests/upstream/test_unification_russian_rule_oracle_parity.py

Differential test suite validating 100% parity between pylat_ru RussianGrammarEngine
and the pinned Java LanguageTool Oracle across all real Russian unification rule fixture cases.
Asserts all rule metadata, match counts, UTF-16 and Python codepoint offsets, pattern spans, messages, and suggestions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_unification_russian_rules.json"
MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "compat" / "oracle_manifest.json"


def utf16_offset_to_codepoint_offset(text: str, utf16_offset: int) -> int:
    """Convert a UTF-16 code unit offset to Unicode codepoint index."""
    u16_count = 0
    for cp_idx, char in enumerate(text):
        if u16_count >= utf16_offset:
            return cp_idx
        u16_count += 2 if ord(char) > 0xFFFF else 1
    return len(text)


def text_slice_from_utf16(text: str, from_u16: int, to_u16: int) -> str:
    """Slice text given UTF-16 code unit offsets."""
    from_cp = utf16_offset_to_codepoint_offset(text, from_u16)
    to_cp = utf16_offset_to_codepoint_offset(text, to_u16)
    return text[from_cp:to_cp]


def load_oracle_manifest() -> Dict[str, Any]:
    """Load the trusted oracle manifest."""
    if not MANIFEST_PATH.is_file():
        pytest.fail(f"Oracle manifest not found at {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_data():
    assert FIXTURE_PATH.is_file(), f"Missing fixture file: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_unification_russian_rules_fixture_integrity(fixture_data):
    """Verify oracle unification Russian rules fixture metadata against oracle_manifest.json."""
    assert fixture_data.get("schema_version") == "1.0.0"
    manifest = load_oracle_manifest()
    meta = fixture_data.get("metadata", {})

    assert meta.get("pinned_lt_version") == manifest.get("pinned_version")
    assert meta.get("pinned_lt_commit") == manifest.get("pinned_commit")
    assert meta.get("corpus_version") == "1.0.0"
    assert meta.get("generator_operation") == "tools/generate_oracle_unification_fixtures.py"

    oracle_build_id = meta.get("oracle_build_id")
    assert oracle_build_id == "lt_6.8_source_build_jdk17_stefan"
    trusted_builds = {b["build_id"]: b for b in manifest.get("trusted_oracle_builds", [])}
    assert oracle_build_id in trusted_builds, f"Untrusted build_id: {oracle_build_id}"

    expected_sha = trusted_builds[oracle_build_id]["jar_sha256"]
    assert expected_sha == "b88f235819adbc49f11988e232bc065b61740381f6f40bfa99dc502505390efc"
    assert meta.get("oracle_jar_sha256") == expected_sha

    cases = fixture_data.get("cases", [])
    assert meta.get("cases_count") == len(cases)
    assert meta.get("promoted_rules_count") == 24
    assert len(meta.get("promoted_full_rule_ids", [])) == 24

    # Assert all case IDs are unique and inputs non-empty
    case_ids = [c["id"] for c in cases]
    assert len(set(case_ids)) == len(case_ids)
    assert all(len(c.get("text", "")) > 0 for c in cases)


def test_unification_russian_rules_feature_coverage(fixture_data):
    """Verify that real Russian rule feature coverage metadata correctly maps actual rule usage."""
    feat_cov = fixture_data.get("feature_coverage", {})
    cases = fixture_data.get("cases", [])
    cases_by_id = {c["id"]: c for c in cases}

    assert len(feat_cov) > 0, "Real Russian rule feature coverage mapping is empty"

    for feat_key, feat_info in feat_cov.items():
        feat_name = feat_info["feature_name"]
        covered_rules = feat_info["covered_rule_ids"]
        covered_cases = feat_info["covered_case_ids"]

        assert len(covered_rules) > 0, f"No rules for {feat_key}"
        assert len(covered_cases) > 0, f"No cases for {feat_key}"

        # Assert every case ID in covered_cases actually uses this feature
        for cid in covered_cases:
            c = cases_by_id[cid]
            assert feat_name in c["rule_features"], f"Case {cid} does not actually use feature {feat_name}"


def test_unification_russian_rules_oracle_parity(fixture_data):
    """Verify exact full parity (count, order, offsets, pattern spans, message, suggestions) between pylat_ru and Java LT oracle."""
    engine = RussianGrammarEngine.get_instance()
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()

    cases = fixture_data.get("cases", [])
    failures: List[str] = []

    for case in cases:
        case_id = case["id"]
        full_rule_id = case["full_rule_id"]
        text = case["text"]
        oracle_res = case.get("oracle_result", {})
        oracle_matches = oracle_res.get("matches", [])

        sent = disambiguator.disambiguate_text(text)
        sent.text = text
        chunker.chunk(sent)

        py_matches = engine.check_rule(sent, full_rule_id)

        if len(py_matches) != len(oracle_matches):
            failures.append(
                f"[{case_id}][{full_rule_id}] Match count mismatch: expected {len(oracle_matches)}, got {len(py_matches)} on text: {text!r}"
            )
            continue

        for m_idx, (py_m, or_m) in enumerate(zip(py_matches, oracle_matches)):
            prefix = f"[{case_id}][{full_rule_id}][match_{m_idx}]"

            # 1. Full rule ID
            if py_m.full_rule_id != full_rule_id:
                failures.append(f"{prefix} Full rule ID mismatch: expected {full_rule_id}, got {py_m.full_rule_id}")

            # 2. UTF-16 error/marker span offsets
            if (py_m.from_pos_utf16, py_m.to_pos_utf16) != (or_m["from_utf16"], or_m["to_utf16"]):
                failures.append(
                    f"{prefix} UTF-16 marker offset mismatch: expected ({or_m['from_utf16']}, {or_m['to_utf16']}), got ({py_m.from_pos_utf16}, {py_m.to_pos_utf16})"
                )

            # 3. UTF-16 pattern span offsets
            if (py_m.pattern_from_pos_utf16, py_m.pattern_to_pos_utf16) != (or_m["pattern_from_utf16"], or_m["pattern_to_utf16"]):
                failures.append(
                    f"{prefix} UTF-16 pattern offset mismatch: expected ({or_m['pattern_from_utf16']}, {or_m['pattern_to_utf16']}), got ({py_m.pattern_from_pos_utf16}, {py_m.pattern_to_pos_utf16})"
                )

            # 4. Codepoint marker span offsets
            if (py_m.from_pos, py_m.to_pos) != (or_m["expected_from_codepoint"], or_m["expected_to_codepoint"]):
                failures.append(
                    f"{prefix} Codepoint marker offset mismatch: expected ({or_m['expected_from_codepoint']}, {or_m['expected_to_codepoint']}), got ({py_m.from_pos}, {py_m.to_pos})"
                )

            # 5. Codepoint pattern span offsets
            if (py_m.pattern_from_pos, py_m.pattern_to_pos) != (or_m["expected_pattern_from_codepoint"], or_m["expected_pattern_to_codepoint"]):
                failures.append(
                    f"{prefix} Codepoint pattern offset mismatch: expected ({or_m['expected_pattern_from_codepoint']}, {or_m['expected_pattern_to_codepoint']}), got ({py_m.pattern_from_pos}, {py_m.pattern_to_pos})"
                )

            # 6. Exact message
            if py_m.message != or_m["message"]:
                failures.append(f"{prefix} Message mismatch: expected {or_m['message']!r}, got {py_m.message!r}")

            # 7. Exact short message
            exp_short = or_m.get("short_message") or None
            act_short = py_m.short_message or None
            if exp_short and act_short != exp_short:
                failures.append(f"{prefix} Short message mismatch: expected {exp_short!r}, got {act_short!r}")

            # 8. Exact suggestions including order and duplicates
            if py_m.suggestions != or_m["suggestions"]:
                failures.append(f"{prefix} Suggestions mismatch: expected {or_m['suggestions']!r}, got {py_m.suggestions!r}")

    assert not failures, f"Oracle Russian unification rules parity failures ({len(failures)}):\n" + "\n".join(failures[:25])
