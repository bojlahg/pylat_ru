"""Unit tests for differential test oracle boundary and comparison schemas."""

import json
import os
from pathlib import Path
import pytest

from tools.differential_lt import (
    DEFAULT_ORACLE_MANIFEST_PATH,
    LOOMCHILD_VERSION,
    PINNED_LT_COMMIT,
    PINNED_LT_VERSION,
    DifferentialComparisonResult,
    Finding,
    JavaLanguageToolOracle,
    compare_findings,
    generate_tokenization_fixtures,
    validate_oracle_manifest,
)


def test_finding_dataclass():
    """Verify Finding dataclass structure."""
    f = Finding(
        rule_id="RU_SPELL",
        category_id="TYPOS",
        message="Возможная ошибка",
        offset=0,
        length=5,
        suggestions=["слово"],
        source="java_lt",
    )
    assert f.rule_id == "RU_SPELL"
    assert f.category_id == "TYPOS"
    assert f.offset == 0
    assert f.length == 5
    assert f.suggestions == ["слово"]


def test_compare_findings_exact_match():
    """Verify comparison logic when findings match exactly."""
    f1 = Finding(
        rule_id="RULE_1",
        category_id="CAT_1",
        message="msg",
        offset=2,
        length=4,
        suggestions=["corr"],
        source="java_lt",
    )
    f2 = Finding(
        rule_id="RULE_1",
        category_id="CAT_1",
        message="msg",
        offset=2,
        length=4,
        suggestions=["corr"],
        source="pylat_ru",
    )

    res = compare_findings("Text with error", [f1], [f2])
    assert res.is_exact_match is True
    assert res.finding_count_match is True
    assert res.matching_rule_ids == ["RULE_1"]
    assert res.missing_in_pylat == []
    assert res.extra_in_pylat == []
    assert res.span_matches == 1
    assert res.suggestion_matches == 1

    d = res.to_dict()
    assert d["is_exact_match"] is True


def test_compare_findings_mismatch():
    """Verify comparison logic with discrepancies."""
    f_java = Finding(
        rule_id="JAVA_ONLY_RULE",
        category_id="CAT_1",
        message="msg",
        offset=0,
        length=3,
        suggestions=["a"],
        source="java_lt",
    )
    f_pylat = Finding(
        rule_id="PYLAT_ONLY_RULE",
        category_id="CAT_1",
        message="msg",
        offset=5,
        length=3,
        suggestions=["b"],
        source="pylat_ru",
    )

    res = compare_findings("Text with error", [f_java], [f_pylat])
    assert res.is_exact_match is False
    assert res.finding_count_match is True
    assert res.missing_in_pylat == ["JAVA_ONLY_RULE"]
    assert res.extra_in_pylat == ["PYLAT_ONLY_RULE"]
    assert res.span_matches == 0


def test_oracle_isolation_and_error_handling(tmp_path: Path):
    """Verify oracle can be instantiated without Java and raises cleanly when not configured."""
    oracle = JavaLanguageToolOracle(cache_dir=tmp_path)
    assert isinstance(oracle.is_java_available(), bool)
    assert oracle.is_oracle_configured() is False

    # When jar is missing, check() should raise informative RuntimeError
    with pytest.raises(RuntimeError) as exc_info:
        oracle.check("Текст")
    assert "not found" in str(exc_info.value) or "Java runtime" in str(exc_info.value)

    # When jar is missing, validate_oracle() raises RuntimeError
    with pytest.raises(RuntimeError) as exc_info2:
        oracle.validate_oracle()
    assert "not found" in str(exc_info2.value) or "Java runtime" in str(exc_info2.value)

    # Refuse fixture generation when oracle identity cannot be proven
    with pytest.raises(RuntimeError):
        generate_tokenization_fixtures(oracle, tmp_path)


def test_oracle_manifest_structure_and_sha_mismatch(tmp_path: Path):
    """Verify oracle manifest bindings and SHA-256 mismatch rejection."""
    assert DEFAULT_ORACLE_MANIFEST_PATH.is_file(), f"Missing {DEFAULT_ORACLE_MANIFEST_PATH}"
    manifest_data = validate_oracle_manifest(DEFAULT_ORACLE_MANIFEST_PATH)
    assert manifest_data.get("pinned_version") == PINNED_LT_VERSION
    assert manifest_data.get("pinned_commit") == PINNED_LT_COMMIT
    assert manifest_data.get("loomchild_version") == LOOMCHILD_VERSION
    assert manifest_data.get("jar_name") == "languagetool-commandline.jar"
    assert "oracle_sha256" in manifest_data

    # Fake jar with wrong SHA-256
    fake_jar = tmp_path / "languagetool-commandline.jar"
    fake_jar.write_text("fake jar content", encoding="utf-8")

    oracle_fake = JavaLanguageToolOracle(jar_path=fake_jar, manifest_path=DEFAULT_ORACLE_MANIFEST_PATH)
    if oracle_fake.is_java_available():
        with pytest.raises(RuntimeError, match="Oracle JAR SHA-256 mismatch"):
            oracle_fake.validate_oracle()


def test_oracle_manifest_missing_fails_closed(tmp_path: Path):
    """Verify validate_oracle() fails closed when manifest is missing and no override given."""
    missing_manifest = tmp_path / "non_existent_manifest.json"
    fake_jar = tmp_path / "languagetool-commandline.jar"
    fake_jar.write_text("dummy jar", encoding="utf-8")

    oracle = JavaLanguageToolOracle(jar_path=fake_jar, manifest_path=missing_manifest)
    if oracle.is_java_available():
        with pytest.raises(RuntimeError, match="manifest file not found"):
            oracle.validate_oracle()


def test_oracle_manifest_malformed_json(tmp_path: Path):
    """Verify validate_oracle_manifest fails cleanly on malformed JSON."""
    bad_manifest = tmp_path / "bad_manifest.json"
    bad_manifest.write_text("{broken json", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Malformed oracle manifest"):
        validate_oracle_manifest(bad_manifest)


def test_oracle_manifest_validation_negative_cases(tmp_path: Path):
    """Verify validate_oracle_manifest validates required fields, versions, and hex SHA-256."""
    valid_data = {
        "schema_version": "1.0.0",
        "pinned_version": PINNED_LT_VERSION,
        "pinned_commit": PINNED_LT_COMMIT,
        "loomchild_version": LOOMCHILD_VERSION,
        "jar_name": "languagetool-commandline.jar",
        "oracle_sha256": "4b63897b7b15d03bb639912752174dc0e090df4a78465d648cebcad5a4e3fa37",
    }

    def write_manifest(data: dict) -> Path:
        p = tmp_path / f"m_{len(list(tmp_path.iterdir()))}.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    # Missing key
    with pytest.raises(RuntimeError, match="missing required keys"):
        bad_data = {k: v for k, v in valid_data.items() if k != "oracle_sha256"}
        validate_oracle_manifest(write_manifest(bad_data))

    # Wrong version
    with pytest.raises(RuntimeError, match="pinned_version mismatch"):
        validate_oracle_manifest(write_manifest({**valid_data, "pinned_version": "6.7"}))

    # Wrong commit
    with pytest.raises(RuntimeError, match="pinned_commit mismatch"):
        validate_oracle_manifest(write_manifest({**valid_data, "pinned_commit": "wrong_commit"}))

    # Invalid SHA format (not 64 hex chars)
    with pytest.raises(RuntimeError, match="valid 64-char hex SHA-256 string"):
        validate_oracle_manifest(write_manifest({**valid_data, "oracle_sha256": "short_hash"}))


def test_oracle_sha_env_and_argument_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify expected_sha256 argument and PYLAT_ORACLE_SHA256 environment overrides manifest."""
    fake_jar = tmp_path / "languagetool-commandline.jar"
    fake_jar.write_text("sample jar content", encoding="utf-8")

    oracle = JavaLanguageToolOracle(jar_path=fake_jar, manifest_path=tmp_path / "missing.json")

    # Invalid override format raises immediately
    if oracle.is_java_available():
        with pytest.raises(RuntimeError, match="Invalid expected_sha256 format"):
            oracle.validate_oracle(expected_sha256="not_a_valid_sha")

        monkeypatch.setenv("PYLAT_ORACLE_SHA256", "invalid_env_sha")
        with pytest.raises(RuntimeError, match="Invalid PYLAT_ORACLE_SHA256"):
            oracle.validate_oracle()
