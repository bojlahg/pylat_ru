from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pylat_ru import LanguageToolRU
from pylat_ru.spelling import get_default_spelling_rule
from tools.benchmark_0015 import INPUTS, SUITE_VERSION


ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_inputs_are_committed_and_deterministic() -> None:
    baseline = json.loads((ROOT / "compat/performance_baseline_0015.json").read_text(encoding="utf-8"))
    assert baseline["benchmark_suite_version"] == SUITE_VERSION
    for name, text in INPUTS.items():
        assert baseline["inputs"][name] == {
            "code_points": len(text), "utf8_bytes": len(text.encode("utf-8")),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        }


def test_expensive_spelling_resources_are_reused_and_cache_is_bounded() -> None:
    first = get_default_spelling_rule(); second = get_default_spelling_rule()
    assert first is second
    tool = LanguageToolRU()
    rule = tool.java_rules_engine.get_rule("MORFOLOGIK_RULE_RU_RU")
    for index in range(25):
        tool.check(f"несуществующаяопечатка{index}.")
    assert rule.speller._speller1 is not None
    assert len(rule.speller._speller1._default_suggestion_cache) <= 2000
