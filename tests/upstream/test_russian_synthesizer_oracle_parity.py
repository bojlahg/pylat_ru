"""tests/upstream/test_russian_synthesizer_oracle_parity.py

Compares Python RussianSynthesizer output against committed Java LanguageTool v6.8 oracle fixture,
with strict manifest and build record integrity validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
import pytest

from pylat_ru.analysis import AnalyzedToken
from pylat_ru.synthesis import RussianSynthesizer

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "oracle_russian_synthesizer_sample.json"
MANIFEST_PATH = REPO_ROOT / "compat" / "oracle_manifest.json"


@pytest.fixture(scope="module")
def manifest_data() -> Dict[str, Any]:
    """Load trusted oracle manifest."""
    assert MANIFEST_PATH.is_file(), f"Missing oracle manifest at {MANIFEST_PATH}"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_data() -> Dict[str, Any]:
    """Load committed LanguageTool 6.8 synthesizer oracle fixture."""
    assert FIXTURE_PATH.is_file(), f"Missing oracle fixture at {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


class TestRussianSynthesizerOracleParity:
    """Differential parity test suite against LanguageTool 6.8 Java oracle fixture."""

    def test_fixture_integrity(
        self, fixture_data: Dict[str, Any], manifest_data: Dict[str, Any]
    ) -> None:
        """Verify oracle fixture metadata and bind to exact trusted build record in manifest."""
        assert fixture_data["schema_version"] == "1.0.0"
        meta = fixture_data["metadata"]
        build_id = meta.get("oracle_build_id")
        assert build_id is not None, "Missing oracle_build_id in fixture metadata"

        build_map = {b["build_id"]: b for b in manifest_data["trusted_oracle_builds"]}
        assert build_id in build_map, f"Build ID '{build_id}' not found in trusted manifest builds"
        build = build_map[build_id]

        assert meta["pinned_lt_version"] == manifest_data["pinned_version"] == build["pinned_version"]
        assert meta["pinned_lt_commit"] == manifest_data["pinned_commit"] == build["pinned_commit"]
        assert meta["oracle_jar_sha256"] == build["jar_sha256"]
        queries = fixture_data["queries"]
        assert len(queries) == 43

    def test_oracle_cases_parity(self, fixture_data: Dict[str, Any]) -> None:
        """Assert 100% exact parity on all queries in oracle_russian_synthesizer_sample.json."""
        synth = RussianSynthesizer.get_instance()
        queries = fixture_data.get("queries", [])
        assert len(queries) > 0

        mismatches = []
        for q in queries:
            qid = q["id"]
            token_str = q.get("token", "")
            lemma_val = q.get("lemma")
            pos_tag = q["pos_tag"]
            is_regex = q.get("pos_tag_is_regex", False)
            expected_forms = q["expected_forms"]

            tok = AnalyzedToken(token=token_str, lemma=lemma_val, pos_tag="DUMMY")
            actual_forms = synth.synthesize(tok, pos_tag, pos_tag_is_regex=is_regex)

            if actual_forms != expected_forms:
                mismatches.append(
                    f"Query {qid} ({token_str}|lemma={lemma_val!r}|{pos_tag}, is_regex={is_regex}): "
                    f"expected {expected_forms}, got {actual_forms}"
                )

        assert not mismatches, "Synthesizer oracle parity mismatches:\n" + "\n".join(mismatches)
