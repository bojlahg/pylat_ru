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


def get_oracle_jar_path() -> Optional[Path]:
    """Resolve Java LT oracle JAR path if present."""
    candidate = REPO_ROOT / ".oracle_cache" / f"LanguageTool-{PINNED_LT_VERSION}" / "languagetool-commandline.jar"
    if candidate.is_file():
        return candidate
    return None


def run_java_loader_inventory(jar_path: Path) -> Dict[str, Any]:
    """Execute Java PatternRuleLoader over grammar.xml to extract physical variant expansions."""
    java_src = """import org.languagetool.rules.patterns.PatternRuleLoader;
import org.languagetool.rules.patterns.AbstractPatternRule;
import org.languagetool.rules.patterns.PatternRule;
import org.languagetool.language.Russian;
import java.io.InputStream;
import java.util.*;

public class AdvancedLoaderInventory {
    public static void main(String[] args) throws Exception {
        Russian russian = Russian.getInstance();
        PatternRuleLoader loader = new PatternRuleLoader();
        InputStream is = Russian.class.getResourceAsStream("/org/languagetool/rules/ru/grammar.xml");
        List<AbstractPatternRule> rules = loader.getRules(is, "/org/languagetool/rules/ru/grammar.xml", russian);
        
        System.out.println("TOTAL_PHYSICAL_RULES=" + rules.size());
        
        Map<String, List<AbstractPatternRule>> byFullId = new LinkedHashMap<>();
        for (AbstractPatternRule r : rules) {
            byFullId.computeIfAbsent(r.getFullId(), k -> new ArrayList<>()).add(r);
        }
        
        System.out.println("UNIQUE_FULL_IDS=" + byFullId.size());
        
        int multiVariantSourceRules = 0;
        int maxVariants = 1;
        Map<String, Integer> variantCounts = new LinkedHashMap<>();
        
        for (Map.Entry<String, List<AbstractPatternRule>> e : byFullId.entrySet()) {
            int count = e.getValue().size();
            variantCounts.put(e.getKey(), count);
            if (count > 1) {
                multiVariantSourceRules++;
                if (count > maxVariants) {
                    maxVariants = count;
                }
                System.out.println("EXPANDED=" + e.getKey() + "=" + count);
            }
        }
        System.out.println("MULTI_VARIANT_RULES=" + multiVariantSourceRules);
        System.out.println("MAX_VARIANTS_PER_RULE=" + maxVariants);
    }
}
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_file = Path(tmpdir) / "AdvancedLoaderInventory.java"
        src_file.write_text(java_src, encoding="utf-8")
        subprocess.run(
            ["javac", "-encoding", "UTF-8", "-cp", str(jar_path), str(src_file)],
            check=True,
            capture_output=True,
        )
        proc = subprocess.run(
            [
                "java",
                "-Dfile.encoding=UTF-8",
                "-cp",
                f"{tmpdir}{os.pathsep}{jar_path}",
                "AdvancedLoaderInventory",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        out = proc.stdout
        lines = out.strip().splitlines()
        
        total_physical_rules = 0
        unique_full_ids = 0
        multi_variant_rules = 0
        max_variants = 1
        expanded_rules: Dict[str, int] = {}

        for line in lines:
            if line.startswith("TOTAL_PHYSICAL_RULES="):
                total_physical_rules = int(line.split("=", 1)[1])
            elif line.startswith("UNIQUE_FULL_IDS="):
                unique_full_ids = int(line.split("=", 1)[1])
            elif line.startswith("MULTI_VARIANT_RULES="):
                multi_variant_rules = int(line.split("=", 1)[1])
            elif line.startswith("MAX_VARIANTS_PER_RULE="):
                max_variants = int(line.split("=", 1)[1])
            elif line.startswith("EXPANDED="):
                parts = line.split("=", 2)
                expanded_rules[parts[1]] = int(parts[2])

        return {
            "total_physical_rules": total_physical_rules,
            "unique_full_ids": unique_full_ids,
            "multi_variant_rules_count": multi_variant_rules,
            "max_variants_per_rule": max_variants,
            "expanded_rules": expanded_rules,
        }


def generate_advanced_inventory() -> Dict[str, Any]:
    """Parse grammar.xml and build complete advanced matching inventory."""
    tree = ET.parse(str(GRAMMAR_XML_PATH))
    root = tree.getroot()

    xml_size = GRAMMAR_XML_PATH.stat().st_size
    xml_sha256 = sha256_file(GRAMMAR_XML_PATH)

    # Core historical baseline for comparison
    core_inv_data = json.loads(CORE_INVENTORY_PATH.read_text(encoding="utf-8"))
    core_rules_list = core_inv_data["grammar"]["rules"]
    core_rule_states = {r["full_rule_id"]: r["execution_state"] for r in core_rules_list}
    core_rule_blockers = {r["full_rule_id"]: r["blockers"] for r in core_rules_list}

    # Collect rulegroups and categories
    categories = root.findall("category")
    rulegroups = root.findall(".//rulegroup")
    direct_rules = [r for r in root.findall(".//category/rule")]
    all_rules = root.findall(".//rule")

    assert len(categories) == 8, f"Expected 8 categories, got {len(categories)}"
    assert len(rulegroups) == 297, f"Expected 297 rulegroups, got {len(rulegroups)}"
    assert len(all_rules) == 892, f"Expected 892 rules, got {len(all_rules)}"

    # Feature tracking counters
    feature_source_rules: Dict[str, Set[str]] = defaultdict(set)
    feature_occurrences: Dict[str, int] = defaultdict(int)
    feature_distinct_values: Dict[str, Set[str]] = defaultdict(set)
    feature_representative_rules: Dict[str, List[str]] = defaultdict(list)

    # Value distributions
    dist_skip: Counter = Counter()
    dist_min: Counter = Counter()
    dist_max: Counter = Counter()
    dist_spacebefore: Counter = Counter()
    dist_exc_scope: Counter = Counter()
    dist_exc_spacebefore: Counter = Counter()
    dist_case_conv: Counter = Counter()
    dist_include_skipped: Counter = Counter()
    dist_setpos: Counter = Counter()
    dist_raw_pos: Counter = Counter()
    dist_chunk: Counter = Counter()

    rules_records: List[Dict[str, Any]] = []
    source_order_idx = 0

    runnable_0007_count = 0
    promoted_0008_count = 0
    deferred_0009_count = 0
    deferred_0010_count = 0
    deferred_0012_count = 0
    multi_blocker_count = 0
    unknown_count = 0

    examples_by_state = defaultdict(lambda: {"total": 0, "incorrect": 0, "correct": 0})
    total_examples_count = 0

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
                        sub_id = r_id if r_id else str(rule_num)
                        full_id = f"{group_id}[{sub_id}]"
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
                            core_state=core_rule_states.get(full_id, "UNKNOWN"),
                            core_blockers=core_rule_blockers.get(full_id, []),
                        )
                        rules_records.append(rec)
                        source_order_idx += 1

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
                    core_state=core_rule_states.get(full_id, "UNKNOWN"),
                    core_blockers=core_rule_blockers.get(full_id, []),
                )
                rules_records.append(rec)
                source_order_idx += 1

    # Aggregate global stats
    for r in rules_records:
        st = r["task_0008_state"]
        if st == "CORE_0007_RUNNABLE":
            runnable_0007_count += 1
        elif st == "ADVANCED_0008_RUNNABLE":
            promoted_0008_count += 1
        elif st == "DEFERRED_0009_UNIFICATION":
            deferred_0009_count += 1
        elif st == "DEFERRED_0010_FILTER":
            deferred_0010_count += 1
        elif st == "DEFERRED_0012_SPELLING_OR_SUPPRESSION":
            deferred_0012_count += 1
        elif st == "MULTI_BLOCKER":
            multi_blocker_count += 1
        else:
            unknown_count += 1

        ex_counts = r["examples_count"]
        examples_by_state[st]["total"] += ex_counts["total"]
        examples_by_state[st]["incorrect"] += ex_counts["incorrect"]
        examples_by_state[st]["correct"] += ex_counts["correct"]
        total_examples_count += ex_counts["total"]

        # Aggregate feature usage
        for feat, count in r["feature_counts"].items():
            if count > 0:
                feature_source_rules[feat].add(r["full_id"])
                feature_occurrences[feat] += count
                if len(feature_representative_rules[feat]) < 5 and r["full_id"] not in feature_representative_rules[feat]:
                    feature_representative_rules[feat].append(r["full_id"])

        # Distributions
        for k, v in r["attribute_counts"].items():
            if k == "skip":
                dist_skip.update(v)
            elif k == "min":
                dist_min.update(v)
            elif k == "max":
                dist_max.update(v)
            elif k == "spacebefore":
                dist_spacebefore.update(v)
            elif k == "exc_scope":
                dist_exc_scope.update(v)
            elif k == "exc_spacebefore":
                dist_exc_spacebefore.update(v)
            elif k == "case_conversion":
                dist_case_conv.update(v)
            elif k == "include_skipped":
                dist_include_skipped.update(v)
            elif k == "setpos":
                dist_setpos.update(v)
            elif k == "raw_pos":
                dist_raw_pos.update(v)
            elif k == "chunk":
                dist_chunk.update(v)

    # Feature catalog with exact 0 counts for items not in Russian grammar.xml
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
        "match@setpostag",
        "match@suppress_misspelled",
        "static_lemma_match",
        "rule@minprevmatches",
        "rule@distancetokens",
        "rulegroup@minprevmatches",
        "rulegroup@distancetokens",
    ]

    feature_summary: Dict[str, Any] = {}
    for feat in all_candidate_features:
        rules_set = feature_source_rules.get(feat, set())
        feat_dist = None
        if feat == "token@skip":
            feat_dist = dict(sorted(dist_skip.items()))
        elif feat == "token@min":
            feat_dist = dict(sorted(dist_min.items()))
        elif feat == "token@max":
            feat_dist = dict(sorted(dist_max.items()))
        elif feat == "token@spacebefore":
            feat_dist = dict(sorted(dist_spacebefore.items()))
        elif feat == "exception@spacebefore":
            feat_dist = dict(sorted(dist_exc_spacebefore.items()))
        elif feat == "token@chunk":
            feat_dist = dict(sorted(dist_chunk.items()))
        elif feat == "match@case_conversion":
            feat_dist = dict(sorted(dist_case_conv.items()))
        elif feat == "match@include_skipped":
            feat_dist = dict(sorted(dist_include_skipped.items()))
        elif feat == "match@setpos":
            feat_dist = dict(sorted(dist_setpos.items()))
        elif feat == "pattern@raw_pos":
            feat_dist = dict(sorted(dist_raw_pos.items()))

        entry: Dict[str, Any] = {
            "source_rules_count": len(rules_set),
            "occurrences_count": feature_occurrences.get(feat, 0),
            "representative_rules": feature_representative_rules.get(feat, []),
        }
        if feat_dist is not None:
            entry["value_distribution"] = feat_dist
        feature_summary[feat] = entry

    # Run Java loader inventory if jar exists
    jar_path = get_oracle_jar_path()
    java_loader_data = run_java_loader_inventory(jar_path) if jar_path else {
        "status": "JAVA_ORACLE_NOT_FOUND",
        "total_physical_rules": 0,
        "unique_full_ids": 892,
        "multi_variant_rules_count": 0,
        "max_variants_per_rule": 1,
        "expanded_rules": {},
    }

    inventory = {
        "schema_version": "1.0.0",
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "baseline_task_0007_commit": BASELINE_0007_COMMIT,
            "grammar_xml_path": str(GRAMMAR_XML_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "grammar_xml_size": xml_size,
            "grammar_xml_sha256": xml_sha256,
            "generator_path": "tools/russian_grammar_advanced_inventory.py",
        },
        "source_totals": {
            "categories": len(categories),
            "rulegroups": len(rulegroups),
            "source_rule_elements": len(all_rules),
            "embedded_examples_total": total_examples_count,
        },
        "classification_summary": {
            "CORE_0007_RUNNABLE": runnable_0007_count,
            "ADVANCED_0008_RUNNABLE": promoted_0008_count,
            "TOTAL_0007_0008_RUNNABLE": runnable_0007_count + promoted_0008_count,
            "DEFERRED_0009_UNIFICATION": deferred_0009_count,
            "DEFERRED_0010_FILTER": deferred_0010_count,
            "DEFERRED_0012_SPELLING_OR_SUPPRESSION": deferred_0012_count,
            "MULTI_BLOCKER": multi_blocker_count,
            "UNKNOWN": unknown_count,
        },
        "examples_summary": {
            "runnable_0007_0008_total": examples_by_state["CORE_0007_RUNNABLE"]["total"] + examples_by_state["ADVANCED_0008_RUNNABLE"]["total"],
            "deferred_total": (
                examples_by_state["DEFERRED_0009_UNIFICATION"]["total"]
                + examples_by_state["DEFERRED_0010_FILTER"]["total"]
                + examples_by_state["DEFERRED_0012_SPELLING_OR_SUPPRESSION"]["total"]
                + examples_by_state["MULTI_BLOCKER"]["total"]
            ),
            "by_state": dict(examples_by_state),
        },
        "feature_summary": feature_summary,
        "attribute_distributions": {
            "skip": dict(sorted(dist_skip.items())),
            "min": dict(sorted(dist_min.items())),
            "max": dict(sorted(dist_max.items())),
            "spacebefore": dict(sorted(dist_spacebefore.items())),
            "exception_scope": dict(sorted(dist_exc_scope.items())),
            "exception_spacebefore": dict(sorted(dist_exc_spacebefore.items())),
            "case_conversion": dict(sorted(dist_case_conv.items())),
            "include_skipped": dict(sorted(dist_include_skipped.items())),
            "setpos": dict(sorted(dist_setpos.items())),
            "raw_pos": dict(sorted(dist_raw_pos.items())),
            "chunk": dict(sorted(dist_chunk.items())),
        },
        "java_loader_expansion": java_loader_data,
        "rules": rules_records,
    }

    return inventory


def _analyze_single_rule(
    r_elem: ET.Element,
    full_id: str,
    rule_id: str,
    sub_id: Optional[str],
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
    core_blockers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Inspect XML structure of a rule and compute its feature usage, blockers, and transition."""
    feature_usage: Set[str] = set()
    feature_counts: Counter = Counter()
    attr_counts: Dict[str, Counter] = defaultdict(Counter)

    # 1. Rule & Rulegroup modifiers
    if r_elem.attrib.get("minprevmatches"):
        feature_usage.add("rule@minprevmatches")
        feature_counts["rule@minprevmatches"] += 1
    if r_elem.attrib.get("distancetokens"):
        feature_usage.add("rule@distancetokens")
        feature_counts["rule@distancetokens"] += 1
    if parent_minprevmatches:
        feature_usage.add("rulegroup@minprevmatches")
        feature_counts["rulegroup@minprevmatches"] += 1
    if parent_distancetokens:
        feature_usage.add("rulegroup@distancetokens")
        feature_counts["rulegroup@distancetokens"] += 1

    # 2. Antipatterns
    rule_antipatterns = r_elem.findall("antipattern")
    if rule_antipatterns:
        feature_usage.add("antipattern_rule_level")
        feature_counts["antipattern_rule_level"] += len(rule_antipatterns)
    if parent_antipatterns:
        feature_usage.add("antipattern_rulegroup_inherited")
        feature_counts["antipattern_rulegroup_inherited"] += len(parent_antipatterns)

    # 3. Patterns
    patterns = r_elem.findall("pattern")
    for pat in patterns:
        if pat.attrib.get("raw_pos") == "yes":
            feature_usage.add("pattern@raw_pos")
            feature_counts["pattern@raw_pos"] += 1
            attr_counts["raw_pos"]["yes"] += 1

        and_elems = pat.findall(".//and")
        if and_elems:
            feature_usage.add("pattern:and")
            feature_counts["pattern:and"] += len(and_elems)

        or_elems = pat.findall(".//or")
        if or_elems:
            feature_usage.add("pattern:or")
            feature_counts["pattern:or"] += len(or_elems)

        unify_elems = pat.findall(".//unify")
        if unify_elems:
            feature_usage.add("pattern:unify")
            feature_counts["pattern:unify"] += len(unify_elems)

        unify_ignore_elems = pat.findall(".//unify-ignore")
        if unify_ignore_elems:
            feature_usage.add("pattern:unify-ignore")
            feature_counts["pattern:unify-ignore"] += len(unify_ignore_elems)

        for phr in pat.findall(".//phrase"):
            if "id" in phr.attrib:
                feature_usage.add("phrase_definition")
                feature_counts["phrase_definition"] += 1
            if "ref" in phr.attrib or "idref" in phr.attrib:
                feature_usage.add("phrase_reference")
                feature_counts["phrase_reference"] += 1

        for phr in pat.findall(".//phraseref"):
            if "idref" in phr.attrib or "ref" in phr.attrib:
                feature_usage.add("phrase_reference")
                feature_counts["phrase_reference"] += 1

        for tok in pat.findall(".//token"):
            if "raw_pos" in tok.attrib:
                feature_usage.add("token@raw_pos")
                feature_counts["token@raw_pos"] += 1
                attr_counts["raw_pos"][tok.attrib["raw_pos"]] += 1
            if "skip" in tok.attrib:
                feature_usage.add("token@skip")
                feature_counts["token@skip"] += 1
                attr_counts["skip"][tok.attrib["skip"]] += 1
            if "min" in tok.attrib:
                feature_usage.add("token@min")
                feature_counts["token@min"] += 1
                attr_counts["min"][tok.attrib["min"]] += 1
            if "max" in tok.attrib:
                feature_usage.add("token@max")
                feature_counts["token@max"] += 1
                attr_counts["max"][tok.attrib["max"]] += 1
            if "spacebefore" in tok.attrib:
                feature_usage.add("token@spacebefore")
                feature_counts["token@spacebefore"] += 1
                attr_counts["spacebefore"][tok.attrib["spacebefore"]] += 1
            if "chunk" in tok.attrib:
                feature_usage.add("token@chunk")
                feature_counts["token@chunk"] += 1
                attr_counts["chunk"][tok.attrib["chunk"]] += 1

            tok_matches = tok.findall("match")
            if tok_matches:
                feature_usage.add("token_level_match")
                feature_counts["token_level_match"] += len(tok_matches)

            for exc in tok.findall("exception"):
                scope = exc.attrib.get("scope", "current")
                feature_usage.add(f"exception@scope={scope}")
                feature_counts[f"exception@scope={scope}"] += 1
                attr_counts["exc_scope"][scope] += 1
                if "spacebefore" in exc.attrib:
                    feature_usage.add("exception@spacebefore")
                    feature_counts["exception@spacebefore"] += 1
                    attr_counts["exc_spacebefore"][exc.attrib["spacebefore"]] += 1

    # 4. Message and Suggestion <match> elements
    match_elements = r_elem.findall(".//message//match") + r_elem.findall(".//suggestion//match")
    if match_elements:
        feature_usage.add("message_suggestion_match")
        feature_counts["message_suggestion_match"] += len(match_elements)

    for match in match_elements:
        if match.text and match.text.strip():
            feature_usage.add("static_lemma_match")
            feature_counts["static_lemma_match"] += 1
        for attr, val in match.attrib.items():
            if attr == "case_conversion":
                feature_usage.add("match@case_conversion")
                feature_counts["match@case_conversion"] += 1
                attr_counts["case_conversion"][val] += 1
            elif attr == "include_skipped":
                feature_usage.add("match@include_skipped")
                feature_counts["match@include_skipped"] += 1
                attr_counts["include_skipped"][val] += 1
            elif attr == "regexp_match":
                feature_usage.add("match@regexp_match")
                feature_counts["match@regexp_match"] += 1
            elif attr == "regexp_replace":
                feature_usage.add("match@regexp_replace")
                feature_counts["match@regexp_replace"] += 1
            elif attr == "postag":
                feature_usage.add("match@postag")
                feature_counts["match@postag"] += 1
            elif attr == "postag_regexp":
                feature_usage.add("match@postag_regexp")
                feature_counts["match@postag_regexp"] += 1
            elif attr == "postag_replace":
                feature_usage.add("match@postag_replace")
                feature_counts["match@postag_replace"] += 1
            elif attr == "setpos":
                feature_usage.add("match@setpos")
                feature_counts["match@setpos"] += 1
                attr_counts["setpos"][val] += 1

    # 5. Filters
    filter_elements = r_elem.findall("filter")
    for filt in filter_elements:
        cls_name = filt.attrib.get("class", "unknown")
        feature_usage.add(f"filter:{cls_name}")
        feature_counts[f"filter:{cls_name}"] += 1

    # 6. Spelling / suppress misspelled
    if any(m.attrib.get("suppress_misspelled") == "yes" for m in r_elem.findall("message")):
        feature_usage.add("message@suppress_misspelled")
        feature_counts["message@suppress_misspelled"] += 1
    if any(s.attrib.get("suppress_misspelled") == "yes" for s in r_elem.findall(".//suggestion")):
        feature_usage.add("suggestion@suppress_misspelled")
        feature_counts["suggestion@suppress_misspelled"] += 1

    # 7. Examples
    examples = r_elem.findall("example")
    inc_ex = [e for e in examples if e.attrib.get("type") == "incorrect"]
    corr_ex = [e for e in examples if e.attrib.get("type") != "incorrect"]
    examples_count = {
        "total": len(examples),
        "incorrect": len(inc_ex),
        "correct": len(corr_ex),
    }

    # 8. Blocker Analysis & Task-0008 Transitions
    # Determine which blockers are implemented in 0008 vs remaining
    # Features owned by 0008:
    # - pattern@raw_pos, token@raw_pos, token@skip, token@min_max (min/max), token@spacebefore, token@chunk
    # - pattern:and, pattern:or, phrase, exception@scope=previous, exception@scope=next, exception@spacebefore
    # - antipattern (rule or rulegroup)
    # - match@case_conversion, match@include_skipped, match@regexp_match, match@regexp_replace,
    #   match@postag, match@postag_regexp, match@postag_replace, match@setpos, static lemma match
    # - token_level_match
    # Features remaining for future tasks:
    # - 0009: pattern:unify, pattern:unify-ignore, unification
    # - 0010: filter:* (<filter class="...">)
    # - 0012: message@suppress_misspelled, suggestion@suppress_misspelled

    remaining_blockers: List[Dict[str, str]] = []
    removed_blockers: List[Dict[str, str]] = []

    # Check 0009 unification
    if "pattern:unify" in feature_usage or "pattern:unify-ignore" in feature_usage:
        remaining_blockers.append({
            "feature": "unification",
            "target_task": "0009",
            "description": "<unify> / <unify-ignore> feature agreement",
        })

    # Check 0010 filters
    for filt in filter_elements:
        cls_name = filt.attrib.get("class", "unknown")
        remaining_blockers.append({
            "feature": f"filter:{cls_name}",
            "target_task": "0010",
            "description": f"Java filter class {cls_name}",
        })

    # Check 0012 spelling suppression
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
        "feature_counts": dict(feature_counts),
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
    print("\nSummary of Example Counts:")
    for k, v in inv["examples_summary"].items():
        if k != "by_state":
            print(f"  {k:35s}: {v:4d}")
    print("\nJava Loader Expansions:")
    print(f"  Total physical rules: {inv['java_loader_expansion']['total_physical_rules']}")
    print(f"  Rules with >1 variant: {inv['java_loader_expansion']['multi_variant_rules_count']}")


if __name__ == "__main__":
    main()
