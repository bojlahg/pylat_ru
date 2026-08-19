"""tests/upstream/test_pattern_token_oracle_parity.py

Verifies 100% differential parity for PatternToken inflected semantics
between native Python CompiledPatternToken / CompiledTokenException and
the Java LanguageTool Oracle on committed fixture oracle_pattern_token_inflected.json.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from pylat_ru.analysis import AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.grammar.matcher import CompiledPatternToken, CompiledTokenException
from pylat_ru.grammar.model import PatternToken, PatternTokenException

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "oracle_pattern_token_inflected.json"
MANIFEST_PATH = REPO_ROOT / "compat" / "oracle_manifest.json"


def load_oracle_manifest() -> Dict[str, Any]:
    """Load the trusted oracle manifest."""
    if not MANIFEST_PATH.is_file():
        pytest.fail(f"Oracle manifest not found at {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pattern_token_oracle_fixture() -> Dict[str, Any]:
    assert FIXTURE_PATH.is_file(), f"Fixture missing: {FIXTURE_PATH}"
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_pattern_token_fixture_integrity(pattern_token_oracle_fixture: Dict[str, Any]):
    """Assert metadata integrity of committed PatternToken oracle fixture against oracle_manifest.json."""
    manifest = load_oracle_manifest()
    data = pattern_token_oracle_fixture
    assert data["schema_version"] == "1.0.0"
    meta = data["metadata"]

    assert meta.get("pinned_lt_version") == manifest.get("pinned_version")
    assert meta.get("pinned_lt_commit") == manifest.get("pinned_commit")

    oracle_build_id = meta.get("oracle_build_id")
    trusted_builds = {b["build_id"]: b for b in manifest.get("trusted_oracle_builds", [])}
    assert oracle_build_id in trusted_builds, f"Untrusted build_id: {oracle_build_id}"

    expected_sha = trusted_builds[oracle_build_id]["jar_sha256"]
    assert meta.get("oracle_jar_sha256") == expected_sha
    assert meta["cases_count"] == len(data["cases"])
    assert meta["cases_count"] == 6


def test_pattern_token_oracle_parity_all_cases(pattern_token_oracle_fixture: Dict[str, Any]):
    """Verify exact token-level match and exception parity against Java LT Oracle."""
    cases = pattern_token_oracle_fixture["cases"]

    for case in cases:
        case_id = case["id"]
        pat_info = case["pattern"]
        tok_info = case["token"]
        exp_oracle = case["oracle_result"]

        # Build Python PatternToken
        exceptions = []
        if pat_info.get("has_exception") and pat_info.get("exception"):
            exc_info = pat_info["exception"]
            exceptions.append(
                PatternTokenException(
                    text=exc_info.get("text"),
                    inflected=exc_info.get("inflected", False),
                    postag=exc_info.get("postag"),
                    postag_regexp=exc_info.get("postag_regexp", False),
                    case_sensitive=pat_info.get("case_sensitive", False),
                )
            )

        pt_model = PatternToken(
            text=pat_info.get("text"),
            inflected=pat_info.get("inflected", False),
            case_sensitive=pat_info.get("case_sensitive", False),
            regexp=pat_info.get("regexp", False),
            postag=pat_info.get("postag"),
            postag_regexp=pat_info.get("postag_regexp", False),
            exceptions=exceptions,
        )

        cpt = CompiledPatternToken(pt_model)

        # Build Python AnalyzedTokenReadings
        at = AnalyzedToken(
            token=tok_info["token"],
            pos_tag=tok_info["pos_tag"],
            lemma=tok_info["lemma"],
        )
        atr = AnalyzedTokenReadings(
            readings=[at],
            start_pos=0,
        )

        py_matched = cpt.matches_token_readings(atr)
        exp_match = exp_oracle["final_match"]

        assert py_matched == exp_match, (
            f"[{case_id}] {case['description']}: "
            f"Expected Java Oracle final_match={exp_match}, but Python got {py_matched} "
            f"for token={at} and pattern={pt_model}"
        )
