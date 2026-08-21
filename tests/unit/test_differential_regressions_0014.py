"""Task 0014 section 15 - Java-free parity against the committed regression fixture.

The expected findings in ``tests/fixtures/differential_regressions_0014.json`` were
produced by the trusted pinned Java oracle, never typed by hand.  These tests replay
them against the Python pipeline without a JVM.

The same replay covers ``tests/fixtures/oracle_utf16_calibration_0014.json``, which
pins the UTF-16 offset domain for non-BMP, combining-mark and soft-hyphen inputs.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest

from tools.differential_batch_oracle_0014 import pylat_findings
from tools.differential_corpus_0014 import (
    REGRESSION_FIXTURE_PATH,
    UTF16_CALIBRATION_PATH,
    build_profiles,
    python_tool,
    utf16_prefix_table,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def regressions() -> dict:
    return json.loads(REGRESSION_FIXTURE_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def calibration() -> dict:
    return json.loads(UTF16_CALIBRATION_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tools() -> dict:
    profiles = build_profiles()
    return {profile_id: python_tool(profiles[profile_id]) for profile_id in profiles}


def test_regression_cases_reproduce_pinned_java_findings(
    regressions: dict, tools: dict
) -> None:
    """Every minimized regression case must match the recorded pinned-Java result."""
    for case in regressions["cases"]:
        actual = [
            finding.comparable_json()
            for finding in pylat_findings(tools[case["profile"]].check(case["minimized_text"]))
        ]
        expected = [list(finding) for finding in case["expected_java_findings"]]
        assert actual == expected, case["case_id"]


def test_regression_cases_carry_their_required_provenance(regressions: dict) -> None:
    for case in regressions["cases"]:
        for key in (
            "case_id",
            "discovered_in_stratum",
            "original_mismatch_type",
            "minimized_text",
            "profile",
            "expected_java_findings",
            "upstream_proof",
        ):
            assert key in case, (case.get("case_id"), key)
        assert case["minimized_text"].strip()
        assert case["profile"] in build_profiles()


def test_calibration_cases_reproduce_pinned_java_findings(
    calibration: dict, tools: dict
) -> None:
    """Section 4.2: Python must match recorded Java output on non-BMP inputs exactly."""
    tool = tools[calibration["metadata"]["profile"]["profile_id"]]
    for case in calibration["cases"]:
        actual = [
            finding.comparable_json()
            for finding in pylat_findings(tool.check(case["text"]))
        ]
        expected = [list(finding) for finding in case["java_findings"]]
        assert actual == expected, case["case_id"]


def test_python_utf16_spans_agree_with_its_own_code_point_spans(
    calibration: dict, tools: dict
) -> None:
    """A disagreement inside Python's dual offset representation is a test failure."""
    tool = tools[calibration["metadata"]["profile"]["profile_id"]]
    checked = 0
    for case in calibration["cases"]:
        text = case["text"]
        prefix = utf16_prefix_table(text)
        assert prefix[-1] == case["text_utf16_length"]
        assert len(text) == case["text_code_point_length"]
        for match in tool.check(text):
            assert match.utf16_offset == prefix[match.offset], case["case_id"]
            assert (
                match.utf16_length
                == prefix[match.offset + match.length] - prefix[match.offset]
            ), case["case_id"]
            checked += 1
    assert checked > 0


def test_calibration_covers_the_required_unicode_categories(calibration: dict) -> None:
    cases = calibration["cases"]
    assert sum(1 for case in cases if case["has_non_bmp"]) >= 50
    assert sum(1 for case in cases if case["has_combining"]) >= 10
    assert sum(1 for case in cases if case["has_soft_hyphen"]) >= 10
    assert any(
        case["text_utf16_length"] - case["text_code_point_length"] >= 4
        for case in cases
    ), "expected a case with several non-BMP characters"
    assert any(
        any(unicodedata.combining(character) for character in case["text"])
        and case["has_non_bmp"]
        for case in cases
    ), "expected a BMP + non-BMP mixture"
