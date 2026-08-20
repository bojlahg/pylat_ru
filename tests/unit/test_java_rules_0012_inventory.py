"""Independent inventory, resource, and Java-oracle integrity proofs for Task 0012."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIN = "e807fcde6a6506191e1470744d2345da28c26be6"
FIXTURES = (
    ROOT / "tests/fixtures/oracle_java_rules_0012_spelling.json",
    ROOT / "tests/fixtures/oracle_java_rules_0012_rules.json",
    ROOT / "tests/fixtures/oracle_java_rules_0012_filter.json",
    ROOT / "tests/fixtures/oracle_java_rules_0012_combined.json",
)
TASK_0012_RULE_CLASSES = {
    "MorfologikRussianSpellerRule",
    "MorfologikRussianYOSpellerRule",
    "RussianCompoundRule",
    "RussianSimpleReplaceRule",
    "RussianSimpleWordRepeatRule",
    "RussianWordCoherencyRule",
    "RussianWordRepeatRule",
    "RussianWordRootRepeatRule",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signature(case: dict) -> str:
    keys = (
        "execution_mode", "rule_class", "rule_id", "text", "explicitly_enabled",
        "explicitly_enabled_rules", "explicitly_disabled_rules", "config", "raw_rule_ids",
    )
    payload = {
        key: case.get(
            key,
            [] if key in ("raw_rule_ids", "explicitly_enabled_rules", "explicitly_disabled_rules") else "",
        )
        for key in keys
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_java_rules_registration_inventory_is_complete_and_source_bound() -> None:
    data = json.loads((ROOT / "compat/russian_java_rules_inventory.json").read_text(encoding="utf-8"))
    assert data["pinned_lt_commit"] == PIN
    assert data["accounting"] == {
        "relevant_total": 23,
        "implemented_total": 23,
        "implemented_0011": 15,
        "implemented_0012": 8,
        "deferred_ordinary": 0,
        "generic_implemented": 10,
        "generic_total": 10,
        "russian_specific_implemented": 13,
        "russian_specific_total": 13,
        "language_model_total": 1,
        "language_model_implemented": 0,
    }
    assert len(data["rules"]) == 23
    assert [rule["registration_order"] for rule in data["rules"]] == list(range(23))
    assert len({rule["rule_class"] for rule in data["rules"]}) == 23
    assert sum(rule["classification"] == "TASK_0011" for rule in data["rules"]) == 15
    assert sum(rule["classification"] == "TASK_0012" for rule in data["rules"]) == 8
    assert {r["rule_class"] for r in data["rules"] if r["classification"] == "TASK_0012"} == TASK_0012_RULE_CLASSES
    assert all(rule["compatibility_status"].startswith("NATIVE_") for rule in data["rules"])
    for rule in data["rules"]:
        source = ROOT / "third_party/languagetool" / rule["source_file"]
        assert source.is_file()
        assert _sha(source) == rule["source_sha256"]
    assert data["language_model_rules"][0]["classification"] == "LANGUAGE_MODEL_DEFERRED"


def test_effective_priorities_and_default_states_match_pinned_registration() -> None:
    data = json.loads((ROOT / "compat/russian_java_rules_inventory.json").read_text(encoding="utf-8"))
    rules = {rule["rule_id"]: rule for rule in data["rules"]}

    assert rules["RU_COMPOUNDS"]["effective_priority"] == 11
    assert rules["RU_COMPOUNDS"]["priority_binding_status"] == "BOUND"
    # Russian.java's override keys for these four rules never match the real IDs.
    for rule_id, target in (
        ("MORFOLOGIK_RULE_RU_RU", "MORFOLOGIC_RULE_RU_RU"),
        ("MORFOLOGIK_RULE_RU_RU_YO", "MORFOLOGIC_RULE_RU_RU_YO"),
        ("RU_SIMPLE_REPLACE", "RUSSIAN_SIMPLE_REPLACE_RULE"),
        ("RU_WORD_ROOT_REPEAT", "Word_root_repeat"),
    ):
        assert rules[rule_id]["configured_priority_target"] == target
        assert rules[rule_id]["priority_binding_status"] == "ORPHAN_OVERRIDE_ID"
        assert rules[rule_id]["effective_priority"] == 0

    default_off = {rule_id for rule_id, rule in rules.items() if rule["default_off"]}
    assert {
        "MORFOLOGIK_RULE_RU_RU_YO", "RU_WORD_REPEAT", "RU_WORD_ROOT_REPEAT",
    } <= default_off
    assert "MORFOLOGIK_RULE_RU_RU" not in default_off
    assert "RU_COMPOUNDS" not in default_off
    assert "RU_SIMPLE_REPLACE" not in default_off
    assert "WORD_REPEAT_RULE" not in default_off
    assert "RU_WORD_COHERENCY" not in default_off


def test_task_0012_oracle_manifest_raw_byte_bindings() -> None:
    manifest = json.loads((ROOT / "compat/oracle_manifest.json").read_text(encoding="utf-8"))
    assert manifest["pinned_commit"] == PIN
    assert manifest["default_build_id"] == "lt_6.8_source_build_jdk17_stefan"
    bindings = {item["path"]: item for item in manifest["fixture_bindings"]}
    for path in FIXTURES:
        binding = bindings[path.relative_to(ROOT).as_posix()]
        assert binding["size_bytes"] == len(path.read_bytes())
        assert binding["sha256"] == _sha(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert binding["case_count"] == len(payload["cases"])
        assert binding["oracle_build_id"] == payload["metadata"]["oracle_build_id"]


def test_task_0012_oracle_case_semantics_and_coverage() -> None:
    cases = []
    for path in FIXTURES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["metadata"]["pinned_lt_commit"] == PIN
        assert payload["metadata"]["oracle_generated"] is True
        assert payload["metadata"]["task"] == "0012"
        cases.extend(payload["cases"])

    assert len({case["id"] for case in cases}) == len(cases)
    signatures = [_signature(case) for case in cases]
    assert all(sig == case["semantic_signature"] for sig, case in zip(signatures, cases))
    assert len(signatures) == len(set(signatures)), (
        "duplicate semantic oracle queries must not be disguised by case IDs"
    )

    for case in cases:
        coverage = set(case["coverage"])
        assert not {"positive", "negative"} <= coverage, f"{case['id']}: contradictory labels"
        if case["execution_mode"] == "direct_speller":
            expected = case["expected"]
            if "positive" in coverage:
                assert expected["misspelled"] is True, case["id"]
            if "negative" in coverage:
                assert expected["misspelled"] is False, case["id"]
            if "several_suggestions" in coverage:
                assert len(expected["suggestions"]) >= 2, case["id"]
            if "no_suggestions" in coverage:
                assert expected["suggestions"] == [], case["id"]
            assert case["finding_count"] == (1 if expected["misspelled"] else 0)
            continue
        if "positive" in coverage:
            assert case["finding_count"] > 0, f"{case['id']}: positive case has no Java finding"
        if "negative" in coverage:
            assert case["finding_count"] == 0, f"{case['id']}: negative case has Java findings"
        if coverage.intersection({"multi_finding", "multiple_findings"}):
            assert case["finding_count"] > 1, f"{case['id']}: multiple-finding label is false"
        assert case["finding_count"] == len(case["expected"])
        if case["execution_mode"] == "single_rule":
            assert all(
                match["rule_id"] == case["rule_id"].split("[")[0] for match in case["expected"]
            ), case["id"]

    single_cases = [case for case in cases if case["execution_mode"] == "single_rule"]
    rule_classes = {
        case["rule_class"] for case in single_cases if case["rule_class"] in TASK_0012_RULE_CLASSES
    }
    assert rule_classes == TASK_0012_RULE_CLASSES
    for rule_class in TASK_0012_RULE_CLASSES:
        rule_cases = [case for case in single_cases if case["rule_class"] == rule_class]
        assert any("positive" in c["coverage"] and c["finding_count"] > 0 for c in rule_cases), rule_class
        assert any("negative" in c["coverage"] and c["finding_count"] == 0 for c in rule_cases), rule_class

    direct = [case for case in cases if case["execution_mode"] == "direct_speller"]
    assert {case["rule_id"] for case in direct} == {
        "MORFOLOGIK_RULE_RU_RU", "MORFOLOGIK_RULE_RU_RU_YO",
    }
    assert any(case["expected"]["misspelled"] for case in direct)
    assert any(not case["expected"]["misspelled"] for case in direct)
    assert any(len(case["expected"]["suggestions"]) > 1 for case in direct)
    assert any(case["expected"]["misspelled"] and not case["expected"]["suggestions"] for case in direct)

    combined = [case for case in cases if case["execution_mode"] == "combined_pipeline"]
    assert combined
    assert any("non_bmp" in case["coverage"] and case["expected"] for case in combined)
    assert any(case["explicitly_enabled_rules"] for case in combined)
    assert all(b"\r\n" not in path.read_bytes() for path in FIXTURES)


def test_task_0012_runtime_resource_copies_are_exact_pinned_bytes() -> None:
    module = "languagetool-language-modules/ru/src/main/resources/org/languagetool"
    core = "languagetool-core/src/main/resources/org/languagetool"
    pairs = (
        ("ru/hunspell/ru_RU.dict", f"{module}/resource/ru/hunspell/ru_RU.dict"),
        ("ru/hunspell/ru_RU.info", f"{module}/resource/ru/hunspell/ru_RU.info"),
        ("ru/hunspell/ru_RU_yo.dict", f"{module}/resource/ru/hunspell/ru_RU_yo.dict"),
        ("ru/hunspell/ru_RU_yo.info", f"{module}/resource/ru/hunspell/ru_RU_yo.info"),
        ("ru/hunspell/spelling.txt", f"{module}/resource/ru/hunspell/spelling.txt"),
        ("ru/hunspell/ignore.txt", f"{module}/resource/ru/hunspell/ignore.txt"),
        ("ru/hunspell/prohibit.txt", f"{module}/resource/ru/hunspell/prohibit.txt"),
        ("ru/compounds.txt", f"{module}/resource/ru/compounds.txt"),
        ("rules/ru/replace.txt", f"{module}/rules/ru/replace.txt"),
        ("rules/ru/coherency.txt", f"{module}/rules/ru/coherency.txt"),
        ("rules/ru/wordrootrep.txt", f"{module}/rules/ru/wordrootrep.txt"),
        ("spelling_global.txt", f"{core}/resource/spelling_global.txt"),
    )
    upstream_meta = json.loads(
        (ROOT / "third_party/languagetool/UPSTREAM.json").read_text(encoding="utf-8")
    )["files"]
    for runtime_rel, upstream_rel in pairs:
        runtime = ROOT / "src/pylat_ru/resources" / runtime_rel
        vendored = ROOT / "third_party/languagetool" / upstream_rel
        assert runtime.is_file(), runtime
        assert _sha(runtime) == _sha(vendored), runtime_rel
        assert upstream_meta[upstream_rel]["sha256"] == _sha(vendored), upstream_rel
        assert upstream_meta[upstream_rel]["size"] == vendored.stat().st_size, upstream_rel
