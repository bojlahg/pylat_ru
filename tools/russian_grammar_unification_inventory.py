"""tools/russian_grammar_unification_inventory.py

Deterministic generator for compat/russian_grammar_unification_inventory.json.
Extracts comprehensive unification matching statistics, observed feature distributions,
equivalence configuration mapping, rule-local unify/unify-ignore scopes,
and deterministic 0008 -> 0009 transition matrix for all 892 LanguageTool Russian XML grammar rules.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
LICENSE_INV_PATH = REPO_ROOT / "third_party" / "languagetool" / "license_inventory.json"
ORACLE_MANIFEST_PATH = REPO_ROOT / "compat" / "oracle_manifest.json"
CANONICAL_RAW_INVENTORY_PATH = REPO_ROOT / "compat" / "inventory.json"
ADVANCED_INVENTORY_PATH = REPO_ROOT / "compat" / "russian_grammar_advanced_inventory.json"
UNIFICATION_INVENTORY_OUTPUT_PATH = REPO_ROOT / "compat" / "russian_grammar_unification_inventory.json"
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

    xml_bytes = GRAMMAR_XML_PATH.read_bytes()
    xml_size = len(xml_bytes)
    xml_sha = hashlib.sha256(xml_bytes).hexdigest()

    tree = ET.parse(GRAMMAR_XML_PATH)
    root = tree.getroot()

    # 1. Global unification definitions
    unification_elements = root.findall(".//unification")
    configuration_definitions: List[Dict[str, Any]] = []

    for u_idx, u_elem in enumerate(unification_elements):
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

    # 2. Extract rules and classify transitions
    rules_inventory: List[Dict[str, Any]] = []
    source_order = 0

    trans_counts: Dict[str, int] = {}
    state_0008_counts: Dict[str, int] = {}
    state_0009_counts: Dict[str, int] = {}

    runnable_0009_examples_inc = 0
    runnable_0009_examples_cor = 0
    deferred_0009_examples_inc = 0
    deferred_0009_examples_cor = 0

    all_unify_elements = root.findall(".//unify")
    all_unify_ignore_elements = root.findall(".//unify-ignore")

    unify_negate_counts = {"yes": 0, "no": 0, "default_no": 0}
    unify_features_selected: Dict[str, int] = {}

    for u in all_unify_elements:
        neg = u.attrib.get("negate")
        if neg == "yes":
            unify_negate_counts["yes"] += 1
        elif neg == "no":
            unify_negate_counts["no"] += 1
        else:
            unify_negate_counts["default_no"] += 1

        for f in u.findall("feature"):
            fid = f.attrib.get("id", "")
            unify_features_selected[fid] = unify_features_selected.get(fid, 0) + 1

    for cat in root.findall("category"):
        cat_id = cat.attrib.get("id", "MISC")
        cat_name = cat.attrib.get("name", "Miscellaneous")

        for child in cat:
            if child.tag == "rulegroup":
                rg_id = child.attrib.get("id", "")
                rg_name = child.attrib.get("name", "")
                for r_elem in child.findall("rule"):
                    r_id = r_elem.attrib.get("id", rg_id)
                    sub_id = r_elem.attrib.get("subid")
                    if sub_id:
                        full_id = f"{r_id}[{sub_id}]"
                    else:
                        full_id = f"{rg_id}[{r_id}]" if r_id != rg_id else f"{r_id}[1]"
                    r_info = _analyze_rule(
                        r_elem=r_elem,
                        full_id=full_id,
                        rule_id=r_id,
                        sub_id=sub_id,
                        cat_id=cat_id,
                        cat_name=cat_name,
                        rg_id=rg_id,
                        rg_name=rg_name,
                        source_order=source_order,
                    )
                    rules_inventory.append(r_info)
                    source_order += 1

            elif child.tag == "rule":
                r_id = child.attrib.get("id", "")
                sub_id = child.attrib.get("subid")
                full_id = f"{r_id}[{sub_id}]" if sub_id else f"{r_id}[1]"
                r_info = _analyze_rule(
                    r_elem=child,
                    full_id=full_id,
                    rule_id=r_id,
                    sub_id=sub_id,
                    cat_id=cat_id,
                    cat_name=cat_name,
                    rg_id=None,
                    rg_name=None,
                    source_order=source_order,
                )
                rules_inventory.append(r_info)
                source_order += 1

    # Summarize transitions
    for r in rules_inventory:
        s08 = r["state_task_0008"]
        s09 = r["state_task_0009"]
        trans_key = f"{s08} -> {s09}"
        trans_counts[trans_key] = trans_counts.get(trans_key, 0) + 1
        state_0008_counts[s08] = state_0008_counts.get(s08, 0) + 1
        state_0009_counts[s09] = state_0009_counts.get(s09, 0) + 1

        ex_inc = r["examples_incorrect_count"]
        ex_cor = r["examples_correct_count"]
        if s09 in ("CORE_0007_RUNNABLE", "ADVANCED_0008_RUNNABLE", "UNIFICATION_0009_RUNNABLE"):
            runnable_0009_examples_inc += ex_inc
            runnable_0009_examples_cor += ex_cor
        else:
            deferred_0009_examples_inc += ex_inc
            deferred_0009_examples_cor += ex_cor

    # Raw XML counts
    tag_counts: Counter[str] = Counter()
    attr_counts: Counter[str] = Counter()
    for elem in root.iter():
        tag_counts[elem.tag] += 1
        for attr in elem.attrib:
            attr_counts[f"{elem.tag}@{attr}"] += 1

    unification_raw_xml = {
        "unification_elements_count": tag_counts["unification"],
        "unification_feature_attr_count": attr_counts["unification@feature"],
        "equivalence_elements_count": tag_counts["equivalence"],
        "equivalence_type_attr_count": attr_counts["equivalence@type"],
        "feature_elements_count": tag_counts["feature"],
        "feature_id_attr_count": attr_counts["feature@id"],
        "type_elements_count": tag_counts["type"],
        "type_id_attr_count": attr_counts["type@id"],
        "unify_elements_count": tag_counts["unify"],
        "unify_negate_attr_count": attr_counts["unify@negate"],
        "unify_ignore_elements_count": tag_counts["unify-ignore"],
        "unify_negate_distribution": unify_negate_counts,
        "unify_features_selected_distribution": unify_features_selected,
    }

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
            "all_examples_incorrect": sum(r["examples_incorrect_count"] for r in rules_inventory),
            "all_examples_correct": sum(r["examples_correct_count"] for r in rules_inventory),
            "runnable_examples_total": runnable_0009_examples_inc + runnable_0009_examples_cor,
            "runnable_examples_incorrect": runnable_0009_examples_inc,
            "runnable_examples_correct": runnable_0009_examples_cor,
            "deferred_examples_total": deferred_0009_examples_inc + deferred_0009_examples_cor,
            "deferred_examples_incorrect": deferred_0009_examples_inc,
            "deferred_examples_correct": deferred_0009_examples_cor,
        },
        "raw_xml_unification_totals": unification_raw_xml,
        "configuration_definitions": configuration_definitions,
        "unification_rules_count": len([r for r in rules_inventory if r["uses_unification"]]),
        "rules": rules_inventory,
    }

    return inventory_data


def _analyze_rule(
    r_elem: ET.Element,
    full_id: str,
    rule_id: str,
    sub_id: Optional[str],
    cat_id: str,
    cat_name: str,
    rg_id: Optional[str],
    rg_name: Optional[str],
    source_order: int,
) -> Dict[str, Any]:
    """Analyze a single rule element for unification and blocker transitions."""
    pat_elems = r_elem.findall("pattern")
    unify_elems = r_elem.findall(".//unify")
    unify_ignore_elems = r_elem.findall(".//unify-ignore")

    uses_unify = len(unify_elems) > 0
    uses_unify_ignore = len(unify_ignore_elems) > 0
    uses_unification = uses_unify or uses_unify_ignore

    unify_positive_count = sum(1 for u in unify_elems if u.attrib.get("negate") != "yes")
    unify_negated_count = sum(1 for u in unify_elems if u.attrib.get("negate") == "yes")

    selected_features: Dict[str, List[str]] = {}
    for u in unify_elems:
        for f in u.findall("feature"):
            fid = f.attrib.get("id", "")
            types = [t.attrib.get("id", "") for t in f.findall("type")]
            selected_features.setdefault(fid, []).extend(types)

    # Blocker analysis
    blockers_0008: List[str] = []
    blockers_0009: List[str] = []
    uses_0008_advanced = False

    for pat in pat_elems:
        if pat.attrib.get("raw_pos") == "yes":
            uses_0008_advanced = True
        if pat.findall(".//and") or pat.findall(".//or") or pat.findall(".//phrase"):
            uses_0008_advanced = True
        if pat.findall(".//unify"):
            blockers_0008.append("pattern:unify")
        if pat.findall(".//unify-ignore"):
            blockers_0008.append("pattern:unify-ignore")

        for tok in pat.findall(".//token"):
            if any(k in tok.attrib for k in ("raw_pos", "skip", "min", "max", "spacebefore", "chunk")):
                uses_0008_advanced = True
            if tok.findall("match"):
                uses_0008_advanced = True
            for exc in tok.findall("exception"):
                if exc.attrib.get("scope", "current") != "current" or "spacebefore" in exc.attrib:
                    uses_0008_advanced = True

    if r_elem.findall("antipattern"):
        uses_0008_advanced = True
    match_elements = r_elem.findall(".//message//match") + r_elem.findall(".//suggestion//match")
    for match in match_elements:
        if match.text and match.text.strip():
            uses_0008_advanced = True
        if set(match.attrib.keys()) - {"no"}:
            uses_0008_advanced = True

    # Filter blockers
    for filt in r_elem.findall("filter"):
        cls = filt.attrib.get("class", "unknown")
        b_name = f"filter:{cls}"
        blockers_0008.append(b_name)
        blockers_0009.append(b_name)

    # Spelling/suppression blockers
    for msg in r_elem.findall("message"):
        if msg.attrib.get("suppress_misspelled") == "yes":
            blockers_0008.append("message@suppress_misspelled")
            blockers_0009.append("message@suppress_misspelled")
    for sug in r_elem.findall(".//suggestion"):
        if sug.attrib.get("suppress_misspelled") == "yes":
            blockers_0008.append("suggestion@suppress_misspelled")
            blockers_0009.append("suggestion@suppress_misspelled")

    # Deduplicate blockers preserving order
    blockers_0008 = list(dict.fromkeys(blockers_0008))
    blockers_0009 = list(dict.fromkeys(blockers_0009))

    # Determine 0008 state
    if not blockers_0008:
        state_0008 = "ADVANCED_0008_RUNNABLE" if uses_0008_advanced else "CORE_0007_RUNNABLE"
    else:
        # Check task targets for 0008 blockers
        targets = set()
        for b in blockers_0008:
            if b.startswith("pattern:unify"):
                targets.add("0009")
            elif b.startswith("filter:"):
                targets.add("0010")
            elif "@suppress_misspelled" in b:
                targets.add("0012")
        if len(targets) > 1:
            state_0008 = "MULTI_BLOCKER"
        elif "0009" in targets:
            state_0008 = "DEFERRED_0009_UNIFICATION"
        elif "0010" in targets:
            state_0008 = "DEFERRED_0010_FILTER"
        elif "0012" in targets:
            state_0008 = "DEFERRED_0012_SPELLING_OR_SUPPRESSION"
        else:
            state_0008 = "UNKNOWN"

    # Determine 0009 state
    if not blockers_0009:
        if uses_unification:
            state_0009 = "UNIFICATION_0009_RUNNABLE"
        elif uses_0008_advanced:
            state_0009 = "ADVANCED_0008_RUNNABLE"
        else:
            state_0009 = "CORE_0007_RUNNABLE"
    else:
        targets_09 = set()
        for b in blockers_0009:
            if b.startswith("filter:"):
                targets_09.add("0010")
            elif "@suppress_misspelled" in b:
                targets_09.add("0012")
        if len(targets_09) > 1:
            state_0009 = "MULTI_BLOCKER"
        elif "0010" in targets_09:
            state_0009 = "DEFERRED_0010_FILTER"
        elif "0012" in targets_09:
            state_0009 = "DEFERRED_0012_SPELLING_OR_SUPPRESSION"
        else:
            state_0009 = "UNKNOWN"

    # Examples counting
    ex_elements = r_elem.findall("example")
    ex_total = len(ex_elements)
    ex_inc = 0
    for ex in ex_elements:
        ex_type = ex.attrib.get("type")
        correction = ex.attrib.get("correction")
        if ex_type in ("triggers_error", "incorrect") or correction is not None:
            is_inc = (ex_type not in ("untouched", "correct"))
        else:
            is_inc = False
        if is_inc:
            ex_inc += 1
    ex_cor = ex_total - ex_inc

    return {
        "source_order": source_order,
        "full_id": full_id,
        "id": rule_id,
        "sub_id": sub_id,
        "category_id": cat_id,
        "category_name": cat_name,
        "rulegroup_id": rg_id,
        "rulegroup_name": rg_name,
        "state_task_0008": state_0008,
        "state_task_0009": state_0009,
        "uses_unification": uses_unification,
        "unify_scopes_count": len(unify_elems),
        "unify_positive_count": unify_positive_count,
        "unify_negated_count": unify_negated_count,
        "unify_ignore_scopes_count": len(unify_ignore_elems),
        "selected_features": selected_features,
        "remaining_blockers_0008": blockers_0008,
        "remaining_blockers_0009": blockers_0009,
        "examples_total_count": ex_total,
        "examples_incorrect_count": ex_inc,
        "examples_correct_count": ex_cor,
    }


def main() -> None:
    """Generate and write compat/russian_grammar_unification_inventory.json."""
    gen_sha = sha256_file(Path(__file__).resolve())
    data = generate_unification_inventory()
    data["provenance"]["generator_sha256"] = gen_sha

    UNIFICATION_INVENTORY_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(UNIFICATION_INVENTORY_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Generated {UNIFICATION_INVENTORY_OUTPUT_PATH} (892 rules, {data['source_totals']['embedded_examples_total']} examples)")


if __name__ == "__main__":
    main()
