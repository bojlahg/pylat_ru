"""tests/upstream/test_advanced_pattern_oracle_parity.py

Differential test suite validating 100% parity between pylat_ru RussianGrammarEngine
and the pinned Java LanguageTool Oracle across advanced pattern matching fixture cases.
Asserts all rule metadata, match counts, UTF-16 and Python codepoint offsets, pattern spans, messages, and suggestions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple
import pytest

from pylat_ru.analysis import AnalyzedSentence, AnalyzedToken, AnalyzedTokenReadings
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.loader import GrammarLoader

FIXTURE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "oracle_advanced_pattern_matching.json"
MANIFEST_PATH = Path(__file__).resolve().parent.parent.parent / "compat" / "oracle_manifest.json"

REQUIRED_SYNTHETIC_FEATURE_FAMILIES = {
    "skip_finite",
    "skip_unbounded",
    "skip_with_exception",
    "min_zero",
    "min_one",
    "max_two",
    "max_three",
    "max_unbounded",
    "min_zero_max_two",
    "repeated_any_token",
    "spacebefore_yes",
    "spacebefore_no",
    "exception_spacebefore_yes",
    "exception_spacebefore_no",
    "exception_scope_current",
    "exception_scope_previous",
    "exception_scope_next",
    "chunk_literal",
    "chunk_regex",
    "chunk_multiple",
    "chunk_none",
    "and_cross_reading",
    "and_negative",
    "or_branch_expansion",
    "phrase_expansion",
    "phrase_containing_or",
    "phrase_match_numbering",
    "marker_at_phrase_ref",
    "skip_plus_min_max",
    "marker_with_skipped_tokens",
    "marker_with_omitted_optional",
    "marker_with_repeated_tokens",
    "non_bmp_in_skipped",
    "non_bmp_in_marker",
    "raw_pos_stream_diff",
    "token_match_ref_0_indexed",
    "include_skipped_all",
    "include_skipped_following",
    "case_conversion_alllower",
    "case_conversion_allupper",
    "case_conversion_firstupper",
    "regexp_replace_captures",
    "postag_replace_synthesis",
    "rule_with_max_filter",
}


def utf16_offset_to_codepoint_offset(text: str, utf16_offset: int) -> int:
    """Convert a UTF-16 code unit offset to Unicode codepoint index."""
    u16_count = 0
    for cp_idx, char in enumerate(text):
        if u16_count >= utf16_offset:
            return cp_idx
        u16_count += 2 if ord(char) > 0xFFFF else 1
    return len(text)


def text_slice_from_utf16(text: str, from_u16: int, to_u16: int) -> str:
    """Slice text given UTF-16 code unit offsets."""
    from_cp = utf16_offset_to_codepoint_offset(text, from_u16)
    to_cp = utf16_offset_to_codepoint_offset(text, to_u16)
    return text[from_cp:to_cp]


def load_oracle_manifest() -> Dict[str, Any]:
    """Load the trusted oracle manifest."""
    if not MANIFEST_PATH.is_file():
        pytest.fail(f"Oracle manifest not found at {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_data():
    assert FIXTURE_PATH.is_file(), f"Missing fixture file: {FIXTURE_PATH}"
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def synthetic_engine(fixture_data):
    xml_content = fixture_data.get("synthetic_rules_xml", "")
    assert xml_content, "Missing synthetic_rules_xml in fixture"
    loader = GrammarLoader()
    rules = loader.load_from_string(xml_content)
    return RussianGrammarEngine(rules=rules, loader=loader)


def prepare_synthetic_sentence(
    raw_text: str,
    disambiguator: RussianHybridDisambiguator,
    chunker: RussianChunker,
) -> Tuple[AnalyzedSentence, str]:
    """Parse injection annotations from raw text and construct AnalyzedSentence."""
    clean_text = raw_text
    injected_chunks: Dict[int, List[str]] = {}
    injected_readings: Dict[int, List[AnalyzedToken]] = {}
    injected_pre_disambig: Dict[int, List[AnalyzedToken]] = {}

    while clean_text.startswith("||"):
        end_idx = clean_text.find("||", 2)
        if end_idx == -1:
            break
        tag = clean_text[2:end_idx]
        clean_text = clean_text[end_idx + 2:]
        if tag.startswith("INJECT_CHUNKS:"):
            body = tag[len("INJECT_CHUNKS:"):]
            for item in body.split(";"):
                if not item:
                    continue
                tok_idx_str, ctags_str = item.split("=", 1)
                injected_chunks[int(tok_idx_str)] = [ct for ct in ctags_str.split(",") if ct]
        elif tag.startswith("INJECT_READINGS:"):
            body = tag[len("INJECT_READINGS:"):]
            for item in body.split(";"):
                if not item:
                    continue
                tok_idx_str, rlist_str = item.split("=", 1)
                rlist = []
                for rd in rlist_str.split(","):
                    if not rd:
                        continue
                    parts = rd.split("/", 2)
                    t_str = parts[0]
                    l_str = None if parts[1] == "null" else parts[1]
                    p_str = None if parts[2] == "null" else parts[2]
                    rlist.append(AnalyzedToken(t_str, l_str, p_str))
                injected_readings[int(tok_idx_str)] = rlist
        elif tag.startswith("INJECT_PRE_DISAMBIG:"):
            body = tag[len("INJECT_PRE_DISAMBIG:"):]
            for item in body.split(";"):
                if not item:
                    continue
                tok_idx_str, rlist_str = item.split("=", 1)
                rlist = []
                for rd in rlist_str.split(","):
                    if not rd:
                        continue
                    parts = rd.split("/", 2)
                    t_str = parts[0]
                    l_str = None if parts[1] == "null" else parts[1]
                    p_str = None if parts[2] == "null" else parts[2]
                    rlist.append(AnalyzedToken(t_str, l_str, p_str))
                injected_pre_disambig[int(tok_idx_str)] = rlist

    sent = disambiguator.disambiguate_text(clean_text)
    sent.text = clean_text
    chunker.chunk(sent)

    if injected_chunks:
        for idx, ctags in injected_chunks.items():
            if 0 <= idx < len(sent.tokens):
                sent.tokens[idx].chunk_tags = ctags

    if injected_readings:
        for idx, rlist in injected_readings.items():
            if 0 <= idx < len(sent.tokens):
                sent.tokens[idx].readings = list(rlist)

    if injected_pre_disambig:
        pre_tokens = list(sent.tokens)
        for idx, rlist in injected_pre_disambig.items():
            if 0 <= idx < len(pre_tokens):
                atr_copy = AnalyzedTokenReadings(
                    readings=list(rlist),
                    whitespace_before=sent.tokens[idx].whitespace_before,
                    start_pos=sent.tokens[idx].start_pos,
                    is_sentence_start=sent.tokens[idx].is_sentence_start,
                    is_sentence_end=sent.tokens[idx].is_sentence_end,
                )
                pre_tokens[idx] = atr_copy
        sent.pre_disambig_tokens = pre_tokens

    return sent, clean_text


def test_advanced_pattern_fixture_integrity(fixture_data):
    """Verify oracle advanced pattern fixture metadata against oracle_manifest.json."""
    manifest = load_oracle_manifest()
    meta = fixture_data.get("metadata", {})

    assert meta.get("pinned_lt_version") == manifest.get("pinned_version")
    assert meta.get("pinned_lt_commit") == manifest.get("pinned_commit")

    oracle_build_id = meta.get("oracle_build_id")
    trusted_builds = {b["build_id"]: b for b in manifest.get("trusted_oracle_builds", [])}
    assert oracle_build_id in trusted_builds, f"Untrusted build_id: {oracle_build_id}"

    expected_sha = trusted_builds[oracle_build_id]["jar_sha256"]
    assert meta.get("oracle_jar_sha256") == expected_sha


def test_synthetic_feature_coverage(fixture_data):
    """Assert 100% coverage of required synthetic feature families."""
    feat_cov = fixture_data.get("feature_coverage", {})
    covered_families = set(feat_cov.keys())
    missing_families = REQUIRED_SYNTHETIC_FEATURE_FAMILIES - covered_families
    assert missing_families == set(), f"Missing synthetic feature families: {missing_families}"

    for feat, case_ids in feat_cov.items():
        assert len(case_ids) > 0, f"Feature family '{feat}' has no associated test case IDs"


def test_advanced_pattern_oracle_cases_count(fixture_data):
    """Verify minimum required test cases in advanced pattern fixture (>= 100 cases)."""
    cases = fixture_data.get("cases", [])
    assert len(cases) >= 100, f"Expected at least 100 test cases, found {len(cases)}"


def test_advanced_pattern_oracle_parity_all_cases(fixture_data, synthetic_engine):
    """Verify exact parity for all advanced pattern rule cases between Java LT oracle and pylat_ru."""
    disambiguator = RussianHybridDisambiguator.get_instance()
    chunker = RussianChunker()
    engine = synthetic_engine

    cases = fixture_data.get("cases", [])
    mismatches = []

    for case in cases:
        case_id = case["id"]
        raw_text = case["text"]
        target_rule_id = case["full_rule_id"]
        oracle_res = case["oracle_result"]

        rule = engine.get_rule(target_rule_id)
        if rule is None:
            mismatches.append(f"[{case_id}] Rule not found in engine: {target_rule_id}")
            continue

        # Verify Rule metadata
        if rule.id != oracle_res["rule_id"]:
            mismatches.append(f"[{case_id}] Rule id mismatch: {rule.id} != {oracle_res['rule_id']}")
        if rule.full_id != oracle_res["full_rule_id"]:
            mismatches.append(f"[{case_id}] Rule full_id mismatch: {rule.full_id} != {oracle_res['full_rule_id']}")
        if rule.category_id != oracle_res["category_id"]:
            mismatches.append(f"[{case_id}] Category ID mismatch: {rule.category_id} != {oracle_res['category_id']}")
        if rule.category_name != oracle_res["category_name"]:
            mismatches.append(f"[{case_id}] Category Name mismatch: {rule.category_name} != {oracle_res['category_name']}")
        if rule.name != oracle_res["description"]:
            mismatches.append(f"[{case_id}] Description mismatch: {rule.name} != {oracle_res['description']}")
        if rule.default_off != oracle_res["is_default_off"]:
            mismatches.append(f"[{case_id}] Default off mismatch: {rule.default_off} != {oracle_res['is_default_off']}")

        # Run pipeline with injection handling
        sent, clean_text = prepare_synthetic_sentence(raw_text, disambiguator, chunker)

        act_matches = engine.check_rule(sent, rule)
        exp_matches = oracle_res.get("matches", [])

        if len(act_matches) != oracle_res["matches_count"]:
            mismatches.append(
                f"[{case_id}] ({target_rule_id}) Match count mismatch: expected {oracle_res['matches_count']}, got {len(act_matches)} for text {clean_text!r}"
            )
            continue

        for i, (act_m, exp_m) in enumerate(zip(act_matches, exp_matches)):
            prefix = f"[{case_id}] ({target_rule_id}) Match {i}"

            # Verify finding rule & category fields
            if act_m.rule_id != oracle_res["rule_id"]:
                mismatches.append(f"{prefix} finding rule_id mismatch: {act_m.rule_id} != {oracle_res['rule_id']}")
            if act_m.full_rule_id != oracle_res["full_rule_id"]:
                mismatches.append(f"{prefix} finding full_rule_id mismatch: {act_m.full_rule_id} != {oracle_res['full_rule_id']}")
            if act_m.category_id != oracle_res["category_id"]:
                mismatches.append(f"{prefix} finding category_id mismatch: {act_m.category_id} != {oracle_res['category_id']}")
            if act_m.category_name != oracle_res["category_name"]:
                mismatches.append(f"{prefix} finding category_name mismatch: {act_m.category_name} != {oracle_res['category_name']}")
            if act_m.description != oracle_res["description"]:
                mismatches.append(f"{prefix} finding description mismatch: {act_m.description} != {oracle_res['description']}")

            # Verify UTF-16 error/marker and full pattern offsets
            if act_m.from_pos_utf16 != exp_m["from_utf16"] or act_m.to_pos_utf16 != exp_m["to_utf16"]:
                mismatches.append(
                    f"{prefix} marker UTF-16 offset mismatch: expected ({exp_m['from_utf16']}, {exp_m['to_utf16']}), got ({act_m.from_pos_utf16}, {act_m.to_pos_utf16})"
                )
            if act_m.pattern_from_pos_utf16 != exp_m["pattern_from_utf16"] or act_m.pattern_to_pos_utf16 != exp_m["pattern_to_utf16"]:
                mismatches.append(
                    f"{prefix} pattern UTF-16 offset mismatch: expected ({exp_m['pattern_from_utf16']}, {exp_m['pattern_to_utf16']}), got ({act_m.pattern_from_pos_utf16}, {act_m.pattern_to_pos_utf16})"
                )

            # Verify Unicode codepoint offsets
            exp_from_cp = exp_m["expected_from_codepoint"]
            exp_to_cp = exp_m["expected_to_codepoint"]
            exp_pat_from_cp = exp_m["expected_pattern_from_codepoint"]
            exp_pat_to_cp = exp_m["expected_pattern_to_codepoint"]

            if act_m.from_pos != exp_from_cp or act_m.to_pos != exp_to_cp:
                mismatches.append(
                    f"{prefix} marker codepoint offset mismatch: expected ({exp_from_cp}, {exp_to_cp}), got ({act_m.from_pos}, {act_m.to_pos})"
                )
            if act_m.pattern_from_pos != exp_pat_from_cp or act_m.pattern_to_pos != exp_pat_to_cp:
                mismatches.append(
                    f"{prefix} pattern codepoint offset mismatch: expected ({exp_pat_from_cp}, {exp_pat_to_cp}), got ({act_m.pattern_from_pos}, {act_m.pattern_to_pos})"
                )

            # Verify exact text slices against Java UTF-16 slices
            expected_marker_slice = text_slice_from_utf16(clean_text, exp_m["from_utf16"], exp_m["to_utf16"])
            actual_marker_slice = clean_text[act_m.from_pos:act_m.to_pos]
            if actual_marker_slice != expected_marker_slice:
                mismatches.append(
                    f"{prefix} marker slice mismatch: expected {expected_marker_slice!r}, got {actual_marker_slice!r}"
                )

            expected_pattern_slice = text_slice_from_utf16(clean_text, exp_m["pattern_from_utf16"], exp_m["pattern_to_utf16"])
            actual_pattern_slice = clean_text[act_m.pattern_from_pos:act_m.pattern_to_pos]
            if actual_pattern_slice != expected_pattern_slice:
                mismatches.append(
                    f"{prefix} pattern slice mismatch: expected {expected_pattern_slice!r}, got {actual_pattern_slice!r}"
                )

            # Verify message & short message
            if act_m.message != exp_m["message"]:
                mismatches.append(f"{prefix} message mismatch: expected {exp_m['message']!r}, got {act_m.message!r}")
            if act_m.short_message != exp_m["short_message"]:
                mismatches.append(f"{prefix} short_message mismatch: expected {exp_m['short_message']!r}, got {act_m.short_message!r}")

            # Verify suggestions
            exp_suggs = exp_m.get("suggestions", [])
            if act_m.suggestions != exp_suggs:
                mismatches.append(
                    f"{prefix} suggestions mismatch: expected {exp_suggs}, got {act_m.suggestions}"
                )

    assert not mismatches, f"Advanced pattern oracle parity failures ({len(mismatches)}):\n" + "\n".join(mismatches)

