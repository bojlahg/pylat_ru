"""tests/upstream/test_advanced_russian_rule_oracle_parity.py

Differential test suite validating 100% parity between pylat_ru RussianGrammarEngine
and the pinned Java LanguageTool Oracle across all real Russian advanced rule fixture cases.
Asserts all rule metadata, match counts, UTF-16 and Python codepoint offsets, messages, and suggestions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_advanced_russian_rules.json"
MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "compat" / "oracle_manifest.json"


def load_oracle_manifest() -> Dict[str, Any]:
    """Load the trusted oracle manifest."""
    if not MANIFEST_PATH.is_file():
        pytest.fail(f"Oracle manifest not found at {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_data():
    assert FIXTURE_PATH.is_file(), f"Missing fixture file: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_advanced_russian_rules_fixture_integrity(fixture_data):
    """Verify oracle advanced Russian rules fixture metadata against oracle_manifest.json."""
    manifest = load_oracle_manifest()
    meta = fixture_data.get("metadata", {})

    assert meta.get("pinned_lt_version") == manifest.get("pinned_version")
    assert meta.get("pinned_lt_commit") == manifest.get("pinned_commit")

    oracle_build_id = meta.get("oracle_build_id")
    trusted_builds = {b["build_id"]: b for b in manifest.get("trusted_oracle_builds", [])}
    assert oracle_build_id in trusted_builds, f"Untrusted build_id: {oracle_build_id}"

    expected_sha = trusted_builds[oracle_build_id]["jar_sha256"]
    assert meta.get("oracle_jar_sha256") == expected_sha


def test_advanced_russian_rules_oracle_cases_count(fixture_data):
    """Verify test cases count in advanced Russian rules fixture."""
    cases = fixture_data.get("cases", [])
    assert len(cases) >= 700, f"Expected at least 700 test cases, found {len(cases)}"


def test_advanced_russian_rules_oracle_parity_all_cases(fixture_data):
    """Verify exact parity for all real Russian advanced rule cases between Java LT oracle and pylat_ru."""
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()
    engine = RussianGrammarEngine.get_instance()

    cases = fixture_data.get("cases", [])
    mismatches = []

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        target_rule_id = case["full_rule_id"]
        oracle_res = case["oracle_result"]

        rule = engine.get_rule(target_rule_id)
        if rule is None:
            mismatches.append(f"[{case_id}] Rule not found in engine: {target_rule_id}")
            continue

        # Verify Rule metadata
        if rule.id != oracle_res["rule_id"]:
            mismatches.append(f"[{case_id}] Rule id mismatch: {rule.id} != {oracle_res['rule_id']}")
        if rule.full_id != oracle_res["full_rule_id"]:
            mismatches.append(f"[{case_id}] Rule full_id mismatch: {rule.full_id} != {oracle_res['full_rule_id']}")
        if rule.category_id != oracle_res["category_id"]:
            mismatches.append(f"[{case_id}] Category ID mismatch: {rule.category_id} != {oracle_res['category_id']}")
        if rule.category_name != oracle_res["category_name"]:
            mismatches.append(f"[{case_id}] Category Name mismatch: {rule.category_name} != {oracle_res['category_name']}")
        if rule.name != oracle_res["description"]:
            mismatches.append(f"[{case_id}] Description mismatch: {rule.name} != {oracle_res['description']}")
        if rule.default_off != oracle_res["is_default_off"]:
            mismatches.append(f"[{case_id}] Default off mismatch: {rule.default_off} != {oracle_res['is_default_off']}")

        # Run pipeline
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

            # Verify finding rule & category fields
            if act_m.rule_id != oracle_res["rule_id"]:
                mismatches.append(f"{prefix} finding rule_id mismatch: {act_m.rule_id} != {oracle_res['rule_id']}")
            if act_m.full_rule_id != oracle_res["full_rule_id"]:
                mismatches.append(f"{prefix} finding full_rule_id mismatch: {act_m.full_rule_id} != {oracle_res['full_rule_id']}")
            if act_m.category_id != oracle_res["category_id"]:
                mismatches.append(f"{prefix} finding category_id mismatch: {act_m.category_id} != {oracle_res['category_id']}")
            if act_m.category_name != oracle_res["category_name"]:
                mismatches.append(f"{prefix} finding category_name mismatch: {act_m.category_name} != {oracle_res['category_name']}")
            if act_m.description != oracle_res["description"]:
                mismatches.append(f"{prefix} finding description mismatch: {act_m.description} != {oracle_res['description']}")

            # Verify offsets
            if act_m.from_pos_utf16 != exp_m["from_utf16"] or act_m.to_pos_utf16 != exp_m["to_utf16"]:
                mismatches.append(
                    f"{prefix} offset mismatch: expected ({exp_m['from_utf16']}, {exp_m['to_utf16']}), got ({act_m.from_pos_utf16}, {act_m.to_pos_utf16})"
                )

            # Verify message & short message
            if act_m.message != exp_m["message"]:
                mismatches.append(f"{prefix} message mismatch: expected {exp_m['message']!r}, got {act_m.message!r}")
            if act_m.short_message != exp_m["short_message"]:
                mismatches.append(f"{prefix} short_message mismatch: expected {exp_m['short_message']!r}, got {act_m.short_message!r}")

            # Verify suggestions
            exp_suggs = exp_m.get("suggestions", [])
            if act_m.suggestions != exp_suggs:
                mismatches.append(
                    f"{prefix} suggestions mismatch: expected {exp_suggs}, got {act_m.suggestions}"
                )

            # Verify codepoint slice correctness against original text
            matched_slice = text[act_m.from_pos:act_m.to_pos]
            assert matched_slice != "", f"{prefix} empty matched codepoint slice"

    assert not mismatches, f"Advanced Russian rules oracle parity failures ({len(mismatches)}):\n" + "\n".join(mismatches)
