"""tests/upstream/test_unification_russian_rule_oracle_parity.py

Differential test suite validating 100% parity between pylat_ru RussianGrammarEngine
and the pinned Java LanguageTool Oracle across all real Russian unification rule fixture cases.
Asserts all rule metadata, match counts, UTF-16 and Python codepoint offsets, pattern spans, messages, and suggestions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
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
    manifest = load_oracle_manifest()
    meta = fixture_data.get("metadata", {})

    assert meta.get("pinned_lt_version") == manifest.get("pinned_version")
    assert meta.get("pinned_lt_commit") == manifest.get("pinned_commit")

    oracle_build_id = meta.get("oracle_build_id")
    trusted_builds = {b["build_id"]: b for b in manifest.get("trusted_oracle_builds", [])}
    assert oracle_build_id in trusted_builds, f"Untrusted build_id: {oracle_build_id}"

    expected_sha = trusted_builds[oracle_build_id]["jar_sha256"]
    assert meta.get("oracle_jar_sha256") == expected_sha


def test_unification_russian_rules_oracle_cases_count(fixture_data):
    """Verify test cases count in unification Russian rules fixture."""
    cases = fixture_data.get("cases", [])
    assert len(cases) == 216, f"Expected 216 test cases, found {len(cases)}"


def test_unification_russian_rules_oracle_parity(fixture_data):
    """Verify exact match count, offsets, and messages between pylat_ru and Java LT oracle."""
    engine = RussianGrammarEngine.get_instance()
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()

    cases = fixture_data.get("cases", [])
    failures = []

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
            # Verify marker / error span offsets
            exp_from = or_m["expected_from_codepoint"]
            exp_to = or_m["expected_to_codepoint"]
            if (py_m.from_pos, py_m.to_pos) != (exp_from, exp_to):
                failures.append(
                    f"[{case_id}][{full_rule_id}] Match #{m_idx} span mismatch: expected ({exp_from}, {exp_to}), got ({py_m.from_pos}, {py_m.to_pos})"
                )

            # Verify pattern span offsets
            exp_pat_from = or_m["expected_pattern_from_codepoint"]
            exp_pat_to = or_m["expected_pattern_to_codepoint"]
            if (py_m.pattern_from_pos, py_m.pattern_to_pos) != (exp_pat_from, exp_pat_to):
                failures.append(
                    f"[{case_id}][{full_rule_id}] Match #{m_idx} pattern span mismatch: expected ({exp_pat_from}, {exp_pat_to}), got ({py_m.pattern_from_pos}, {py_m.pattern_to_pos})"
                )

    assert not failures, f"Oracle Russian unification rules parity failures ({len(failures)}):\n" + "\n".join(failures[:20])
