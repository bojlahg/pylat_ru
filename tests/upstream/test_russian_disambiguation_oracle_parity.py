"""Differential oracle parity tests comparing pylat_ru against pinned LanguageTool 6.8 Java Oracle."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedTokenReadings
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.disambiguation.multiwords import MultiWordChunker
from pylat_ru.sentence_analyzer import RussianSentenceAnalyzer


FIXTURE_PATH = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "oracle_russian_disambiguation.json"
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
    """Load the committed LanguageTool 6.8 disambiguation fixture."""
    if not FIXTURE_PATH.is_file():
        pytest.fail(f"Oracle disambiguation fixture not found at {FIXTURE_PATH}")
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def assert_sentence_matches_oracle_stage(
    actual_sentence: AnalyzedSentence,
    expected_stage_tokens: List[Dict[str, Any]],
    stage_name: str,
    case_id: str,
) -> None:
    """Assert exact structural match between an AnalyzedSentence and an oracle stage snapshot."""
    actual_tokens = actual_sentence.get_tokens()

    assert len(actual_tokens) == len(expected_stage_tokens), (
        f"[{case_id}][{stage_name}] Token count mismatch: "
        f"actual {len(actual_tokens)} != oracle {len(expected_stage_tokens)}"
    )

    for i, (act, exp) in enumerate(zip(actual_tokens, expected_stage_tokens)):
        prefix = f"[{case_id}][{stage_name}][tok_{i}='{act.token}']"

        # 1. token surface
        assert act.token == exp["token"], f"{prefix} token mismatch: '{act.token}' != '{exp['token']}'"

        # 2. start_pos_utf16
        assert act.start_pos == exp["start_pos_utf16"], (
            f"{prefix} start_pos mismatch: {act.start_pos} != {exp['start_pos_utf16']}"
        )

        # 3. pos_fix
        assert act.pos_fix == exp["pos_fix"], f"{prefix} pos_fix mismatch: {act.pos_fix} != {exp['pos_fix']}"

        # 4. is_whitespace
        assert act.is_whitespace() == exp["is_whitespace"], (
            f"{prefix} is_whitespace mismatch: {act.is_whitespace()} != {exp['is_whitespace']}"
        )

        # 5. is_sentence_start
        assert act.is_sentence_start == exp["is_sentence_start"], (
            f"{prefix} is_sentence_start mismatch: {act.is_sentence_start} != {exp['is_sentence_start']}"
        )

        # 6. is_sentence_end
        assert act.is_sentence_end == exp["is_sentence_end"], (
            f"{prefix} is_sentence_end mismatch: {act.is_sentence_end} != {exp['is_sentence_end']}"
        )

        # 7. is_paragraph_end
        assert act.is_paragraph_end == exp["is_paragraph_end"], (
            f"{prefix} is_paragraph_end mismatch: {act.is_paragraph_end} != {exp['is_paragraph_end']}"
        )

        # 8. is_ignore_spelling
        assert act.is_ignore_spelling == exp["is_ignore_spelling"], (
            f"{prefix} is_ignore_spelling mismatch: {act.is_ignore_spelling} != {exp['is_ignore_spelling']}"
        )

        # 9. clean_token (including None / fallback)
        assert act.clean_token == exp["clean_token"], (
            f"{prefix} clean_token mismatch: {act.clean_token} != {exp['clean_token']}"
        )

        # 10. whitespace_before (including None / exact string)
        assert act.whitespace_before == exp["whitespace_before"], (
            f"{prefix} whitespace_before mismatch: {act.whitespace_before!r} != {exp['whitespace_before']!r}"
        )

        # 11. chunk_tags (including empty lists)
        assert act.chunk_tags == exp["chunk_tags"], (
            f"{prefix} chunk_tags mismatch: {act.chunk_tags} != {exp['chunk_tags']}"
        )

        # 12. readings (count and every reading in exact sequence)
        exp_readings = exp["readings"]
        act_readings = act.readings

        assert len(act_readings) == len(exp_readings), (
            f"{prefix} readings count mismatch: {len(act_readings)} != {len(exp_readings)}\n"
            f"  Actual:   {[str(r) for r in act_readings]}\n"
            f"  Expected: {exp_readings}"
        )

        for r_idx, (ar, er) in enumerate(zip(act_readings, exp_readings)):
            r_prefix = f"{prefix}[reading_{r_idx}]"
            assert ar.token == er["token"], f"{r_prefix} reading token mismatch: '{ar.token}' != '{er['token']}'"
            assert ar.lemma == er["lemma"], f"{r_prefix} reading lemma mismatch: '{ar.lemma}' != '{er['lemma']}'"
            assert ar.pos_tag == er["pos_tag"], f"{r_prefix} reading pos_tag mismatch: '{ar.pos_tag}' != '{er['pos_tag']}'"


@pytest.fixture(scope="module")
def manifest_data() -> Dict[str, Any]:
    return load_oracle_manifest()


@pytest.fixture(scope="module")
def fixture_data() -> Dict[str, Any]:
    return load_oracle_fixture()


@pytest.fixture(scope="module")
def analyzer() -> RussianSentenceAnalyzer:
    return RussianSentenceAnalyzer.get_instance()


@pytest.fixture(scope="module")
def multiword_chunker() -> MultiWordChunker:
    return MultiWordChunker.get_instance("ru/multiwords.txt")


@pytest.fixture(scope="module")
def hybrid_disambiguator() -> RussianHybridDisambiguator:
    return RussianHybridDisambiguator.get_instance()


class TestRussianDisambiguationOracleParity:
    """Differential parity test suite against LanguageTool 6.8 Java oracle fixture."""

    def test_fixture_integrity(
        self, fixture_data: Dict[str, Any], manifest_data: Dict[str, Any]
    ) -> None:
        """Verify oracle fixture metadata and bind to trusted manifest provenance."""
        assert fixture_data["schema_version"] == "1.0.0"
        assert fixture_data["metadata"]["pinned_lt_version"] == manifest_data["pinned_version"]
        assert fixture_data["metadata"]["pinned_lt_commit"] == manifest_data["pinned_commit"]
        trusted_shas = set(manifest_data.get("trusted_sha256_set", [manifest_data["oracle_sha256"]]))
        assert fixture_data["metadata"]["oracle_jar_sha256"] in trusted_shas
        cases = fixture_data["cases"]
        assert len(cases) == 40

    def test_oracle_cases_parity(
        self,
        fixture_data: Dict[str, Any],
        analyzer: RussianSentenceAnalyzer,
        multiword_chunker: MultiWordChunker,
        hybrid_disambiguator: RussianHybridDisambiguator,
    ) -> None:
        """Run all test cases through all 3 stages and assert exact differential parity against Java LT."""
        for case in fixture_data["cases"]:
            case_id = case["id"]
            text = case["text"]
            stages = case["stages"]

            # Stage 1: Raw sentence analysis
            raw_actual = analyzer.analyze_raw(text)
            assert_sentence_matches_oracle_stage(
                raw_actual, stages["raw"], "raw", case_id
            )

            # Stage 2: MultiWordChunker
            raw_for_mw = analyzer.analyze_raw(text)
            mw_actual = multiword_chunker.disambiguate(raw_for_mw)
            assert_sentence_matches_oracle_stage(
                mw_actual, stages["multiword"], "multiword", case_id
            )

            # Stage 3: Full RussianHybridDisambiguator
            fin_actual = hybrid_disambiguator.disambiguate_text(text)
            assert_sentence_matches_oracle_stage(
                fin_actual, stages["disambiguated"], "disambiguated", case_id
            )
