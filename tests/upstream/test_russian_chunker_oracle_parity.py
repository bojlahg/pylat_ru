"""tests/upstream/test_russian_chunker_oracle_parity.py

Differential oracle parity test verifying RussianChunker against pinned LanguageTool 6.8 Java Oracle.
Checks all observable token fields for both pre_chunker and post_chunker states unconditionally.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator


FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "oracle_russian_chunker.json"
)

MANIFEST_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "compat"
    / "oracle_manifest.json"
)


def load_oracle_manifest() -> Dict[str, Any]:
    """Load the trusted oracle manifest."""
    if not MANIFEST_PATH.is_file():
        pytest.fail(f"Oracle manifest not found at {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_oracle_fixture() -> Dict[str, Any]:
    """Load the committed LanguageTool 6.8 chunker fixture."""
    if not FIXTURE_PATH.is_file():
        pytest.fail(f"Oracle chunker fixture not found at {FIXTURE_PATH}")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_chunker_fixture_integrity():
    """Verify oracle chunker fixture metadata against oracle_manifest.json."""
    manifest = load_oracle_manifest()
    fixture = load_oracle_fixture()

    meta = fixture.get("metadata", {})
    assert meta.get("pinned_lt_version") == manifest.get("pinned_version")
    assert meta.get("pinned_lt_commit") == manifest.get("pinned_commit")

    oracle_build_id = meta.get("oracle_build_id")
    trusted_builds = {b["build_id"]: b for b in manifest.get("trusted_oracle_builds", [])}
    assert oracle_build_id in trusted_builds, f"Untrusted build_id: {oracle_build_id}"

    expected_sha = trusted_builds[oracle_build_id]["jar_sha256"]
    assert meta.get("oracle_jar_sha256") == expected_sha


def test_chunker_oracle_cases_count():
    """Assert chunker fixture contains exactly 34 cases."""
    fixture = load_oracle_fixture()
    assert len(fixture["cases"]) == 34


def _assert_sentence_tokens_match_oracle_stage(
    actual_sentence: AnalyzedSentence,
    expected_stage_tokens: List[Dict[str, Any]],
    stage_name: str,
    case_id: str,
) -> None:
    actual_tokens = actual_sentence.get_tokens()

    assert len(actual_tokens) == len(expected_stage_tokens), (
        f"[{case_id}][{stage_name}] Token count mismatch: "
        f"actual {len(actual_tokens)} != oracle {len(expected_stage_tokens)}"
    )

    for i, (act, exp) in enumerate(zip(actual_tokens, expected_stage_tokens)):
        prefix = f"[{case_id}][{stage_name}][tok_{i}='{act.token}']"

        assert act.token == exp["token"], f"{prefix} token mismatch"
        assert act.start_pos == exp["start_pos_utf16"], f"{prefix} start_pos_utf16 mismatch"
        assert act.pos_fix == exp["pos_fix"], f"{prefix} pos_fix mismatch"
        assert act.is_whitespace() == exp["is_whitespace"], f"{prefix} is_whitespace mismatch"
        assert act.is_sentence_start == exp["is_sentence_start"], f"{prefix} is_sentence_start mismatch"
        assert act.is_sentence_end == exp["is_sentence_end"], f"{prefix} is_sentence_end mismatch"
        assert act.is_paragraph_end == exp["is_paragraph_end"], f"{prefix} is_paragraph_end mismatch"
        assert act.is_ignore_spelling == exp["is_ignore_spelling"], f"{prefix} is_ignore_spelling mismatch"

        assert act.clean_token == exp["clean_token"], f"{prefix} clean_token mismatch"
        assert act.whitespace_before == exp["whitespace_before"], f"{prefix} whitespace_before mismatch"

        act_chunks = act.chunk_tags or []
        assert act_chunks == exp["chunk_tags"], f"{prefix} chunk_tags mismatch: {act_chunks} != {exp['chunk_tags']}"

        actual_readings = [
            {"token": r.token, "lemma": r.lemma, "pos_tag": r.pos_tag}
            for r in act.readings
        ]
        assert actual_readings == exp["readings"], f"{prefix} readings mismatch"


def test_chunker_oracle_parity_all_cases():
    """Run all chunker fixture cases and assert 100% exact parity for both pre and post chunker stages."""
    fixture = load_oracle_fixture()
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()

    for item in fixture["cases"]:
        case_id = item["id"]
        text = item["text"]
        expected_stages = item["stages"]

        # Stage 1: Pre-chunker (post-disambiguation)
        sentence = disambiguator.disambiguate_text(text)
        _assert_sentence_tokens_match_oracle_stage(
            actual_sentence=sentence,
            expected_stage_tokens=expected_stages["pre_chunker"],
            stage_name="pre_chunker",
            case_id=case_id,
        )

        # Stage 2: Post-chunker
        chunker.chunk(sentence)
        _assert_sentence_tokens_match_oracle_stage(
            actual_sentence=sentence,
            expected_stage_tokens=expected_stages["post_chunker"],
            stage_name="post_chunker",
            case_id=case_id,
        )


def test_synthetic_chunker_boundary_cases():
    """Direct assertions on synthetic boundary cases."""
    chunker = RussianChunker()
    disambiguator = RussianHybridDisambiguator.get_instance()

    # 1. Pre-existing unrelated chunk tag preservation
    sent = disambiguator.disambiguate_text("Студент шел в университет.")
    # Assign custom tag to token 1
    tok1 = sent.tokens[1]
    tok1.chunk_tags.append("PRE_EXISTING_TAG")
    chunker.chunk(sent)
    assert "PRE_EXISTING_TAG" in tok1.chunk_tags

    # 2. Overwrite conflict: name sequence has overwrite=True removing FILTER_TAGS
    sent2 = disambiguator.disambiguate_text("Иванов Иван Иванович встретил Петра.")
    tok_ivan = sent2.tokens[1]
    tok_ivan.chunk_tags.append("VP")
    chunker.chunk(sent2)
    assert "VP" not in tok_ivan.chunk_tags
    assert "B-NP" in tok_ivan.chunk_tags

    # 3. Explicit MayMissingYO exclusion readings preservation
    sent3 = disambiguator.disambiguate_text("Все пошло не так.")
    chunker.chunk(sent3)
    assert len(sent3.tokens[1].readings) >= 1
