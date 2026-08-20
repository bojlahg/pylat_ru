"""Unit tests for package foundation, imports, metadata, and production boundaries."""

import pytest
import pylat_ru
from pylat_ru import LanguageToolRU, RuleMatch


def test_package_metadata():
    """Verify package exposes expected version and public symbols."""
    assert hasattr(pylat_ru, "__version__")
    assert isinstance(pylat_ru.__version__, str)
    assert len(pylat_ru.__version__) > 0
    assert "LanguageToolRU" in pylat_ru.__all__
    assert "RuleMatch" in pylat_ru.__all__


def test_rule_match_dataclass():
    """Verify RuleMatch dataclass structure and immutability."""
    match = RuleMatch(
        rule_id="TEST_RULE",
        category_id="TEST_CAT",
        message="Test message",
        offset=5,
        length=4,
        replacements=["replacement"],
        short_message="Short msg",
    )
    assert match.rule_id == "TEST_RULE"
    assert match.category_id == "TEST_CAT"
    assert match.message == "Test message"
    assert match.offset == 5
    assert match.length == 4
    assert match.replacements == ["replacement"]
    assert match.short_message == "Short msg"
    assert match.source == "pylat_ru"

    with pytest.raises(AttributeError):
        match.rule_id = "CHANGED"  # type: ignore


def test_language_tool_ru_native_check_pipeline():
    """Verify the public API executes the native Russian rule pipeline."""
    tool = LanguageToolRU(disabled_rules=["WHITESPACE_RULE"])
    assert "WHITESPACE_RULE" in tool.disabled_rules
    assert not any(m.rule_id == "WHITESPACE_RULE" for m in tool.check("Текст  для проверки."))
    enabled = LanguageToolRU(enabled_rules=["FILLER_WORDS_RU"])
    assert any(m.rule_id == "FILLER_WORDS_RU" for m in enabled.check("ах слово"))


def test_no_java_or_dev_oracle_imported_by_default():
    """Verify production import in clean process does not pull in dev oracle or Java tools."""
    import subprocess
    import sys

    code = (
        "import sys, pylat_ru; "
        "assert 'tools' not in sys.modules; "
        "assert 'tools.differential_lt' not in sys.modules; "
        "assert 'tools.upstream_inventory' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"Clean import failed: {result.stderr}"
