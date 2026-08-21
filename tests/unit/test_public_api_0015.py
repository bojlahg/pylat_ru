from __future__ import annotations

from dataclasses import MISSING, fields
import inspect
import json
from pathlib import Path
import re

import pylat_ru
from pylat_ru import LanguageToolRU, RuleMatch


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = json.loads((ROOT / "compat/public_api_0015.json").read_text(encoding="utf-8"))


def _simple_signature(callable_object: object) -> str:
    signature = inspect.signature(callable_object)
    parts = []
    for parameter in signature.parameters.values():
        item = parameter.name
        if parameter.default is not inspect.Parameter.empty:
            item += "=" + repr(parameter.default)
        parts.append(item)
    return "(" + ", ".join(parts) + ")"


def test_primary_public_api_snapshot() -> None:
    assert all(hasattr(pylat_ru, name) for name in SNAPSHOT["primary_public_symbols"])
    assert list(pylat_ru.__all__) == SNAPSHOT["all_exported_symbols"]
    assert _simple_signature(LanguageToolRU) == SNAPSHOT["language_tool_ru_init_signature"]
    assert _simple_signature(LanguageToolRU.check) == SNAPSHOT["language_tool_ru_check_signature"]


def test_rule_match_contract_snapshot() -> None:
    actual_fields = fields(RuleMatch)
    assert [field.name for field in actual_fields] == SNAPSHOT["rule_match_fields"]
    defaults = {}
    for field in actual_fields:
        value = "REQUIRED" if field.default is MISSING else field.default
        if isinstance(value, tuple):
            value = list(value)
        defaults[field.name] = value
    assert defaults == SNAPSHOT["rule_match_defaults"]


def test_versions_and_levels_cannot_drift() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    metadata_version = re.search(r'(?m)^version = "([^"]+)"$', pyproject)
    assert metadata_version is not None
    assert metadata_version.group(1) == pylat_ru.__version__ == SNAPSHOT["package_version"]
    assert pylat_ru.LEVEL_DEFAULT == SNAPSHOT["checking_levels"]["default"] == "DEFAULT"
    assert pylat_ru.LEVEL_PICKY == SNAPSHOT["checking_levels"]["picky"] == "PICKY"


def test_runtime_dependency_set_is_intentional() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dependencies = re.search(r'(?ms)^dependencies = \[\n(.*?)^\]$', pyproject)
    assert dependencies is not None
    assert re.findall(r'"([^"]+)"', dependencies.group(1)) == ["regex>=2024.5.15,<=2026.7.19"]
