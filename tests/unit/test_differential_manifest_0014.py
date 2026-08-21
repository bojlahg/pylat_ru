"""Task 0014 section 21 - manifest, summary and regression-fixture integrity.

All of these run without Java.  They validate the committed campaign evidence:
pinned upstream identity, trusted oracle identity, source hashes, count and rate
arithmetic, the zero-unexplained gate, and the fail-closed properties of the
allowlist and the regression fixture.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from tools.differential_corpus_0014 import (
    ALLOWLIST_PATH,
    UPSTREAM_DEFECTS_PATH,
    FIXED_SEED,
    GENERATOR_VERSION,
    MANIFEST_PATH,
    REGRESSION_FIXTURE_PATH,
    STRATA,
    SUMMARY_PATH,
    UTF16_CALIBRATION_PATH,
    build_profiles,
    corpus_signature,
    default_off_rule_ids,
)
from tools.differential_lt import (
    PINNED_LT_COMMIT,
    PINNED_LT_VERSION,
    sha256_file,
    validate_oracle_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ORACLE_MANIFEST_PATH = REPO_ROOT / "compat" / "oracle_manifest.json"

HEX64 = re.compile(r"^[0-9a-f]{64}$")


@pytest.fixture(scope="module")
def manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def oracle_manifest() -> dict:
    return validate_oracle_manifest(ORACLE_MANIFEST_PATH)


# -- manifest schema and identity -------------------------------------------


def test_manifest_has_the_required_schema(manifest: dict) -> None:
    required = {
        "schema_version",
        "task",
        "pinned_lt_version",
        "pinned_lt_commit",
        "oracle_build_id",
        "oracle_jar_sha256",
        "generator_version",
        "fixed_seed",
        "source_inventory",
        "mutation_families",
        "profiles",
        "counts",
        "corpus_signature",
        "stratum_signatures",
        "external_corpus",
    }
    assert required.issubset(manifest.keys()), required - manifest.keys()
    assert manifest["task"] == "0014"
    assert manifest["generator_version"] == GENERATOR_VERSION
    assert manifest["fixed_seed"] == FIXED_SEED


def test_manifest_binds_pinned_upstream_identity(manifest: dict) -> None:
    assert manifest["pinned_lt_version"] == PINNED_LT_VERSION
    assert manifest["pinned_lt_commit"] == PINNED_LT_COMMIT


def test_manifest_binds_the_trusted_oracle_identity(
    manifest: dict, oracle_manifest: dict
) -> None:
    assert manifest["oracle_build_id"] == oracle_manifest["default_build_id"]
    assert manifest["oracle_jar_sha256"] == oracle_manifest["oracle_sha256"]
    assert HEX64.match(manifest["oracle_jar_sha256"])


def test_manifest_source_hashes_match_the_committed_files(manifest: dict) -> None:
    assert manifest["source_inventory"]
    for relative_path, recorded in manifest["source_inventory"].items():
        path = REPO_ROOT / relative_path
        assert path.is_file(), relative_path
        assert sha256_file(path) == recorded, relative_path


def test_manifest_records_the_language_model_exclusion(manifest: dict) -> None:
    language_model = manifest["language_model_rule"]
    assert language_model["rule_class"] == "RussianConfusionProbabilityRule"
    assert language_model["status"] == "LANGUAGE_MODEL_DEFERRED"
    assert language_model["excluded_from_java_surface"] is True


def test_manifest_profiles_match_the_generator(manifest: dict) -> None:
    profiles = build_profiles()
    assert set(manifest["profiles"]) == set(profiles)
    for profile_id, recorded in manifest["profiles"].items():
        assert recorded == profiles[profile_id].to_dict()
        assert manifest["profile_signatures"][profile_id] == profiles[
            profile_id
        ].signature()


def test_manifest_declares_level_and_config_sensitivity_evidence(manifest: dict) -> None:
    assert manifest["profiles"]["default"]["level"] == "DEFAULT"
    assert manifest["profiles"]["ref_picky"]["level"] == "PICKY"
    specs = manifest["config_sensitivity_specs"]
    assert set(specs) == {
        "cfg_long_sentence_15",
        "cfg_long_paragraph_30",
        "cfg_filler_words_2",
        "cfg_speller_conf_ru_1",
    }
    assert all(spec["text_sha256"] for spec in specs.values())


def test_manifest_default_off_list_is_derived_not_invented(manifest: dict) -> None:
    assert manifest["default_off_rule_ids"] == default_off_rule_ids()
    assert "CONFUSION_RULE" not in manifest["default_off_rule_ids"]


def test_manifest_count_arithmetic_is_consistent(manifest: dict) -> None:
    counts = manifest["counts"]
    assert counts["cases_total"] == sum(counts["cases_by_stratum"].values())
    assert counts["cases_total"] == sum(counts["cases_by_profile"].values())
    assert set(counts["cases_by_stratum"]) == set(STRATA)
    for stratum in STRATA:
        assert counts["unique_texts_by_stratum"][stratum] <= counts[
            "cases_by_stratum"
        ][stratum]


def test_manifest_meets_the_mandatory_campaign_minimums(manifest: dict) -> None:
    """Section 8 minimum campaign size."""
    counts = manifest["counts"]
    assert counts["unique_texts_total"] >= 8000, counts["unique_texts_total"]
    assert counts["cases_total"] >= 12000, counts["cases_total"]
    assert counts["unique_texts_by_stratum"]["C"] >= 2000
    assert counts["unique_texts_by_stratum"]["D"] >= 2000
    assert counts["non_bmp_executions"] >= 500


def test_manifest_signatures_are_hex_and_regenerable(manifest: dict) -> None:
    assert HEX64.match(manifest["corpus_signature"])
    for stratum in STRATA:
        assert HEX64.match(manifest["stratum_signatures"][stratum])
    assert corpus_signature([]) == hashlib.sha256().hexdigest()


def test_manifest_contains_no_natural_corpus_text(manifest: dict) -> None:
    """The external corpus is described, never embedded."""
    payload = json.dumps(manifest, ensure_ascii=False)
    assert "corpora/" in payload
    external = manifest["external_corpus"]
    assert external["sources"]
    for source in external["sources"]:
        for key in (
            "site",
            "api_url",
            "license",
            "retrieval_date",
            "selection_method",
            "local_file",
            "size_bytes",
            "sha256",
            "raw_block_count",
            "retained_block_count",
        ):
            assert key in source, (source["source_id"], key)
        assert HEX64.match(source["sha256"])
        assert source["local_file"].startswith("corpora/")
        assert source["retained_block_count"] > 0
        assert "text" not in source


def test_external_corpus_has_two_distinct_sources(manifest: dict) -> None:
    sources = manifest["external_corpus"]["sources"]
    assert len({source["source_id"] for source in sources}) >= 2
    assert {source["site"] for source in sources} == {
        "ru.wikipedia.org",
        "ru.wikisource.org",
    }
    counts = {source["source_id"]: source["retained_block_count"] for source in sources}
    assert counts["ru_wikipedia"] >= 1500, counts
    assert counts["ru_wikisource"] >= 750, counts
    assert manifest["external_corpus"]["total_unique_nonempty_blocks"] >= 2000


def test_manifest_does_not_embed_timestamps_in_semantic_identity(manifest: dict) -> None:
    """Section 17: no timestamps inside reproducibility hashes."""
    assert "generated_at" not in manifest
    assert "timestamp" not in manifest


# -- summary ----------------------------------------------------------------


def test_summary_has_the_required_schema(summary: dict) -> None:
    required = {
        "schema_version",
        "task",
        "campaign_identity",
        "input_manifest_sha256",
        "oracle",
        "repository_sha",
        "totals",
        "parity",
        "counts_by_stratum",
        "counts_by_profile",
        "mismatch_counts_by_kind",
        "mismatch_counts_by_rule_id",
        "by_rule_id",
        "unicode_coverage",
        "suggestions",
        "unexplained_discrepancies",
        "ordinary_allowlist_entries",
        "upstream_defects",
    }
    assert required.issubset(summary.keys()), required - summary.keys()


def test_summary_is_bound_to_the_committed_manifest(
    summary: dict, manifest: dict
) -> None:
    payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    assert summary["input_manifest_sha256"] == hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()
    assert summary["campaign_identity"]["corpus_signature"] == manifest[
        "corpus_signature"
    ]
    assert summary["oracle"]["jar_sha256"] == manifest["oracle_jar_sha256"]
    assert summary["oracle"]["pinned_lt_commit"] == PINNED_LT_COMMIT


def test_summary_totals_are_internally_consistent(summary: dict) -> None:
    totals = summary["totals"]
    assert totals["exact_cases"] + totals["non_exact_cases"] == totals["cases_total"]
    assert (
        totals["comparable_cases"] + summary["upstream_defects"]["java_error_cases"]
        == totals["cases_total"]
    )
    assert totals["cases_total"] == sum(
        block["cases"] for block in summary["counts_by_stratum"].values()
    )
    assert totals["cases_total"] == sum(
        block["cases"] for block in summary["counts_by_profile"].values()
    )
    assert totals["java_findings_total"] == sum(
        block["java_findings"] for block in summary["counts_by_stratum"].values()
    )
    assert totals["pylat_findings_total"] == sum(
        block["pylat_findings"] for block in summary["counts_by_stratum"].values()
    )


def test_summary_rates_are_derived_from_integer_counts(summary: dict) -> None:
    for name, block in summary["parity"].items():
        assert set(block) == {"numerator", "denominator", "rate", "state"}, name
        if block["denominator"] == 0:
            assert block["rate"] is None, name
            assert block["state"] == "NO_OBSERVATIONS", name
        else:
            assert block["state"] == "MEASURED", name
            assert block["rate"] == pytest.approx(
                block["numerator"] / block["denominator"]
            ), name
            assert 0.0 <= block["rate"] <= 1.0, name


def test_summary_exact_rate_matches_the_totals(summary: dict) -> None:
    """Rates are measured over the cases the pinned oracle actually answered."""
    totals = summary["totals"]
    exact = summary["parity"]["finding_sequence_exact"]
    assert exact["numerator"] == totals["exact_cases"]
    assert exact["denominator"] == totals["comparable_cases"]
    assert summary["parity"]["full_observable_field"] == exact


def test_summary_meets_the_campaign_minimums(summary: dict) -> None:
    totals = summary["totals"]
    assert totals["unique_texts_total"] >= 8000
    assert totals["profile_executions_total"] >= 12000


def test_zero_unexplained_ordinary_discrepancies(summary: dict) -> None:
    """Section 12 and 25: the ordinary/non-LM target is exactly zero.

    A case the pinned oracle answered must match exactly.  A case the pinned oracle
    could not answer at all -- because pinned LanguageTool raised -- is not a
    compatibility discrepancy, but it still has to be named in the committed
    upstream-defect record rather than passed over silently.
    """
    assert summary["unexplained_discrepancies"] == 0, summary["unexplained_case_ids"]
    assert summary["totals"]["python_errors"] == 0
    assert summary["unicode_coverage"]["utf16_parity_failures"] == 0
    defects = summary["upstream_defects"]
    assert defects["unexplained"] == 0, defects["unexplained_case_ids"]
    assert defects["explained"] == defects["java_error_cases"]
    assert defects["explained"] == summary["totals"]["java_errors"]


def test_every_recorded_upstream_defect_is_fully_documented(summary: dict) -> None:
    """Section 12: a difference kept out of scope must carry its own evidence."""
    payload = json.loads(UPSTREAM_DEFECTS_PATH.read_text(encoding="utf-8"))
    assert payload["pinned_lt_commit"] == PINNED_LT_COMMIT
    recorded = {defect["defect_id"] for defect in payload["defects"]}
    observed = {
        defect_id
        for defect_id, count in summary["upstream_defects"]["by_defect_id"].items()
        if count
    }
    assert observed <= recorded
    for defect in payload["defects"]:
        for key in (
            "defect_id",
            "exception_signature",
            "rule_id",
            "trigger",
            "upstream_source",
            "upstream_evidence",
            "pylat_ru_behaviour",
            "scope_reason",
        ):
            assert defect.get(key), (defect.get("defect_id"), key)


def test_no_broad_allowlist_hides_failures(summary: dict) -> None:
    """Section 12: broad rule-wide or field-wide suppression is forbidden."""
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    entries = payload["entries"]
    assert summary["ordinary_allowlist_entries"] == len(entries)
    for entry in entries:
        # A narrow entry must name a concrete case or fingerprint, the exact fields,
        # a reason, upstream evidence and a project scope reason.
        assert entry.get("case_id") or entry.get("fingerprint"), entry
        assert entry.get("fields"), entry
        assert entry.get("reason"), entry
        assert entry.get("upstream_source_evidence"), entry
        assert entry.get("project_scope_reason"), entry
        assert "rule_id_wildcard" not in entry


def test_unicode_coverage_is_reported(summary: dict) -> None:
    coverage = summary["unicode_coverage"]
    assert coverage["non_bmp_cases"] >= 500
    assert coverage["non_bmp_exact"] == coverage["non_bmp_cases"]
    assert coverage["combining_mark_cases"] > 0
    assert coverage["soft_hyphen_cases"] > 0


def test_suggestion_metrics_are_reported(summary: dict) -> None:
    suggestions = summary["suggestions"]
    assert suggestions["java_findings_with_suggestions"] > 0
    assert suggestions["exact_ordered_suggestion_matches"] == suggestions[
        "java_findings_with_suggestions"
    ]
    assert suggestions["suggestion_content_mismatches"] == 0
    assert suggestions["suggestion_order_only_mismatches"] == 0
    assert suggestions["duplicate_preservation_mismatches"] == 0


def test_by_rule_id_view_is_sorted_and_complete(summary: dict) -> None:
    by_rule = summary["by_rule_id"]
    assert by_rule
    assert list(by_rule) == sorted(by_rule)
    for rule_id, block in by_rule.items():
        assert block["java_occurrences"] >= 0
        assert block["pylat_occurrences"] >= 0
        assert block["mismatch_count"] == 0, rule_id
    # The whole point of a differential campaign is that the oracle spoke.
    assert sum(block["java_occurrences"] for block in by_rule.values()) > 0
    assert "CONFUSION_RULE" not in by_rule


def test_summary_stratum_and_profile_views_cover_everything(summary: dict) -> None:
    assert set(summary["counts_by_stratum"]) == set(STRATA)
    assert set(summary["counts_by_profile"]) == set(build_profiles())
    for stratum, block in summary["counts_by_stratum"].items():
        assert block["exact"] + block["non_exact"] == block["cases"], stratum
    for profile_id, block in summary["counts_by_profile"].items():
        assert block["exact"] + block["non_exact"] == block["cases"], profile_id
        assert block["cases"] > 0, profile_id


def test_summary_proves_every_required_configuration_is_observable(summary: dict) -> None:
    evidence = summary["config_sensitivity"]
    assert set(evidence) == {
        "cfg_long_sentence_15",
        "cfg_long_paragraph_30",
        "cfg_filler_words_2",
        "cfg_speller_conf_ru_1",
    }
    for profile_id, block in evidence.items():
        assert block["targeted_cases"] > 0, profile_id
        assert block["java_cases_with_observable_delta"] > 0, profile_id
        assert block["python_cases_with_same_observable_delta"] > 0, profile_id
        assert block["java_python_exact_cases"] == block["targeted_cases"], profile_id
        assert block["delta_rule_ids"], profile_id


def test_new_strict_metadata_fields_have_full_parity(summary: dict) -> None:
    comparable = summary["totals"]["comparable_cases"]
    for field in ("full_rule_id", "category_name"):
        assert summary["parity"][field]["numerator"] == comparable
        assert summary["parity"][field]["denominator"] == comparable


# -- regression fixture -----------------------------------------------------


def test_regression_fixture_exists_and_is_bound_to_the_trusted_oracle(
    oracle_manifest: dict,
) -> None:
    assert REGRESSION_FIXTURE_PATH.is_file()
    payload = json.loads(REGRESSION_FIXTURE_PATH.read_text(encoding="utf-8"))
    metadata = payload["metadata"]
    assert metadata["pinned_lt_commit"] == PINNED_LT_COMMIT
    assert metadata["oracle_build_id"] == oracle_manifest["default_build_id"]
    assert metadata["oracle_jar_sha256"] == oracle_manifest["oracle_sha256"]
    if not payload["cases"]:
        # Section 15 allows an explicitly empty fixture, but it must say why.
        assert metadata["empty_reason"]


def test_regression_fixture_is_bound_in_the_oracle_manifest(
    oracle_manifest: dict,
) -> None:
    relative = "tests/fixtures/differential_regressions_0014.json"
    bindings = {
        binding["path"]: binding for binding in oracle_manifest["fixture_bindings"]
    }
    assert relative in bindings, sorted(bindings)
    binding = bindings[relative]
    payload = json.loads(REGRESSION_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert binding["size_bytes"] == REGRESSION_FIXTURE_PATH.stat().st_size
    assert binding["sha256"] == sha256_file(REGRESSION_FIXTURE_PATH)
    assert binding["case_count"] == len(payload["cases"])
    assert binding["oracle_build_id"] == oracle_manifest["default_build_id"]


def test_regression_cases_are_semantically_unique() -> None:
    payload = json.loads(REGRESSION_FIXTURE_PATH.read_text(encoding="utf-8"))
    identities = {
        (case["minimized_text"], case["profile"]) for case in payload["cases"]
    }
    assert len(identities) == len(payload["cases"])


def test_utf16_calibration_fixture_is_bound_in_the_oracle_manifest(
    oracle_manifest: dict,
) -> None:
    relative = "tests/fixtures/oracle_utf16_calibration_0014.json"
    bindings = {
        binding["path"]: binding for binding in oracle_manifest["fixture_bindings"]
    }
    assert relative in bindings, sorted(bindings)
    binding = bindings[relative]
    payload = json.loads(UTF16_CALIBRATION_PATH.read_text(encoding="utf-8"))
    assert binding["size_bytes"] == UTF16_CALIBRATION_PATH.stat().st_size
    assert binding["sha256"] == sha256_file(UTF16_CALIBRATION_PATH)
    assert binding["case_count"] == len(payload["cases"])


# -- regeneration ------------------------------------------------------------


def test_internal_strata_regenerate_to_the_recorded_signatures(manifest: dict) -> None:
    """Section 10 and 17: regenerating the internal strata reproduces the manifest.

    Only the internal strata are checked, because Stratum D is the external natural
    corpus, which is deliberately not committed.  The targeted-configuration cases are
    excluded for the same reason: their sample pool contains the natural corpus.
    """
    from tools.differential_corpus_0014 import (
        build_corpus,
        internal_stratum_signature,
    )

    cases, _ = build_corpus()
    for stratum in ("A", "B", "C", "E"):
        assert internal_stratum_signature(cases, stratum) == manifest[
            "internal_stratum_signatures"
        ][stratum], stratum


def test_compatibility_metadata_points_at_task_0014_evidence(summary: dict) -> None:
    """Section 20: the milestone section is traceable to the committed summary."""
    payload = json.loads(
        (REPO_ROOT / "compat" / "compatibility.json").read_text(encoding="utf-8")
    )
    status = payload["compatibility_status"]
    assert status["task_milestone"] == "0014_differential_corpus"
    section = status["task_0014_differential_corpus"]
    assert section["manifest"] == "compat/differential_corpus_0014_manifest.json"
    assert section["summary"] == "compat/differential_summary_0014.json"
    assert section["pinned_lt_commit"] == PINNED_LT_COMMIT
    assert section["input_manifest_sha256"] == summary["input_manifest_sha256"]
    assert section["unique_texts"] == summary["totals"]["unique_texts_total"]
    assert section["profile_executions"] == summary["totals"]["profile_executions_total"]
    assert section["exact_cases"] == summary["totals"]["exact_cases"]
    assert section["unexplained_discrepancies"] == summary["unexplained_discrepancies"]
    assert section["ordinary_allowlist_entries"] == summary["ordinary_allowlist_entries"]
    assert section["full_observable_field_parity"] == summary["parity"][
        "full_observable_field"
    ]["rate"]
    assert section["external_corpus_committed"] is False

    language_model = status["implementation_progress"]["java_rules"][
        "language_model_rules"
    ]
    assert language_model["implemented"] == 0
    assert language_model["status"] == "LANGUAGE_MODEL_DEFERRED"


def test_state_and_order_invariance_evidence_is_committed(manifest: dict) -> None:
    """Section 5.4: long-lived state and case order must not change a result."""
    from tools.differential_corpus_0014 import STATE_ISOLATION_PATH

    payload = json.loads(STATE_ISOLATION_PATH.read_text(encoding="utf-8"))
    assert payload["pinned_lt_commit"] == PINNED_LT_COMMIT
    assert payload["corpus_signature"] == manifest["corpus_signature"]
    assert payload["sample_size"] >= 100
    assert payload["oracle_error_cases"] == len(payload["oracle_error_case_ids"])
    assert payload["java_fresh_matches_shared"] is True
    assert payload["java_reverse_matches_forward"] is True
    assert payload["python_fresh_matches_shared"] is True
    assert payload["python_reverse_matches_forward"] is True
    assert payload["divergent_case_ids"] == []
    assert set(payload["profiles"]) == set(build_profiles())


def test_comparable_finding_totals_agree(summary: dict) -> None:
    """Over the cases the oracle answered, both sides produced the same findings."""
    totals = summary["totals"]
    assert totals["java_findings_comparable"] == totals["pylat_findings_comparable"]
    assert totals["java_findings_comparable"] > 0
