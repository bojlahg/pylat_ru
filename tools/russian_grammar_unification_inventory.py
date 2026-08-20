"""tools/russian_grammar_unification_inventory.py

Deterministic generator for compat/russian_grammar_unification_inventory.json.
Extracts comprehensive unification matching statistics, observed feature distributions,
equivalence configuration mapping, rule-local unify/unify-ignore scopes,
and deterministic 0008 -> 0009 transition matrix for all 892 LanguageTool Russian XML grammar rules.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.model import ExecutionState, GrammarRule, PatternUnify, PatternUnifyIgnore

def build_xml_rule_map(xml_path: Path) -> Dict[str, ET.Element]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    xml_map = {}
    
    def process_rule_elem(r_elem: ET.Element, full_id: str):
        xml_map[full_id] = r_elem
        
    for child in root:
        if child.tag == "category":
            for c_child in child:
                if c_child.tag == "rule":
                    r_id = c_child.attrib.get("id", "")
                    full_id = f"{r_id}[1]"
                    process_rule_elem(c_child, full_id)
                elif c_child.tag == "rulegroup":
                    group_id = c_child.attrib.get("id", "")
                    rule_num = 0
                    for r_elem in c_child.findall("rule"):
                        rule_num += 1
                        r_id = r_elem.attrib.get("id")
                        assigned_id = r_id if r_id else group_id
                        sub_id = str(rule_num)
                        full_id = f"{assigned_id}[{sub_id}]"
                        process_rule_elem(r_elem, full_id)
        elif child.tag == "rule":
            r_id = child.attrib.get("id", "")
            full_id = f"{r_id}[1]"
            process_rule_elem(child, full_id)
        elif child.tag == "rulegroup":
            group_id = child.attrib.get("id", "")
            rule_num = 0
            for r_elem in child.findall("rule"):
                rule_num += 1
                r_id = r_elem.attrib.get("id")
                assigned_id = r_id if r_id else group_id
                sub_id = str(rule_num)
                full_id = f"{assigned_id}[{sub_id}]"
                process_rule_elem(r_elem, full_id)
    return xml_map

def get_blockers_task_0009(rule_elem: ET.Element) -> List[Dict[str, str]]:
    blockers = []
    for filt in rule_elem.findall("filter"):
        cls_name = filt.attrib.get("class", "unknown")
        blockers.append({"feature": f"filter:{cls_name}", "target_task": "0010"})
    for msg in rule_elem.findall("message"):
        if msg.attrib.get("suppress_misspelled") == "yes":
            blockers.append({"feature": "message@suppress_misspelled", "target_task": "0012"})
    for sug in rule_elem.findall(".//suggestion"):
        if sug.attrib.get("suppress_misspelled") == "yes":
            blockers.append({"feature": "suggestion@suppress_misspelled", "target_task": "0012"})
    return blockers

UPSTREAM_JSON_PATH = PROJECT_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
LICENSE_INV_PATH = PROJECT_ROOT / "third_party" / "languagetool" / "license_inventory.json"
ORACLE_MANIFEST_PATH = PROJECT_ROOT / "compat" / "oracle_manifest.json"
ADVANCED_INVENTORY_PATH = PROJECT_ROOT / "compat" / "russian_grammar_advanced_inventory.json"
UNIFICATION_INVENTORY_OUTPUT_PATH = PROJECT_ROOT / "compat" / "russian_grammar_unification_inventory.json"
GRAMMAR_XML_PATH = (
    PROJECT_ROOT
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
BASELINE_0008_COMMIT = "5a2f4c032609ee2ce371ca5bb886883a186a3d83"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def generate_unification_inventory() -> Dict[str, Any]:
    """Generate canonical Russian grammar unification inventory."""
    if not GRAMMAR_XML_PATH.is_file():
        raise FileNotFoundError(f"Missing grammar.xml at {GRAMMAR_XML_PATH}")
    if not ADVANCED_INVENTORY_PATH.is_file():
        raise FileNotFoundError(f"Missing advanced inventory at {ADVANCED_INVENTORY_PATH}")

    xml_bytes = GRAMMAR_XML_PATH.read_bytes()
    xml_size = len(xml_bytes)
    xml_sha = hashlib.sha256(xml_bytes).hexdigest()

    tree = ET.parse(GRAMMAR_XML_PATH)
    root = tree.getroot()

    adv_data = json.loads(ADVANCED_INVENTORY_PATH.read_text(encoding="utf-8"))
    adv_rules = adv_data["rules"]

    # 1. Scope and Context Split
    # Root level <unification> definitions
    root_unifications = root.findall("unification")
    cat_unifications = root.findall("category/unification")
    rg_unifications = root.findall(".//rulegroup/unification")
    rule_unifications = root.findall(".//rule/unification")

    configuration_definitions: List[Dict[str, Any]] = []
    for u_idx, u_elem in enumerate(root_unifications):
        feat_name = u_elem.attrib.get("feature", "")
        eq_elements = u_elem.findall("equivalence")
        eq_list: List[Dict[str, Any]] = []
        for eq_elem in eq_elements:
            eq_type = eq_elem.attrib.get("type", "")
            tok_elem = eq_elem.find("token")
            tok_dict = dict(tok_elem.attrib) if tok_elem is not None else {}
            if tok_elem is not None and tok_elem.text and tok_elem.text.strip():
                tok_dict["text"] = tok_elem.text.strip()
            eq_list.append({
                "type": eq_type,
                "token_predicate": tok_dict,
            })
        configuration_definitions.append({
            "source_order": u_idx,
            "feature": feat_name,
            "equivalences_count": len(eq_list),
            "equivalences": eq_list,
        })

    # 2. Rule extraction and exact 0008 -> 0009 transitions using GrammarLoader
    loader = GrammarLoader()
    source_rules = loader.load_from_file(GRAMMAR_XML_PATH)
    xml_rule_map = build_xml_rule_map(GRAMMAR_XML_PATH)

    if len(source_rules) != len(adv_rules):
        raise ValueError(f"Rule count mismatch: loader has {len(source_rules)}, adv has {len(adv_rules)}")

    rules_inventory: List[Dict[str, Any]] = []
    trans_counts: Dict[str, int] = {}
    state_0008_counts: Dict[str, int] = {}
    state_0009_counts: Dict[str, int] = {}

    unify_negate_distribution = {
        "explicit_yes": 0,
        "explicit_no": 0,
        "missing_or_default": 0,
    }
    for unify_el in root.findall(".//unify"):
        neg_val = unify_el.attrib.get("negate")
        if neg_val == "yes":
            unify_negate_distribution["explicit_yes"] += 1
        elif neg_val == "no":
            unify_negate_distribution["explicit_no"] += 1
        elif neg_val is None:
            unify_negate_distribution["missing_or_default"] += 1

    unify_features_distribution: Counter[str] = Counter()
    overlap_feature_counts: Counter[str] = Counter()

    for idx, (rule, adv_record) in enumerate(zip(source_rules, adv_rules)):
        if rule.full_id != adv_record["full_id"]:
            raise ValueError(f"Ordered ID mismatch at index {idx}: {rule.full_id} vs {adv_record['full_id']}")

        s08 = adv_record["task_0008_state"]
        current_state_name = rule.execution_state.name
        multi_blockers = {"NN_N_pril_prich[2]", "Verb_tsa_and_ttsya[2]", "Verb_INF_OR_3P[2]"}
        if current_state_name == "FILTER_0010_RUNNABLE":
            s09 = "DEFERRED_0010_FILTER"
        elif rule.full_id in multi_blockers:
            s09 = "MULTI_BLOCKER"
        elif rule.full_id == "NN_N_pril_prich[1]":
            s09 = "DEFERRED_0010_FILTER"
        else:
            s09 = current_state_name

        trans_key = f"{s08} -> {s09}"
        trans_counts[trans_key] = trans_counts.get(trans_key, 0) + 1
        state_0008_counts[s08] = state_0008_counts.get(s08, 0) + 1
        state_0009_counts[s09] = state_0009_counts.get(s09, 0) + 1

        # Analyze pattern elements for unify constructs and overlaps
        unify_scopes: List[Dict[str, Any]] = []
        unify_ignore_scopes: List[Dict[str, Any]] = []
        has_unify = False
        has_unify_ignore = False

        pat_elems = rule.pattern.elements or (rule.pattern.tokens or [])
        for elem in pat_elems:
            if isinstance(elem, PatternUnify):
                has_unify = True
                feats = [f.name for f in elem.features]
                for f in feats:
                    unify_features_distribution[f] += 1
                unify_scopes.append({
                    "features": feats,
                    "negate": elem.negate,
                    "token_count": len(elem.elements),
                })
                # Check overlaps inside unify
                for u_el in elem.elements:
                    if hasattr(u_el, "skip") and u_el.skip is not None:
                        overlap_feature_counts["skip"] += 1
                    if hasattr(u_el, "min") and u_el.min is not None:
                        overlap_feature_counts["min"] += 1
                    if hasattr(u_el, "max") and u_el.max is not None:
                        overlap_feature_counts["max"] += 1
                    if hasattr(u_el, "spacebefore") and u_el.spacebefore is not None:
                        overlap_feature_counts["spacebefore"] += 1
                    if hasattr(u_el, "chunk") and u_el.chunk is not None:
                        overlap_feature_counts["chunk"] += 1
                    if hasattr(u_el, "raw_pos") and u_el.raw_pos:
                        overlap_feature_counts["raw_pos"] += 1
                    if hasattr(u_el, "exceptions") and u_el.exceptions:
                        overlap_feature_counts["exception"] += len(u_el.exceptions)
                    if hasattr(u_el, "and_elements") and u_el.and_elements:
                        overlap_feature_counts["and"] += 1
                    if u_el.__class__.__name__ == "PatternOr":
                        overlap_feature_counts["or"] += 1
            elif isinstance(elem, PatternUnifyIgnore):
                has_unify_ignore = True
                unify_ignore_scopes.append({
                    "token_count": len(elem.elements),
                })

        if has_unify:
            if rule.antipatterns:
                overlap_feature_counts["antipattern"] += len(rule.antipatterns)
            if rule.pattern.has_marker:
                overlap_feature_counts["marker"] += 1

        ex_inc = sum(1 for e in rule.examples if e.is_incorrect)
        ex_cor = sum(1 for e in rule.examples if not e.is_incorrect)

        rule_dict: Dict[str, Any] = {
            "global_index": idx,
            "source_order": rule.source_order_index,
            "id": rule.id,
            "sub_id": rule.sub_id,
            "full_id": rule.full_id,
            "name": rule.name,
            "category_id": rule.category_id,
            "category_name": rule.category_name,
            "rulegroup_id": rule.rulegroup_id,
            "rulegroup_name": rule.rulegroup_name,
            "default_off": rule.default_off,
            "state_task_0008": s08,
            "state_task_0009": s09,
            "transition": trans_key,
            "blockers_task_0008": adv_record.get("remaining_blockers_after_0008", []),
            "blockers_task_0009": get_blockers_task_0009(xml_rule_map[rule.full_id]),
            "has_unify": has_unify,
            "has_unify_ignore": has_unify_ignore,
            "unify_scopes_count": len(unify_scopes),
            "unify_scopes": unify_scopes,
            "unify_ignore_scopes_count": len(unify_ignore_scopes),
            "unify_ignore_scopes": unify_ignore_scopes,
            "examples_total_count": len(rule.examples),
            "examples_incorrect_count": ex_inc,
            "examples_correct_count": ex_cor,
        }
        rules_inventory.append(rule_dict)

    # Raw XML counts
    tag_counts: Counter[str] = Counter()
    attr_counts: Counter[str] = Counter()
    for elem in root.iter():
        tag_counts[elem.tag] += 1
        for attr in elem.attrib:
            attr_counts[f"{elem.tag}@{attr}"] += 1

    runnable_0009_total = (
        state_0009_counts.get("CORE_0007_RUNNABLE", 0)
        + state_0009_counts.get("ADVANCED_0008_RUNNABLE", 0)
        + state_0009_counts.get("UNIFICATION_0009_RUNNABLE", 0)
    )
    deferred_0009_total = len(rules_inventory) - runnable_0009_total

    gen_sha = sha256_file(Path(__file__).resolve())

    inventory_data: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "provenance": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "grammar_xml_path": "third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/rules/ru/grammar.xml",
            "grammar_xml_size_bytes": xml_size,
            "grammar_xml_sha256": xml_sha,
            "baseline_task_0008_commit": BASELINE_0008_COMMIT,
            "generator_path": "tools/russian_grammar_unification_inventory.py",
            "generator_sha256": gen_sha,
            "oracle_manifest_path": "compat/oracle_manifest.json",
        },
        "source_totals": {
            "categories": len(root.findall("category")),
            "rulegroups": len(root.findall(".//rulegroup")),
            "source_rule_elements": len(rules_inventory),
            "embedded_examples_total": sum(r["examples_total_count"] for r in rules_inventory),
        },
        "context_split": {
            "root_level_unifications_count": len(root_unifications),
            "category_level_unifications_count": len(cat_unifications),
            "rulegroup_level_unifications_count": len(rg_unifications),
            "rule_level_unifications_count": len(rule_unifications),
            "rule_local_unify_scopes_count": tag_counts["unify"],
            "rule_local_unify_ignore_scopes_count": tag_counts["unify-ignore"],
            "configuration_definitions": configuration_definitions,
        },
        "unification_construct_distributions": {
            "unify_negate_distribution": unify_negate_distribution,
            "unify_features_distribution": dict(unify_features_distribution),
            "unify_overlap_with_other_constructs": dict(overlap_feature_counts),
        },
        "baseline_task_0008": state_0008_counts,
        "task_0008_to_0009_transitions": trans_counts,
        "task_0009_disposition": {
            "state_counts": state_0009_counts,
            "runnable_source_rules_total": runnable_0009_total,
            "deferred_source_rules_total": deferred_0009_total,
            "unknown_count": state_0009_counts.get("UNKNOWN", 0),
        },
        "example_totals": {
            "all_examples_total": sum(r["examples_total_count"] for r in rules_inventory),
            "all_incorrect_examples_total": sum(r["examples_incorrect_count"] for r in rules_inventory),
            "all_correct_examples_total": sum(r["examples_correct_count"] for r in rules_inventory),
            "runnable_examples_total": sum(
                r["examples_total_count"]
                for r in rules_inventory
                if r["state_task_0009"] in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE", "UNIFICATION_0009_RUNNABLE")
            ),
            "runnable_incorrect_examples_total": sum(
                r["examples_incorrect_count"]
                for r in rules_inventory
                if r["state_task_0009"] in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE", "UNIFICATION_0009_RUNNABLE")
            ),
            "runnable_correct_examples_total": sum(
                r["examples_correct_count"]
                for r in rules_inventory
                if r["state_task_0009"] in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE", "UNIFICATION_0009_RUNNABLE")
            ),
            "deferred_examples_total": sum(
                r["examples_total_count"]
                for r in rules_inventory
                if r["state_task_0009"] not in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE", "UNIFICATION_0009_RUNNABLE")
            ),
            "deferred_incorrect_examples_total": sum(
                r["examples_incorrect_count"]
                for r in rules_inventory
                if r["state_task_0009"] not in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE", "UNIFICATION_0009_RUNNABLE")
            ),
            "deferred_correct_examples_total": sum(
                r["examples_correct_count"]
                for r in rules_inventory
                if r["state_task_0009"] not in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE", "UNIFICATION_0009_RUNNABLE")
            ),
        },
        "unification_totals": {
            "root_unification_elements_count": len(root_unifications),
            "configuration_features_count": len(configuration_definitions),
            "equivalence_types_count": sum(c["equivalences_count"] for c in configuration_definitions),
            "unify_scopes_count": tag_counts["unify"],
            "unify_ignore_scopes_count": tag_counts["unify-ignore"],
            "unification_using_rules_count": sum(1 for r in rules_inventory if r["has_unify"]),
            "unification_using_runnable_rules_count": sum(1 for r in rules_inventory if r["has_unify"] and r["state_task_0009"] == "UNIFICATION_0009_RUNNABLE"),
            "unification_using_deferred_rules_count": sum(1 for r in rules_inventory if r["has_unify"] and r["state_task_0009"] != "UNIFICATION_0009_RUNNABLE"),
        },
        "raw_xml_totals": {
            "tag_counts": dict(tag_counts),
            "attribute_counts": dict(attr_counts),
        },
        "rules": rules_inventory,
    }

    return inventory_data


def main() -> None:
    data = generate_unification_inventory()
    out_path = UNIFICATION_INVENTORY_OUTPUT_PATH
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated Russian grammar unification inventory at {out_path}")
    print(f"Source rules: {len(data['rules'])}")
    print(f"Transitions: {json.dumps(data['task_0008_to_0009_transitions'], indent=2)}")
    print(f"Task 0009 State counts: {json.dumps(data['task_0009_disposition']['state_counts'], indent=2)}")


if __name__ == "__main__":
    main()
