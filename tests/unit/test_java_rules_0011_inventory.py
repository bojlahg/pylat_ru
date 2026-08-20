"""Independent inventory and Java-oracle integrity proofs for Task 0011."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PIN = "e807fcde6a6506191e1470744d2345da28c26be6"
FIXTURES = (
    ROOT / "tests/fixtures/oracle_java_rules_0011_synthetic.json",
    ROOT / "tests/fixtures/oracle_java_rules_0011_russian.json",
    ROOT / "tests/fixtures/oracle_java_rules_0011_combined.json",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _signature(case: dict) -> str:
    payload = {key: case.get(key, []) if key == "raw_rule_ids" else case[key] for key in ("execution_mode", "rule_class", "rule_id", "text", "explicitly_enabled", "explicitly_enabled_rules", "explicitly_disabled_rules", "config", "raw_rule_ids")}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def test_java_rules_registration_inventory_is_source_bound() -> None:
    path = ROOT / "compat/russian_java_rules_inventory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["pinned_lt_commit"] == PIN
    assert data["accounting"] == {
        "relevant_total": 23,
        "implemented_0011": 15,
        "deferred_0012": 8,
        "generic_implemented": 10,
        "generic_total": 10,
        "russian_specific_implemented": 5,
        "russian_specific_total": 13,
        "language_model_total": 1,
        "language_model_implemented": 0,
    }
    assert len(data["rules"]) == 23
    assert [rule["registration_order"] for rule in data["rules"]] == list(range(23))
    assert len({rule["rule_class"] for rule in data["rules"]}) == 23
    assert sum(rule["classification"] == "TASK_0011" for rule in data["rules"]) == 15
    assert sum(rule["classification"] == "TASK_0012" for rule in data["rules"]) == 8
    for rule in data["rules"]:
        source = ROOT / "third_party/languagetool" / rule["source_file"]
        assert source.is_file()
        assert _sha(source) == rule["source_sha256"]
    assert data["language_model_rules"][0]["classification"] == "LANGUAGE_MODEL_DEFERRED"


def test_task_0011_oracle_manifest_raw_byte_bindings() -> None:
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


def test_task_0011_oracle_case_semantics_and_coverage() -> None:
    cases = []
    for path in FIXTURES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["metadata"]["pinned_lt_commit"] == PIN
        assert payload["metadata"]["oracle_generated"] is True
        cases.extend(payload["cases"])
    assert len({case["id"] for case in cases}) == len(cases)
    signatures = [_signature(case) for case in cases]
    assert all(signature == case["semantic_signature"] for signature, case in zip(signatures, cases))
    assert len(signatures) == len(set(signatures)), "duplicate semantic oracle queries must not be disguised by case IDs"
    single_cases = [case for case in cases if case["execution_mode"] == "single_rule"]
    for case in single_cases:
        coverage = set(case["coverage"])
        assert not {"positive", "negative"} <= coverage, f"{case['id']}: contradictory result labels"
        if "positive" in coverage:
            assert case["finding_count"] > 0, f"{case['id']}: positive case has no Java finding"
        if "negative" in coverage:
            assert case["finding_count"] == 0, f"{case['id']}: negative case has Java findings"
        if coverage.intersection({"multi_finding", "multiple_findings"}):
            assert case["finding_count"] > 1, f"{case['id']}: multiple-finding label is false"
    classes = {case["rule_class"] for case in single_cases}
    assert len(classes) == 15
    for rule_class in classes:
        rule_cases = [case for case in single_cases if case["rule_class"] == rule_class]
        assert any("positive" in case["coverage"] and case["finding_count"] > 0 for case in rule_cases)
        assert any("negative" in case["coverage"] and case["finding_count"] == 0 for case in rule_cases)
        assert all(all(match["rule_id"] == case["rule_id"] for match in case["expected"]) for case in rule_cases)
    assert any(case["finding_count"] > 1 for case in cases)
    assert any("non_bmp" in case["coverage"] and case["expected"] for case in cases)
    assert any("picky" in case["coverage"] and case.get("pre_overlap_expected") for case in cases)
    assert all(case["finding_count"] == len(case["expected"]) for case in cases)
    assert all(b"\r\n" not in path.read_bytes() for path in FIXTURES)


def test_runtime_resource_copies_are_exact_pinned_bytes() -> None:
    pairs = (
        ("compounds.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/compounds.txt"),
        ("specific_case.txt", "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/specific_case.txt"),
    )
    for runtime_name, upstream_rel in pairs:
        assert _sha(ROOT / "src/pylat_ru/resources/ru" / runtime_name) == _sha(ROOT / "third_party/languagetool" / upstream_rel)
