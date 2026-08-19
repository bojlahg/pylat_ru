"""tools/russian_grammar_advanced_inventory.py

Deterministic generator for compat/russian_grammar_advanced_inventory.json.
Extracts comprehensive advanced matching statistics, observed attribute distributions,
Java loader variant expansions, feature usage independent of blockers, and deterministic
before/after transition matrix for all 892 LanguageTool Russian XML grammar rules.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
LICENSE_INV_PATH = REPO_ROOT / "third_party" / "languagetool" / "license_inventory.json"
ORACLE_MANIFEST_PATH = REPO_ROOT / "compat" / "oracle_manifest.json"
CANONICAL_RAW_INVENTORY_PATH = REPO_ROOT / "compat" / "inventory.json"
CORE_INVENTORY_PATH = REPO_ROOT / "compat" / "russian_grammar_core_inventory.json"
ADVANCED_INVENTORY_OUTPUT_PATH = REPO_ROOT / "compat" / "russian_grammar_advanced_inventory.json"
GRAMMAR_XML_PATH = (
    REPO_ROOT
    / "third_party"
    / "languagetool"
    / "languagetool-language-modules"
    / "ru"
    / "src"
    / "main"
    / "resources"
    / "org"
    / "languagetool"
    / "rules"
    / "ru"
    / "grammar.xml"
)

PINNED_LT_VERSION = "6.8"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"
BASELINE_0007_COMMIT = "b75bc4dfa84c1549d22f83388785dd9b2988f6de"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_trusted_java_variant_evidence(
    variant_inv_path: Optional[Path] = None,
    oracle_manifest_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Load canonical manifest-bound Java loader expansion evidence, validating against oracle_manifest.json."""
    if variant_inv_path is None:
        variant_inv_path = REPO_ROOT / "compat" / "rule_variant_inventory.json"
    if oracle_manifest_path is None:
        oracle_manifest_path = REPO_ROOT / "compat" / "oracle_manifest.json"

    if not variant_inv_path.is_file():
        raise FileNotFoundError(f"Missing canonical variant inventory: {variant_inv_path}")
    if not oracle_manifest_path.is_file():
        raise FileNotFoundError(f"Missing oracle manifest: {oracle_manifest_path}")

    oracle_manifest = json.loads(oracle_manifest_path.read_text(encoding="utf-8"))
    trusted_builds = {
        b["build_id"]: b for b in oracle_manifest.get("trusted_oracle_builds", [])
    }

    data = json.loads(variant_inv_path.read_text(encoding="utf-8"))
    prov = data.get("provenance")
    if not isinstance(prov, dict):
        raise ValueError(f"Missing or malformed provenance in {variant_inv_path}")

    ver = prov.get("pinned_lt_version")
    commit = prov.get("pinned_lt_commit")
    build_id = prov.get("oracle_build_id")
    jar_sha256 = prov.get("oracle_jar_sha256")

    if ver != PINNED_LT_VERSION:
        raise ValueError(f"Invalid pinned_lt_version in {variant_inv_path}: expected {PINNED_LT_VERSION}, got {ver}")
    if commit != PINNED_LT_COMMIT:
        raise ValueError(f"Invalid pinned_lt_commit in {variant_inv_path}: expected {PINNED_LT_COMMIT}, got {commit}")
    if not build_id or build_id not in trusted_builds:
        raise ValueError(f"Untrusted or missing oracle_build_id '{build_id}' in {variant_inv_path}")

    trusted_record = trusted_builds[build_id]
    if trusted_record.get("pinned_version") != ver:
        raise ValueError(f"Version mismatch between variant provenance ({ver}) and oracle build ({trusted_record.get('pinned_version')})")
    if trusted_record.get("pinned_commit") != commit:
        raise ValueError(f"Commit mismatch between variant provenance ({commit}) and oracle build ({trusted_record.get('pinned_commit')})")
    if trusted_record.get("jar_sha256") != jar_sha256:
        raise ValueError(f"JAR SHA-256 mismatch for build {build_id}: expected {trusted_record.get('jar_sha256')}, got {jar_sha256}")

    # Validate required fields strictly without fallbacks
    for req_field in ("java_total_physical_rules", "source_xml_rules_total", "multi_variant_source_rules_count", "per_full_id_counts"):
        if req_field not in data:
            raise ValueError(f"Missing required field '{req_field}' in {variant_inv_path}")

    total_physical = data["java_total_physical_rules"]
    if not isinstance(total_physical, int) or total_physical <= 0:
        raise ValueError(f"Invalid java_total_physical_rules in {variant_inv_path}: {total_physical}")

    source_rules_tot = data["source_xml_rules_total"]
    if not isinstance(source_rules_tot, int) or source_rules_tot <= 0:
        raise ValueError(f"Invalid source_xml_rules_total in {variant_inv_path}: {source_rules_tot}")

    multi_variant_cnt = data["multi_variant_source_rules_count"]
    if not isinstance(multi_variant_cnt, int) or multi_variant_cnt < 0:
        raise ValueError(f"Invalid multi_variant_source_rules_count in {variant_inv_path}: {multi_variant_cnt}")

    per_full_id = data["per_full_id_counts"]
    if not isinstance(per_full_id, dict) or len(per_full_id) != source_rules_tot:
        raise ValueError(f"Invalid per_full_id_counts in {variant_inv_path}: length {len(per_full_id)} != {source_rules_tot}")

    expanded_rules = {k: v for k, v in per_full_id.items() if v > 1}
    if len(expanded_rules) != multi_variant_cnt:
        raise ValueError(f"Mismatch in expanded rules count: {len(expanded_rules)} != {multi_variant_cnt}")

    max_variants = max(per_full_id.values()) if per_full_id else 1

    return {
        "source_manifest": "compat/rule_variant_inventory.json",
        "provenance": {
            "pinned_lt_version": ver,
            "pinned_lt_commit": commit,
            "oracle_build_id": build_id,
            "oracle_jar_sha256": jar_sha256,
        },
        "total_physical_rules": total_physical,
        "unique_full_ids": source_rules_tot,
        "multi_variant_rules_count": multi_variant_cnt,
        "max_variants_per_rule": max_variants,
        "expanded_rules": expanded_rules,
    }


def classify_runtime_example(ex_elem: ET.Element) -> Tuple[bool, bool, bool, bool]:
    """Runtime example classification matching GrammarLoader._parse_example().

    Returns:
        (is_incorrect, correction_attribute_present, correction_value_non_empty, correction_value_empty)
    """
    ex_type = ex_elem.attrib.get("type")
    corr_attr = ex_elem.attrib.get("correction")
    corr_present = (corr_attr is not None)
    corr_non_empty = bool(corr_attr and corr_attr.strip() != "")
    corr_empty = corr_present and not corr_non_empty

    if ex_type in ("triggers_error", "incorrect") or "correction" in ex_elem.attrib:
        is_inc = (ex_type not in ("untouched", "correct"))
    else:
        is_inc = False
    return is_inc, corr_present, corr_non_empty, corr_empty


def classify_raw_markup_example(ex_elem: ET.Element) -> Tuple[bool, bool, bool, bool]:
    """Raw XML markup error-like classification based on markers, corrections, and type tags.

    Returns:
        (is_error_like, correction_attribute_present, correction_value_non_empty, correction_value_empty)
    """
    ex_type = ex_elem.attrib.get("type")
    corr_attr = ex_elem.attrib.get("correction")
    has_marker = bool(ex_elem.findall("marker"))
    corr_present = (corr_attr is not None)
    corr_non_empty = bool(corr_attr and corr_attr.strip() != "")
    corr_empty = corr_present and not corr_non_empty

    if ex_type in ("untouched", "correct"):
        is_inc = False
    elif ex_type in ("triggers_error", "incorrect") or corr_present or has_marker:
        is_inc = True
    else:
        is_inc = False
    return is_inc, corr_present, corr_non_empty, corr_empty



def _extract_raw_xml_tree_totals(root: ET.Element) -> Dict[str, Any]:
    """Exhaustively parse the complete XML tree to derive raw tag and attribute occurrences."""
    tag_counts = Counter(elem.tag for elem in root.iter())
    attribute_counts: Dict[str, int] = Counter()
    attribute_distributions: Dict[str, Counter] = defaultdict(Counter)

    for elem in root.iter():
        for attr, val in elem.attrib.items():
            key = f"{elem.tag}@{attr}"
            attribute_counts[key] += 1
            attribute_distributions[key][val] += 1

    # Extract specific raw element counts
    raw_matches = list(root.iter("match"))
    raw_antipatterns = list(root.iter("antipattern"))
    raw_rg_antipatterns = list(root.findall(".//rulegroup/antipattern"))
    raw_r_antipatterns = list(root.findall(".//rule/antipattern"))
    raw_tokens = list(root.iter("token"))
    raw_exceptions = list(root.iter("exception"))
    raw_examples = list(root.iter("example"))
    raw_patterns = list(root.iter("pattern"))

    # Contextual <match> classification
    token_level_matches: List[ET.Element] = []
    msg_sugg_matches: List[ET.Element] = []
    other_matches: List[Tuple[str, ET.Element]] = []
    static_lemma_matches: List[ET.Element] = []

    for elem in root.iter():
        for child in elem:
            if child.tag == "match":
                if elem.tag in ("token", "unify-ignore"):
                    token_level_matches.append(child)
                elif elem.tag in ("message", "suggestion"):
                    msg_sugg_matches.append(child)
                else:
                    other_matches.append((elem.tag, child))
                if child.text and child.text.strip():
                    static_lemma_matches.append(child)

    # Raw exception scope distribution (explicit vs implicit default-current)
    explicit_exc_scopes = Counter()
    for exc in raw_exceptions:
        if "scope" in exc.attrib:
            explicit_exc_scopes[exc.attrib["scope"]] += 1
    effective_exc_scopes = Counter()
    for exc in raw_exceptions:
        scope = exc.attrib.get("scope", "current")
        effective_exc_scopes[scope] += 1

    # Raw markup error-like classification (markers, corrections, triggers_error)
    markup_inc_cnt = 0
    markup_cor_cnt = 0
    markup_corr_present_cnt = 0
    markup_corr_nonempty_cnt = 0
    markup_corr_empty_cnt = 0
    for e in raw_examples:
        is_inc, c_pres, c_nonempty, c_empty = classify_raw_markup_example(e)
        if is_inc:
            markup_inc_cnt += 1
        else:
            markup_cor_cnt += 1
        if c_pres:
            markup_corr_present_cnt += 1
        if c_nonempty:
            markup_corr_nonempty_cnt += 1
        if c_empty:
            markup_corr_empty_cnt += 1

    # Runtime example classification across raw examples (GrammarLoader semantics)
    rt_inc_cnt = 0
    rt_cor_cnt = 0
    rt_corr_present_cnt = 0
    rt_corr_nonempty_cnt = 0
    rt_corr_empty_cnt = 0
    for e in raw_examples:
        is_inc, c_pres, c_nonempty, c_empty = classify_runtime_example(e)
        if is_inc:
            rt_inc_cnt += 1
        else:
            rt_cor_cnt += 1
        if c_pres:
            rt_corr_present_cnt += 1
        if c_nonempty:
            rt_corr_nonempty_cnt += 1
        if c_empty:
            rt_corr_empty_cnt += 1

    return {
        "tag_counts": dict(sorted(tag_counts.items())),
        "attribute_counts": dict(sorted(attribute_counts.items())),
        "attribute_distributions": {k: dict(sorted(v.items())) for k, v in sorted(attribute_distributions.items())},
        "match_context_summary": {
            "total_match_elements": len(raw_matches),
            "token_level_matches": len(token_level_matches),
            "message_suggestion_matches": len(msg_sugg_matches),
            "other_context_matches": len(other_matches),
            "static_lemma_matches": len(static_lemma_matches),
        },
        "reconciliation_checks": {
            "match_elements_total": len(raw_matches),
            "antipattern_elements_total": len(raw_antipatterns),
            "antipattern_rulegroup_level": len(raw_rg_antipatterns),
            "antipattern_rule_level": len(raw_r_antipatterns),
            "token_chunk_occurrences": attribute_counts.get("token@chunk", 0),
            "token_spacebefore_occurrences": attribute_counts.get("token@spacebefore", 0),
            "token_skip_occurrences": attribute_counts.get("token@skip", 0),
            "token_min_occurrences": attribute_counts.get("token@min", 0),
            "token_max_occurrences": attribute_counts.get("token@max", 0),
            "exception_spacebefore_occurrences": attribute_counts.get("exception@spacebefore", 0),
            "exception_scope_explicit_occurrences": attribute_counts.get("exception@scope", 0),
            "match_case_conversion_occurrences": attribute_counts.get("match@case_conversion", 0),
            "match_include_skipped_occurrences": attribute_counts.get("match@include_skipped", 0),
            "match_postag_occurrences": attribute_counts.get("match@postag", 0),
            "match_postag_regexp_occurrences": attribute_counts.get("match@postag_regexp", 0),
            "match_postag_replace_occurrences": attribute_counts.get("match@postag_replace", 0),
            "match_regexp_match_occurrences": attribute_counts.get("match@regexp_match", 0),
            "match_regexp_replace_occurrences": attribute_counts.get("match@regexp_replace", 0),
            "match_setpos_occurrences": attribute_counts.get("match@setpos", 0),
            "pattern_raw_pos_occurrences": attribute_counts.get("pattern@raw_pos", 0),
        },
        "antipattern_summary": {
            "raw_total_antipattern_elements": len(raw_antipatterns),
            "raw_rule_antipattern_elements": len(raw_r_antipatterns),
            "raw_rulegroup_antipattern_elements": len(raw_rg_antipatterns),
        },
        "exception_scope_summary": {
            "raw_total_exceptions": len(raw_exceptions),
            "explicit_scope_raw_occurrences": sum(explicit_exc_scopes.values()),
            "explicit_scope_distribution": dict(sorted(explicit_exc_scopes.items())),
            "implicit_scope_raw_occurrences": len(raw_exceptions) - sum(explicit_exc_scopes.values()),
            "effective_scope_distribution": dict(sorted(effective_exc_scopes.items())),
        },
        "raw_examples_summary": {
            "total_examples": len(raw_examples),
            "markup_error_like_examples": markup_inc_cnt,
            "markup_untouched_or_correct_examples": markup_cor_cnt,
            "correction_attribute_present": markup_corr_present_cnt,
            "correction_value_non_empty": markup_corr_nonempty_cnt,
            "correction_value_empty": markup_corr_empty_cnt,
            "runtime_incorrect_examples": rt_inc_cnt,
            "runtime_correct_examples": rt_cor_cnt,
        },
    }


def generate_advanced_inventory() -> Dict[str, Any]:
    """Parse grammar.xml and build complete advanced matching inventory."""
    this_script_path = Path(__file__).resolve()
    generator_sha256 = sha256_file(this_script_path)

    tree = ET.parse(str(GRAMMAR_XML_PATH))
    root = tree.getroot()

    xml_size = GRAMMAR_XML_PATH.stat().st_size
    xml_sha256 = sha256_file(GRAMMAR_XML_PATH)

    # 1. Exhaustive Raw XML tree metrics (Unit A: raw_xml_occurrences)
    raw_xml_totals = _extract_raw_xml_tree_totals(root)

    # Core historical baseline for comparison
    core_inv_data = json.loads(CORE_INVENTORY_PATH.read_text(encoding="utf-8"))
    core_rules_list = core_inv_data["grammar"]["rules"]
    core_rule_states = {r["source_order_index"]: r["execution_state"] for r in core_rules_list}
    core_rule_blockers = {r["source_order_index"]: r["blockers"] for r in core_rules_list}

    # Collect rulegroups and categories
    categories = root.findall("category")
    rulegroups = root.findall(".//rulegroup")
    direct_rules = [r for r in root.findall(".//category/rule")]
    all_rules = root.findall(".//rule")

    assert len(categories) == 8, f"Expected 8 categories, got {len(categories)}"
    assert len(rulegroups) == 297, f"Expected 297 rulegroups, got {len(rulegroups)}"
    assert len(all_rules) == 892, f"Expected 892 rules, got {len(all_rules)}"

    # Per-feature rule tracking (Unit B: source_rules_count)
    feature_source_rules: Dict[str, Set[str]] = defaultdict(set)
    feature_positive_occurrences: Dict[str, int] = defaultdict(int)
    feature_representative_rules: Dict[str, List[str]] = defaultdict(list)
    feature_examples_counts: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "incorrect": 0,
            "correct": 0,
            "correction_attribute_present": 0,
            "correction_value_non_empty": 0,
            "correction_value_empty": 0,
        }
    )

    # Positive pattern token value distributions
    pos_dist_skip: Counter = Counter()
    pos_dist_min: Counter = Counter()
    pos_dist_max: Counter = Counter()
    pos_dist_spacebefore: Counter = Counter()
    pos_dist_exc_scope: Counter = Counter()
    pos_dist_exc_spacebefore: Counter = Counter()
    pos_dist_case_conv: Counter = Counter()
    pos_dist_include_skipped: Counter = Counter()
    pos_dist_setpos: Counter = Counter()
    pos_dist_raw_pos: Counter = Counter()
    pos_dist_chunk: Counter = Counter()

    rules_records: List[Dict[str, Any]] = []
    source_order_idx = 0

    classification_counts: Dict[str, int] = defaultdict(int)
    examples_by_state: Dict[str, Dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "incorrect": 0,
            "correct": 0,
            "correction_attribute_present": 0,
            "correction_value_non_empty": 0,
            "correction_value_empty": 0,
        }
    )
    total_rule_examples_count = 0

    # Track effective antipattern applications
    rules_with_direct_antipatterns: Set[str] = set()
    rules_with_inherited_antipatterns: Set[str] = set()
    effective_inherited_antipattern_apps = 0

    # Blocker combinations tracking
    blocker_combinations_counter: Counter = Counter()

    # Transition tracking from 0007 -> 0008
    task_0007_to_0008_transitions: Counter = Counter()

    for cat in categories:
        cat_id = cat.attrib["id"]
        cat_name = cat.attrib.get("name", cat_id)

        for child in cat:
            if child.tag == "rulegroup":
                group_id = child.attrib["id"]
                group_name = child.attrib.get("name", group_id)
                group_default_off = (child.attrib.get("default") == "off")
                group_minprevmatches = child.attrib.get("minprevmatches")
                group_distancetokens = child.attrib.get("distancetokens")
                group_antipatterns = child.findall("antipattern")
                child_rules = child.findall("rule")

                rule_num = 0
                for r_elem in child:
                    if r_elem.tag == "rule":
                        rule_num += 1
                        r_id = r_elem.attrib.get("id")
                        assigned_id = r_id if r_id else group_id
                        sub_id = str(rule_num)
                        full_id = f"{assigned_id}[{sub_id}]"
                        r_name = r_elem.attrib.get("name", group_name)
                        r_default_off = (r_elem.attrib.get("default") == "off") or group_default_off

                        rec = _analyze_single_rule(
                            r_elem=r_elem,
                            full_id=full_id,
                            rule_id=r_id,
                            sub_id=sub_id,
                            name=r_name,
                            category_id=cat_id,
                            category_name=cat_name,
                            rulegroup_id=group_id,
                            rulegroup_name=group_name,
                            default_off=r_default_off,
                            source_order=source_order_idx,
                            parent_antipatterns=group_antipatterns,
                            parent_minprevmatches=group_minprevmatches,
                            parent_distancetokens=group_distancetokens,
                            core_state=core_rule_states.get(source_order_idx, "UNKNOWN"),
                            core_blockers=core_rule_blockers.get(source_order_idx, []),
                        )
                        rules_records.append(rec)
                        source_order_idx += 1

                        if r_elem.findall("antipattern"):
                            rules_with_direct_antipatterns.add(full_id)
                        if group_antipatterns:
                            rules_with_inherited_antipatterns.add(full_id)
                            effective_inherited_antipattern_apps += len(group_antipatterns)

            elif child.tag == "rule":
                r_elem = child
                r_id = r_elem.attrib["id"]
                sub_id = "1"
                full_id = f"{r_id}[{sub_id}]"
                r_name = r_elem.attrib.get("name", r_id)
                r_default_off = (r_elem.attrib.get("default") == "off")

                rec = _analyze_single_rule(
                    r_elem=r_elem,
                    full_id=full_id,
                    rule_id=r_id,
                    sub_id=sub_id,
                    name=r_name,
                    category_id=cat_id,
                    category_name=cat_name,
                    rulegroup_id=None,
                    rulegroup_name=None,
                    default_off=r_default_off,
                    source_order=source_order_idx,
                    parent_antipatterns=[],
                    parent_minprevmatches=None,
                    parent_distancetokens=None,
                    core_state=core_rule_states.get(source_order_idx, "UNKNOWN"),
                    core_blockers=core_rule_blockers.get(source_order_idx, []),
                )
                rules_records.append(rec)
                source_order_idx += 1

                if r_elem.findall("antipattern"):
                    rules_with_direct_antipatterns.add(full_id)

    assert source_order_idx == 892, f"Expected 892 rules processed, got {source_order_idx}"

    # Aggregate records
    for r in rules_records:
        fid = r["full_id"]
        st_0007 = r["task_0007_state"]
        st = r["task_0008_state"]
        classification_counts[st] += 1
        task_0007_to_0008_transitions[f"{st_0007} -> {st}"] += 1

        # Blocker combination string
        rem_blockers = r["remaining_blockers_after_0008"]
        if not rem_blockers:
            blocker_key = "NONE"
        else:
            blocker_key = "+".join(sorted({b["feature"] for b in rem_blockers}))
        blocker_combinations_counter[blocker_key] += 1

        ex_cnt = r["examples_count"]
        examples_by_state[st]["total"] += ex_cnt["total"]
        examples_by_state[st]["incorrect"] += ex_cnt["incorrect"]
        examples_by_state[st]["correct"] += ex_cnt["correct"]
        examples_by_state[st]["correction_attribute_present"] += ex_cnt["correction_attribute_present"]
        examples_by_state[st]["correction_value_non_empty"] += ex_cnt["correction_value_non_empty"]
        examples_by_state[st]["correction_value_empty"] += ex_cnt["correction_value_empty"]
        total_rule_examples_count += ex_cnt["total"]

        for feat in r["feature_usage"]:
            feature_source_rules[feat].add(fid)
            feature_examples_counts[feat]["total"] += ex_cnt["total"]
            feature_examples_counts[feat]["incorrect"] += ex_cnt["incorrect"]
            feature_examples_counts[feat]["correct"] += ex_cnt["correct"]
            feature_examples_counts[feat]["correction_attribute_present"] += ex_cnt["correction_attribute_present"]
            feature_examples_counts[feat]["correction_value_non_empty"] += ex_cnt["correction_value_non_empty"]
            feature_examples_counts[feat]["correction_value_empty"] += ex_cnt["correction_value_empty"]
            if len(feature_representative_rules[feat]) < 5 and fid not in feature_representative_rules[feat]:
                feature_representative_rules[feat].append(fid)

        for feat, p_cnt in r["positive_feature_counts"].items():
            feature_positive_occurrences[feat] += p_cnt

        for k, v in r["attribute_counts"].items():
            if k == "skip":
                pos_dist_skip.update(v)
            elif k == "min":
                pos_dist_min.update(v)
            elif k == "max":
                pos_dist_max.update(v)
            elif k == "spacebefore":
                pos_dist_spacebefore.update(v)
            elif k == "exc_scope":
                pos_dist_exc_scope.update(v)
            elif k == "exc_spacebefore":
                pos_dist_exc_spacebefore.update(v)
            elif k == "case_conversion":
                pos_dist_case_conv.update(v)
            elif k == "include_skipped":
                pos_dist_include_skipped.update(v)
            elif k == "setpos":
                pos_dist_setpos.update(v)
            elif k == "raw_pos":
                pos_dist_raw_pos.update(v)
            elif k == "chunk":
                pos_dist_chunk.update(v)

    # Feature catalog with Phase-0 comprehensive metadata
    all_candidate_features = [
        "pattern@raw_pos",
        "token@raw_pos",
        "token@chunk",
        "token@spacebefore",
        "exception@spacebefore",
        "pattern:and",
        "pattern:or",
        "phrase_definition",
        "phrase_reference",
        "token@skip",
        "token@min",
        "token@max",
        "exception@scope=current",
        "exception@scope=previous",
        "exception@scope=next",
        "antipattern_rule_level",
        "antipattern_rulegroup_inherited",
        "token_level_match",
        "message_suggestion_match",
        "match@case_conversion",
        "match@include_skipped",
        "match@regexp_match",
        "match@regexp_replace",
        "match@postag",
        "match@postag_regexp",
        "match@postag_replace",
        "match@setpos",
        "static_lemma_match",
        "rule@minprevmatches",
        "rule@distancetokens",
        "rulegroup@minprevmatches",
        "rulegroup@distancetokens",
    ]

    descriptors = {
        "pattern@raw_pos": '<pattern raw_pos="yes">',
        "token@raw_pos": '<token raw_pos="yes">',
        "token@chunk": '<token chunk="...">',
        "token@spacebefore": '<token spacebefore="no|yes">',
        "exception@spacebefore": '<exception spacebefore="no">',
        "pattern:and": '<and><token .../><token .../></and>',
        "pattern:or": '<or><token .../><token .../></or>',
        "phrase_definition": '<phrase id="...">',
        "phrase_reference": '<phraseref idref="...">',
        "token@skip": '<token skip="N">',
        "token@min": '<token min="0|1|2">',
        "token@max": '<token max="1|2|3|4">',
        "exception@scope=current": '<exception>...</exception> (implicit default scope)',
        "exception@scope=previous": '<exception scope="previous">...</exception>',
        "exception@scope=next": '<exception scope="next">...</exception>',
        "antipattern_rule_level": '<rule><antipattern>...</antipattern>...</rule>',
        "antipattern_rulegroup_inherited": '<rulegroup><antipattern>...</antipattern><rule>...</rule></rulegroup>',
        "token_level_match": '<token><match no="0"/></token>',
        "message_suggestion_match": '<message>...<match no="1"/>...</message>',
        "match@case_conversion": '<match no="1" case_conversion="startlower|startupper|alllower|firstupper"/>',
        "match@include_skipped": '<match no="1" include_skipped="all|none"/>',
        "match@regexp_match": '<match no="1" regexp_match="regex"/>',
        "match@regexp_replace": '<match no="1" regexp_replace="repl"/>',
        "match@postag": '<match no="1" postag="POS"/>',
        "match@postag_regexp": '<match no="1" postag_regexp="yes"/>',
        "match@postag_replace": '<match no="1" postag_replace="REPL"/>',
        "match@setpos": '<match no="1" setpos="yes"/>',
        "static_lemma_match": '<match no="1">lemma</match>',
        "rule@minprevmatches": '<rule minprevmatches="N">',
        "rule@distancetokens": '<rule distancetokens="N">',
        "rulegroup@minprevmatches": '<rulegroup minprevmatches="N">',
        "rulegroup@distancetokens": '<rulegroup distancetokens="N">',
    }

    # Map raw XML occurrence numbers
    raw_attr_counts = raw_xml_totals["attribute_counts"]
    raw_tag_counts = raw_xml_totals["tag_counts"]
    raw_attr_dists = raw_xml_totals["attribute_distributions"]

    feature_summary: Dict[str, Any] = {}
    for feat in all_candidate_features:
        rules_set = feature_source_rules.get(feat, set())
        raw_occ = 0
        eff_occ = 0
        raw_dist = None
        pos_occ = feature_positive_occurrences.get(feat, 0)
        pos_dist = None

        if feat == "pattern@raw_pos":
            raw_occ = raw_attr_counts.get("pattern@raw_pos", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("pattern@raw_pos", {})
            pos_dist = dict(sorted(pos_dist_raw_pos.items()))
        elif feat == "token@raw_pos":
            raw_occ = raw_attr_counts.get("token@raw_pos", 0)
            eff_occ = raw_occ
        elif feat == "token@chunk":
            raw_occ = raw_attr_counts.get("token@chunk", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("token@chunk", {})
            pos_dist = dict(sorted(pos_dist_chunk.items()))
        elif feat == "token@spacebefore":
            raw_occ = raw_attr_counts.get("token@spacebefore", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("token@spacebefore", {})
            pos_dist = dict(sorted(pos_dist_spacebefore.items()))
        elif feat == "exception@spacebefore":
            raw_occ = raw_attr_counts.get("exception@spacebefore", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("exception@spacebefore", {})
            pos_dist = dict(sorted(pos_dist_exc_spacebefore.items()))
        elif feat == "pattern:and":
            raw_occ = raw_tag_counts.get("and", 0)
            eff_occ = raw_occ
        elif feat == "pattern:or":
            raw_occ = raw_tag_counts.get("or", 0)
            eff_occ = raw_occ
        elif feat == "phrase_definition":
            raw_occ = raw_tag_counts.get("phrase", 0)
            eff_occ = raw_occ
        elif feat == "phrase_reference":
            raw_occ = raw_tag_counts.get("phraseref", 0)
            eff_occ = raw_occ
        elif feat == "token@skip":
            raw_occ = raw_attr_counts.get("token@skip", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("token@skip", {})
            pos_dist = dict(sorted(pos_dist_skip.items()))
        elif feat == "token@min":
            raw_occ = raw_attr_counts.get("token@min", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("token@min", {})
            pos_dist = dict(sorted(pos_dist_min.items()))
        elif feat == "token@max":
            raw_occ = raw_attr_counts.get("token@max", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("token@max", {})
            pos_dist = dict(sorted(pos_dist_max.items()))
        elif feat == "exception@scope=current":
            raw_occ = 0
            eff_occ = raw_xml_totals["exception_scope_summary"]["implicit_scope_raw_occurrences"]
        elif feat == "exception@scope=previous":
            raw_occ = raw_xml_totals["exception_scope_summary"]["explicit_scope_distribution"].get("previous", 0)
            eff_occ = raw_occ
        elif feat == "exception@scope=next":
            raw_occ = raw_xml_totals["exception_scope_summary"]["explicit_scope_distribution"].get("next", 0)
            eff_occ = raw_occ
        elif feat == "antipattern_rule_level":
            raw_occ = raw_xml_totals["antipattern_summary"]["raw_rule_antipattern_elements"]
            eff_occ = raw_occ
        elif feat == "antipattern_rulegroup_inherited":
            raw_occ = raw_xml_totals["antipattern_summary"]["raw_rulegroup_antipattern_elements"]
            eff_occ = effective_inherited_antipattern_apps
        elif feat == "token_level_match":
            raw_occ = raw_xml_totals["match_context_summary"]["token_level_matches"]
            eff_occ = raw_occ
        elif feat == "message_suggestion_match":
            raw_occ = raw_xml_totals["match_context_summary"]["message_suggestion_matches"]
            eff_occ = raw_occ
        elif feat == "match@case_conversion":
            raw_occ = raw_attr_counts.get("match@case_conversion", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("match@case_conversion", {})
            pos_dist = dict(sorted(pos_dist_case_conv.items()))
        elif feat == "match@include_skipped":
            raw_occ = raw_attr_counts.get("match@include_skipped", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("match@include_skipped", {})
            pos_dist = dict(sorted(pos_dist_include_skipped.items()))
        elif feat == "match@regexp_match":
            raw_occ = raw_attr_counts.get("match@regexp_match", 0)
            eff_occ = raw_occ
        elif feat == "match@regexp_replace":
            raw_occ = raw_attr_counts.get("match@regexp_replace", 0)
            eff_occ = raw_occ
        elif feat == "match@postag":
            raw_occ = raw_attr_counts.get("match@postag", 0)
            eff_occ = raw_occ
        elif feat == "match@postag_regexp":
            raw_occ = raw_attr_counts.get("match@postag_regexp", 0)
            eff_occ = raw_occ
        elif feat == "match@postag_replace":
            raw_occ = raw_attr_counts.get("match@postag_replace", 0)
            eff_occ = raw_occ
        elif feat == "match@setpos":
            raw_occ = raw_attr_counts.get("match@setpos", 0)
            eff_occ = raw_occ
            raw_dist = raw_attr_dists.get("match@setpos", {})
            pos_dist = dict(sorted(pos_dist_setpos.items()))
        elif feat == "static_lemma_match":
            raw_occ = raw_xml_totals["match_context_summary"]["static_lemma_matches"]
            eff_occ = raw_occ
        elif feat == "rule@minprevmatches":
            raw_occ = raw_attr_counts.get("rule@minprevmatches", 0)
            eff_occ = raw_occ
        elif feat == "rule@distancetokens":
            raw_occ = raw_attr_counts.get("rule@distancetokens", 0)
            eff_occ = raw_occ
        elif feat == "rulegroup@minprevmatches":
            raw_occ = raw_attr_counts.get("rulegroup@minprevmatches", 0)
            eff_occ = raw_occ
        elif feat == "rulegroup@distancetokens":
            raw_occ = raw_attr_counts.get("rulegroup@distancetokens", 0)
            eff_occ = raw_occ

        # Overlap with other advanced features and remaining blocker tasks/features
        overlap_adv: Counter = Counter()
        overlap_tasks: Counter = Counter()
        overlap_blocker_feats: Counter = Counter()
        state_dist: Counter = Counter()

        for r in rules_records:
            if r["full_id"] in rules_set:
                state_dist[r["task_0008_state"]] += 1
                for other_feat in r["feature_usage"]:
                    if other_feat != feat and other_feat in all_candidate_features:
                        overlap_adv[other_feat] += 1
                for blk in r["remaining_blockers_after_0008"]:
                    overlap_tasks[blk["target_task"]] += 1
                    overlap_blocker_feats[blk["feature"]] += 1

        entry: Dict[str, Any] = {
            "raw_xml_occurrences": raw_occ,
            "effective_occurrences": eff_occ,
            "source_rules_count": len(rules_set),
            "positive_pattern_occurrences": pos_occ,
            "representative_descriptor": descriptors.get(feat, feat),
            "representative_rules": feature_representative_rules.get(feat, []),
            "embedded_examples_count": dict(feature_examples_counts[feat]),
            "overlap_with_advanced_features": dict(sorted(overlap_adv.items())),
            "remaining_blocker_target_tasks": dict(sorted(overlap_tasks.items())),
            "remaining_blocker_features": dict(sorted(overlap_blocker_feats.items())),
            "execution_state_distribution": dict(sorted(state_dist.items())),
        }
        if raw_dist is not None:
            entry["raw_value_distribution"] = raw_dist
        if pos_dist is not None:
            entry["positive_pattern_value_distribution"] = pos_dist
        if feat == "antipattern_rulegroup_inherited":
            entry["effective_inherited_applications"] = effective_inherited_antipattern_apps

        feature_summary[feat] = entry

    # Load manifest-bound Java loader expansion evidence
    java_loader_data = load_trusted_java_variant_evidence()

    # Summary of runtime examples by runnable vs deferred state (GrammarLoader semantics)
    runnable_tot = examples_by_state["CORE_0007_RUNNABLE"]["total"] + examples_by_state["ADVANCED_0008_RUNNABLE"]["total"]
    runnable_inc = examples_by_state["CORE_0007_RUNNABLE"]["incorrect"] + examples_by_state["ADVANCED_0008_RUNNABLE"]["incorrect"]
    runnable_corr = examples_by_state["CORE_0007_RUNNABLE"]["correct"] + examples_by_state["ADVANCED_0008_RUNNABLE"]["correct"]
    runnable_corr_pres = examples_by_state["CORE_0007_RUNNABLE"]["correction_attribute_present"] + examples_by_state["ADVANCED_0008_RUNNABLE"]["correction_attribute_present"]
    runnable_corr_nonempty = examples_by_state["CORE_0007_RUNNABLE"]["correction_value_non_empty"] + examples_by_state["ADVANCED_0008_RUNNABLE"]["correction_value_non_empty"]
    runnable_corr_empty = examples_by_state["CORE_0007_RUNNABLE"]["correction_value_empty"] + examples_by_state["ADVANCED_0008_RUNNABLE"]["correction_value_empty"]

    def_states = ["DEFERRED_0009_UNIFICATION", "DEFERRED_0010_FILTER", "DEFERRED_0012_SPELLING_OR_SUPPRESSION", "MULTI_BLOCKER"]
    deferred_tot = sum(examples_by_state[s]["total"] for s in def_states)
    deferred_inc = sum(examples_by_state[s]["incorrect"] for s in def_states)
    deferred_corr = sum(examples_by_state[s]["correct"] for s in def_states)
    deferred_corr_pres = sum(examples_by_state[s]["correction_attribute_present"] for s in def_states)
    deferred_corr_nonempty = sum(examples_by_state[s]["correction_value_non_empty"] for s in def_states)
    deferred_corr_empty = sum(examples_by_state[s]["correction_value_empty"] for s in def_states)

    all_rules_inc = sum(examples_by_state[s]["incorrect"] for s in examples_by_state)
    all_rules_corr = sum(examples_by_state[s]["correct"] for s in examples_by_state)
    all_corr_pres = sum(examples_by_state[s]["correction_attribute_present"] for s in examples_by_state)
    all_corr_nonempty = sum(examples_by_state[s]["correction_value_non_empty"] for s in examples_by_state)
    all_corr_empty = sum(examples_by_state[s]["correction_value_empty"] for s in examples_by_state)

    core_0007_count = classification_counts["CORE_0007_RUNNABLE"]
    advanced_0008_count = classification_counts["ADVANCED_0008_RUNNABLE"]
    deferred_0009_count = classification_counts["DEFERRED_0009_UNIFICATION"]
    deferred_0010_count = classification_counts["DEFERRED_0010_FILTER"]
    deferred_0012_count = classification_counts["DEFERRED_0012_SPELLING_OR_SUPPRESSION"]
    multi_blocker_count = classification_counts["MULTI_BLOCKER"]
    unknown_count = classification_counts["UNKNOWN"]

    baseline_0007_counts = Counter(core_rule_states.values())

    return {
        "schema_version": "1.0.0",
        "provenance": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "grammar_xml_path": "third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml",
            "grammar_xml_size_bytes": xml_size,
            "grammar_xml_sha256": xml_sha256,
            "baseline_task_0007_commit": BASELINE_0007_COMMIT,
            "generator_path": "tools/russian_grammar_advanced_inventory.py",
            "generator_sha256": generator_sha256,
        },
        "source_totals": {
            "categories": len(categories),
            "rulegroups": len(rulegroups),
            "source_rule_elements": len(all_rules),
            "embedded_examples_total": total_rule_examples_count,
        },
        "baseline_task_0007": {
            "CORE_0007_RUNNABLE": baseline_0007_counts.get("CORE_0007_RUNNABLE", 0),
            "DEFERRED_0008_ADVANCED_MATCHING": baseline_0007_counts.get("DEFERRED_0008_ADVANCED_MATCHING", 0),
            "DEFERRED_0009_UNIFICATION": baseline_0007_counts.get("DEFERRED_0009_UNIFICATION", 0),
            "DEFERRED_0010_FILTER": baseline_0007_counts.get("DEFERRED_0010_FILTER", 0),
            "MULTI_BLOCKER": baseline_0007_counts.get("MULTI_BLOCKER", 0),
            "UNRECOGNIZED": baseline_0007_counts.get("UNRECOGNIZED", 0),
        },
        "task_0007_to_0008_transitions": dict(sorted(task_0007_to_0008_transitions.items())),
        "blocker_combinations": dict(sorted(blocker_combinations_counter.items())),
        "raw_xml_totals": raw_xml_totals,
        "classification_summary": {
            "CORE_0007_RUNNABLE": core_0007_count,
            "ADVANCED_0008_RUNNABLE": advanced_0008_count,
            "TOTAL_0007_0008_RUNNABLE": core_0007_count + advanced_0008_count,
            "DEFERRED_0009_UNIFICATION": deferred_0009_count,
            "DEFERRED_0010_FILTER": deferred_0010_count,
            "DEFERRED_0012_SPELLING_OR_SUPPRESSION": deferred_0012_count,
            "MULTI_BLOCKER": multi_blocker_count,
            "UNKNOWN": unknown_count,
        },
        "examples_summary": {
            "runtime_classification": {
                "runnable_0007_0008_total": runnable_tot,
                "runnable_0007_0008_incorrect": runnable_inc,
                "runnable_0007_0008_correct": runnable_corr,
                "runnable_correction_attribute_present": runnable_corr_pres,
                "runnable_correction_value_non_empty": runnable_corr_nonempty,
                "runnable_correction_value_empty": runnable_corr_empty,
                "deferred_total": deferred_tot,
                "deferred_incorrect": deferred_inc,
                "deferred_correct": deferred_corr,
                "deferred_correction_attribute_present": deferred_corr_pres,
                "deferred_correction_value_non_empty": deferred_corr_nonempty,
                "deferred_correction_value_empty": deferred_corr_empty,
                "all_rules_examples_total": total_rule_examples_count,
                "all_rules_examples_incorrect": all_rules_inc,
                "all_rules_examples_correct": all_rules_corr,
                "all_rules_correction_attribute_present": all_corr_pres,
                "all_rules_correction_value_non_empty": all_corr_nonempty,
                "all_rules_correction_value_empty": all_corr_empty,
                "by_state": {k: dict(v) for k, v in sorted(examples_by_state.items())},
            },
            "raw_markup_error_like_examples": {
                "total_examples": raw_xml_totals["raw_examples_summary"]["total_examples"],
                "markup_error_like_examples": raw_xml_totals["raw_examples_summary"]["markup_error_like_examples"],
                "markup_untouched_or_correct_examples": raw_xml_totals["raw_examples_summary"]["markup_untouched_or_correct_examples"],
                "correction_attribute_present": raw_xml_totals["raw_examples_summary"]["correction_attribute_present"],
                "correction_value_non_empty": raw_xml_totals["raw_examples_summary"]["correction_value_non_empty"],
                "correction_value_empty": raw_xml_totals["raw_examples_summary"]["correction_value_empty"],
            },
            "runnable_0007_0008_total": runnable_tot,
            "runnable_0007_0008_incorrect": runnable_inc,
            "runnable_0007_0008_correct": runnable_corr,
            "deferred_total": deferred_tot,
            "deferred_incorrect": deferred_inc,
            "deferred_correct": deferred_corr,
            "all_rules_examples_total": total_rule_examples_count,
            "all_rules_examples_incorrect": all_rules_inc,
            "all_rules_examples_correct": all_rules_corr,
            "correction_attribute_present": all_corr_pres,
            "correction_value_non_empty": all_corr_nonempty,
            "correction_value_empty": all_corr_empty,
            "by_state": {k: dict(v) for k, v in sorted(examples_by_state.items())},
        },
        "feature_summary": feature_summary,
        "antipattern_details": {
            "raw_rule_antipattern_elements": raw_xml_totals["antipattern_summary"]["raw_rule_antipattern_elements"],
            "raw_rulegroup_antipattern_elements": raw_xml_totals["antipattern_summary"]["raw_rulegroup_antipattern_elements"],
            "raw_total_antipattern_elements": raw_xml_totals["antipattern_summary"]["raw_total_antipattern_elements"],
            "source_rules_with_direct_antipatterns_count": len(rules_with_direct_antipatterns),
            "source_rules_with_inherited_antipatterns_count": len(rules_with_inherited_antipatterns),
            "source_rules_with_any_antipatterns_count": len(rules_with_direct_antipatterns | rules_with_inherited_antipatterns),
            "effective_inherited_applications": effective_inherited_antipattern_apps,
        },
        "java_loader_expansion": java_loader_data,
        "rules": rules_records,
    }


def _analyze_single_rule(
    r_elem: ET.Element,
    full_id: str,
    rule_id: Optional[str],
    sub_id: str,
    name: str,
    category_id: str,
    category_name: str,
    rulegroup_id: Optional[str],
    rulegroup_name: Optional[str],
    default_off: bool,
    source_order: int,
    parent_antipatterns: List[ET.Element],
    parent_minprevmatches: Optional[str],
    parent_distancetokens: Optional[str],
    core_state: str,
    core_blockers: List[Dict[str, str]],
) -> Dict[str, Any]:
    """Inspect XML structure of a rule and compute its positive feature usage, blockers, and transition."""
    feature_usage: Set[str] = set()
    positive_feature_counts: Counter = Counter()
    attr_counts: Dict[str, Counter] = defaultdict(Counter)

    # 1. Rule & Rulegroup modifiers
    if r_elem.attrib.get("minprevmatches"):
        feature_usage.add("rule@minprevmatches")
        positive_feature_counts["rule@minprevmatches"] += 1
    if r_elem.attrib.get("distancetokens"):
        feature_usage.add("rule@distancetokens")
        positive_feature_counts["rule@distancetokens"] += 1
    if parent_minprevmatches:
        feature_usage.add("rulegroup@minprevmatches")
        positive_feature_counts["rulegroup@minprevmatches"] += 1
    if parent_distancetokens:
        feature_usage.add("rulegroup@distancetokens")
        positive_feature_counts["rulegroup@distancetokens"] += 1

    # 2. Antipatterns
    rule_antipatterns = r_elem.findall("antipattern")
    if rule_antipatterns:
        feature_usage.add("antipattern_rule_level")
        positive_feature_counts["antipattern_rule_level"] += len(rule_antipatterns)
    if parent_antipatterns:
        feature_usage.add("antipattern_rulegroup_inherited")
        positive_feature_counts["antipattern_rulegroup_inherited"] += len(parent_antipatterns)

    # 3. Patterns (positive patterns)
    patterns = r_elem.findall("pattern")
    for pat in patterns:
        if pat.attrib.get("raw_pos") == "yes":
            feature_usage.add("pattern@raw_pos")
            positive_feature_counts["pattern@raw_pos"] += 1
            attr_counts["raw_pos"]["yes"] += 1

        and_elems = pat.findall(".//and")
        if and_elems:
            feature_usage.add("pattern:and")
            positive_feature_counts["pattern:and"] += len(and_elems)

        or_elems = pat.findall(".//or")
        if or_elems:
            feature_usage.add("pattern:or")
            positive_feature_counts["pattern:or"] += len(or_elems)

        unify_elems = pat.findall(".//unify")
        if unify_elems:
            feature_usage.add("pattern:unify")
            positive_feature_counts["pattern:unify"] += len(unify_elems)

        unify_ignore_elems = pat.findall(".//unify-ignore")
        if unify_ignore_elems:
            feature_usage.add("pattern:unify-ignore")
            positive_feature_counts["pattern:unify-ignore"] += len(unify_ignore_elems)

        for phr in pat.findall(".//phrase"):
            if "id" in phr.attrib:
                feature_usage.add("phrase_definition")
                positive_feature_counts["phrase_definition"] += 1
            if "ref" in phr.attrib or "idref" in phr.attrib:
                feature_usage.add("phrase_reference")
                positive_feature_counts["phrase_reference"] += 1

        for phr in pat.findall(".//phraseref"):
            if "idref" in phr.attrib or "ref" in phr.attrib:
                feature_usage.add("phrase_reference")
                positive_feature_counts["phrase_reference"] += 1

        for tok in pat.findall(".//token"):
            if "raw_pos" in tok.attrib:
                feature_usage.add("token@raw_pos")
                positive_feature_counts["token@raw_pos"] += 1
                attr_counts["raw_pos"][tok.attrib["raw_pos"]] += 1
            if "skip" in tok.attrib:
                feature_usage.add("token@skip")
                positive_feature_counts["token@skip"] += 1
                attr_counts["skip"][tok.attrib["skip"]] += 1
            if "min" in tok.attrib:
                feature_usage.add("token@min")
                positive_feature_counts["token@min"] += 1
                attr_counts["min"][tok.attrib["min"]] += 1
            if "max" in tok.attrib:
                feature_usage.add("token@max")
                positive_feature_counts["token@max"] += 1
                attr_counts["max"][tok.attrib["max"]] += 1
            if "spacebefore" in tok.attrib:
                feature_usage.add("token@spacebefore")
                positive_feature_counts["token@spacebefore"] += 1
                attr_counts["spacebefore"][tok.attrib["spacebefore"]] += 1
            if "chunk" in tok.attrib:
                feature_usage.add("token@chunk")
                positive_feature_counts["token@chunk"] += 1
                attr_counts["chunk"][tok.attrib["chunk"]] += 1

            tok_matches = tok.findall("match")
            if tok_matches:
                feature_usage.add("token_level_match")
                positive_feature_counts["token_level_match"] += len(tok_matches)

            for exc in tok.findall("exception"):
                scope = exc.attrib.get("scope", "current")
                feature_usage.add(f"exception@scope={scope}")
                positive_feature_counts[f"exception@scope={scope}"] += 1
                attr_counts["exc_scope"][scope] += 1
                if "spacebefore" in exc.attrib:
                    feature_usage.add("exception@spacebefore")
                    positive_feature_counts["exception@spacebefore"] += 1
                    attr_counts["exc_spacebefore"][exc.attrib["spacebefore"]] += 1

    # 4. Message and Suggestion <match> elements (non-overlapping physical node walk)
    unique_rule_matches = list(r_elem.iter("match"))
    if unique_rule_matches:
        feature_usage.add("message_suggestion_match")
        positive_feature_counts["message_suggestion_match"] += len(unique_rule_matches)

    for match in unique_rule_matches:
        if match.text and match.text.strip():
            feature_usage.add("static_lemma_match")
            positive_feature_counts["static_lemma_match"] += 1
        for attr, val in match.attrib.items():
            if attr == "case_conversion":
                feature_usage.add("match@case_conversion")
                positive_feature_counts["match@case_conversion"] += 1
                attr_counts["case_conversion"][val] += 1
            elif attr == "include_skipped":
                feature_usage.add("match@include_skipped")
                positive_feature_counts["match@include_skipped"] += 1
                attr_counts["include_skipped"][val] += 1
            elif attr == "regexp_match":
                feature_usage.add("match@regexp_match")
                positive_feature_counts["match@regexp_match"] += 1
            elif attr == "regexp_replace":
                feature_usage.add("match@regexp_replace")
                positive_feature_counts["match@regexp_replace"] += 1
            elif attr == "postag":
                feature_usage.add("match@postag")
                positive_feature_counts["match@postag"] += 1
            elif attr == "postag_regexp":
                feature_usage.add("match@postag_regexp")
                positive_feature_counts["match@postag_regexp"] += 1
            elif attr == "postag_replace":
                feature_usage.add("match@postag_replace")
                positive_feature_counts["match@postag_replace"] += 1
            elif attr == "setpos":
                feature_usage.add("match@setpos")
                positive_feature_counts["match@setpos"] += 1
                attr_counts["setpos"][val] += 1

    # 5. Filters
    filter_elements = r_elem.findall("filter")
    for filt in filter_elements:
        cls_name = filt.attrib.get("class", "unknown")
        feature_usage.add(f"filter:{cls_name}")
        positive_feature_counts[f"filter:{cls_name}"] += 1

    # 6. Spelling / suppress misspelled
    if any(m.attrib.get("suppress_misspelled") == "yes" for m in r_elem.findall("message")):
        feature_usage.add("message@suppress_misspelled")
        positive_feature_counts["message@suppress_misspelled"] += 1
    if any(s.attrib.get("suppress_misspelled") == "yes" for s in r_elem.findall(".//suggestion")):
        feature_usage.add("suggestion@suppress_misspelled")
        positive_feature_counts["suggestion@suppress_misspelled"] += 1

    # 7. Examples classification matching runtime GrammarLoader semantics
    examples = r_elem.findall("example")
    incorrect_cnt = 0
    correct_cnt = 0
    corr_pres_cnt = 0
    corr_nonempty_cnt = 0
    corr_empty_cnt = 0

    for ex in examples:
        is_inc, c_pres, c_nonempty, c_empty = classify_runtime_example(ex)
        if is_inc:
            incorrect_cnt += 1
        else:
            correct_cnt += 1
        if c_pres:
            corr_pres_cnt += 1
        if c_nonempty:
            corr_nonempty_cnt += 1
        if c_empty:
            corr_empty_cnt += 1

    examples_count = {
        "total": len(examples),
        "incorrect": incorrect_cnt,
        "correct": correct_cnt,
        "correction_attribute_present": corr_pres_cnt,
        "correction_value_non_empty": corr_nonempty_cnt,
        "correction_value_empty": corr_empty_cnt,
    }

    # 8. Blocker Analysis & Transition
    remaining_blockers: List[Dict[str, str]] = []
    removed_blockers: List[Dict[str, str]] = []

    # Check remaining Task 0009 Unification blockers
    if "pattern:unify" in feature_usage or "pattern:unify-ignore" in feature_usage:
        remaining_blockers.append({
            "feature": "pattern:unify",
            "target_task": "0009",
            "description": "Unification construct in pattern",
        })

    # Check remaining Task 0010 Filter blockers
    for feat in feature_usage:
        if feat.startswith("filter:"):
            cls_name = feat.split(":", 1)[1]
            remaining_blockers.append({
                "feature": f"filter:{cls_name}",
                "target_task": "0010",
                "description": f"Custom filter class {cls_name}",
            })

    # Check remaining Task 0012 Spelling/Suppression blockers
    if "message@suppress_misspelled" in feature_usage:
        remaining_blockers.append({
            "feature": "message@suppress_misspelled",
            "target_task": "0012",
            "description": "Message suppress_misspelled attribute",
        })
    if "suggestion@suppress_misspelled" in feature_usage:
        remaining_blockers.append({
            "feature": "suggestion@suppress_misspelled",
            "target_task": "0012",
            "description": "Suggestion suppress_misspelled attribute",
        })

    # Check which old blockers from 0007 were removed by 0008
    for b in core_blockers:
        feat = b["feature"]
        if b["target_task"] == "0008" or (b["target_task"] == "0010" and feat.startswith("match@")):
            removed_blockers.append(b)

    # Determine post-0008 execution state
    if not remaining_blockers:
        if core_state == "CORE_0007_RUNNABLE":
            task_0008_state = "CORE_0007_RUNNABLE"
        else:
            task_0008_state = "ADVANCED_0008_RUNNABLE"
    else:
        tasks = {b["target_task"] for b in remaining_blockers}
        if len(tasks) > 1:
            task_0008_state = "MULTI_BLOCKER"
        elif "0009" in tasks:
            task_0008_state = "DEFERRED_0009_UNIFICATION"
        elif "0010" in tasks:
            task_0008_state = "DEFERRED_0010_FILTER"
        elif "0012" in tasks:
            task_0008_state = "DEFERRED_0012_SPELLING_OR_SUPPRESSION"
        else:
            task_0008_state = "UNKNOWN"

    return {
        "full_id": full_id,
        "rule_id": rule_id,
        "sub_id": sub_id,
        "source_order": source_order,
        "name": name,
        "category_id": category_id,
        "category_name": category_name,
        "rulegroup_id": rulegroup_id,
        "rulegroup_name": rulegroup_name,
        "default_off": default_off,
        "task_0007_state": core_state,
        "task_0008_state": task_0008_state,
        "task_0007_blockers": core_blockers,
        "blockers_removed_by_0008": removed_blockers,
        "remaining_blockers_after_0008": remaining_blockers,
        "feature_usage": sorted(list(feature_usage)),
        "positive_feature_counts": dict(positive_feature_counts),
        "examples_count": examples_count,
        "attribute_counts": {k: dict(v) for k, v in attr_counts.items()},
    }


def main() -> None:
    print("Generating LanguageTool Russian Advanced Grammar Inventory...")
    inv = generate_advanced_inventory()

    ADVANCED_INVENTORY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_text = json.dumps(inv, indent=2, ensure_ascii=False) + "\n"
    ADVANCED_INVENTORY_OUTPUT_PATH.write_text(out_text, encoding="utf-8")

    print(f"Wrote advanced inventory to {ADVANCED_INVENTORY_OUTPUT_PATH}")
    print("\nSummary of Task 0008 Rule Classification:")
    for k, v in inv["classification_summary"].items():
        print(f"  {k:35s}: {v:4d}")
    print("\nSummary of Example Counts (Runtime):")
    rt = inv["examples_summary"]["runtime_classification"]
    for k, v in rt.items():
        if isinstance(v, int):
            print(f"  {k:35s}: {v:4d}")
    print("\nSummary of Example Counts (Raw Markup Error-Like):")
    mk = inv["examples_summary"]["raw_markup_error_like_examples"]
    for k, v in mk.items():
        if isinstance(v, int):
            print(f"  {k:35s}: {v:4d}")
    print("\nJava Loader Expansions:")
    print(f"  Total physical rules: {inv['java_loader_expansion']['total_physical_rules']}")
    print(f"  Rules with >1 variant: {inv['java_loader_expansion']['multi_variant_rules_count']}")


if __name__ == "__main__":
    main()
