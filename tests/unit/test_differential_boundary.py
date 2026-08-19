"""Unit tests for differential test oracle boundary and comparison schemas."""

import pytest
from pathlib import Path

from tools.differential_lt import (
    DifferentialComparisonResult,
    Finding,
    JavaLanguageToolOracle,
    compare_findings,
    generate_tokenization_fixtures,
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
