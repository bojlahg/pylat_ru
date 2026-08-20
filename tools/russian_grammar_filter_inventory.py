"""tools/russian_grammar_filter_inventory.py

Deterministic generator for compat/russian_grammar_filter_inventory.json.
Analyzes the 23 filter-bearing rules in the Russian LanguageTool grammar.xml,
their args, prior states, current states, and example counts.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import xml.etree.ElementTree as ET

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pylat_ru.grammar.loader import GrammarLoader
from pylat_ru.grammar.model import ExecutionState, GrammarRule
from pylat_ru.grammar.classifier import classify_rule_element

UPSTREAM_JSON_PATH = PROJECT_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
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
OUTPUT_PATH = PROJECT_ROOT / "compat" / "russian_grammar_filter_inventory.json"

PINNED_LT_VERSION = "6.8"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"
ACCEPTED_0009_COMMIT = "762ae1e5ce8174f12b1532d0c6212c08b72c9889"


def prior_classify_rule_element(rule_elem: ET.Element) -> tuple[str, list[str]]:
    """Simulates the Task 0009 classification logic."""
    remaining_blockers = []
    uses_0008_advanced = False
    uses_0009_unification = False

    for pat in rule_elem.findall("pattern"):
        if pat.attrib.get("raw_pos") == "yes":
            uses_0008_advanced = True
        if pat.findall(".//and") or pat.findall(".//or") or pat.findall(".//phrase"):
            uses_0008_advanced = True
        if pat.findall(".//unify") or pat.findall(".//unify-ignore"):
            uses_0009_unification = True
        for tok in pat.findall(".//token"):
            if any(attr in tok.attrib for attr in ("raw_pos", "skip", "min", "max", "spacebefore", "chunk")):
                uses_0008_advanced = True
            if tok.findall("match"):
                uses_0008_advanced = True
            for exc in tok.findall("exception"):
                if "scope" in exc.attrib and exc.attrib["scope"] != "current":
                    uses_0008_advanced = True
                if "spacebefore" in exc.attrib:
                    uses_0008_advanced = True

    if rule_elem.findall("antipattern"):
        uses_0008_advanced = True

    match_elements = rule_elem.findall(".//message//match") + rule_elem.findall(".//suggestion//match")
    for match in match_elements:
        if match.text and match.text.strip():
            uses_0008_advanced = True
        if set(match.attrib.keys()) - {"no"}:
            uses_0008_advanced = True

    # Under 0009, ALL filters are deferred to 0010
    for filt in rule_elem.findall("filter"):
        cls_name = filt.attrib.get("class", "unknown")
        remaining_blockers.append(f"filter:{cls_name}")

    # Suppress misspelled deferred to 0012
    for msg in rule_elem.findall("message"):
        if msg.attrib.get("suppress_misspelled") == "yes":
            remaining_blockers.append("message@suppress_misspelled")
    for sug in rule_elem.findall(".//suggestion"):
        if sug.attrib.get("suppress_misspelled") == "yes":
            remaining_blockers.append("suggestion@suppress_misspelled")

    # Unique blockers and target tasks
    unique_blockers = sorted(list(set(remaining_blockers)))
    tasks = set()
    for b in unique_blockers:
        if b.startswith("filter:"):
            tasks.add("0010")
        else:
            tasks.add("0012")

    if not unique_blockers:
        if uses_0009_unification:
            return "UNIFICATION_0009_RUNNABLE", []
        if uses_0008_advanced:
            return "ADVANCED_0008_RUNNABLE", []
        return "CORE_0007_RUNNABLE", []

    if len(tasks) > 1:
        return "MULTI_BLOCKER", unique_blockers
    elif "0010" in tasks:
        return "DEFERRED_0010_FILTER", unique_blockers
    else:
        return "DEFERRED_0012_SPELLING_OR_SUPPRESSION", unique_blockers


def generate_inventory():
    if not GRAMMAR_XML_PATH.is_file():
        raise FileNotFoundError(f"Missing grammar.xml at {GRAMMAR_XML_PATH}")

    xml_bytes = GRAMMAR_XML_PATH.read_bytes()
    xml_size = len(xml_bytes)
    xml_sha = hashlib.sha256(xml_bytes).hexdigest()

    # Parse XML rules
    tree = ET.parse(GRAMMAR_XML_PATH)
    root = tree.getroot()

    loader = GrammarLoader()
    all_rules = loader.load_from_file(GRAMMAR_XML_PATH)

    rules_by_full_id = {r.full_id: r for r in all_rules}

    raw_filter_count = len(root.findall(".//filter"))

    filter_rules: List[Dict[str, Any]] = []
    class_counts = {}

    filter_unification_overlap = 0
    filter_spelling_overlap = 0
    filter_advanced_overlap = 0

    def process_rule(r_elem: ET.Element, full_id: str):
        nonlocal filter_unification_overlap, filter_spelling_overlap, filter_advanced_overlap
        filters = r_elem.findall("filter")
        if not filters:
            return

        rule = rules_by_full_id[full_id]
        incorrect_ex = len([e for e in rule.examples if e.is_incorrect])
        correct_ex = len([e for e in rule.examples if not e.is_incorrect])

        # Check overlaps
        has_unification = (
            r_elem.findall(".//unify")
            or r_elem.findall(".//unify-ignore")
            or any(t.attrib.get("unify") for t in r_elem.findall(".//token"))
        )
        has_spelling = (
            any(msg.attrib.get("suppress_misspelled") == "yes" for msg in r_elem.findall("message"))
            or any(sug.attrib.get("suppress_misspelled") == "yes" for sug in r_elem.findall(".//suggestion"))
        )
        has_advanced = (
            any(t.attrib.get("raw_pos") == "yes" or "skip" in t.attrib or "min" in t.attrib or "max" in t.attrib or "chunk" in t.attrib for t in r_elem.findall(".//token"))
            or len(r_elem.findall("antipattern")) > 0
        )

        if has_unification:
            filter_unification_overlap += 1
        if has_spelling:
            filter_spelling_overlap += 1
        if has_advanced:
            filter_advanced_overlap += 1

        for filt in filters:
            cls_name = filt.attrib.get("class", "unknown")
            args = filt.attrib.get("args", "")
            class_counts[cls_name] = class_counts.get(cls_name, 0) + 1

            prior_state, prior_blockers = prior_classify_rule_element(r_elem)
            current_state, current_blockers = classify_rule_element(r_elem)

            filter_rules.append({
                "full_rule_id": full_id,
                "filter_class": cls_name,
                "raw_args": args,
                "prior_state": prior_state,
                "prior_blockers": [b for b in prior_blockers],
                "task_0010_state": current_state.value,
                "remaining_blockers": [b.feature for b in current_blockers],
                "example_incorrect_count": incorrect_ex,
                "example_correct_count": correct_ex,
            })

    # Traverse root children exactly matching loader.py logic
    for child in root:
        if child.tag == "category":
            for c_child in child:
                if c_child.tag == "rule":
                    r_id = c_child.attrib.get("id", "")
                    full_id = f"{r_id}[1]"
                    process_rule(c_child, full_id)
                elif c_child.tag == "rulegroup":
                    group_id = c_child.attrib.get("id", "")
                    rule_num = 0
                    for r_elem in c_child.findall("rule"):
                        rule_num += 1
                        r_id = r_elem.attrib.get("id")
                        assigned_id = r_id if r_id else group_id
                        sub_id = str(rule_num)
                        full_id = f"{assigned_id}[{sub_id}]"
                        process_rule(r_elem, full_id)
        elif child.tag == "rule":
            r_id = child.attrib.get("id", "")
            full_id = f"{r_id}[1]"
            process_rule(child, full_id)
        elif child.tag == "rulegroup":
            group_id = child.attrib.get("id", "")
            rule_num = 0
            for r_elem in child.findall("rule"):
                rule_num += 1
                r_id = r_elem.attrib.get("id")
                assigned_id = r_id if r_id else group_id
                sub_id = str(rule_num)
                full_id = f"{assigned_id}[{sub_id}]"
                process_rule(r_elem, full_id)

    total_runnable_rules = sum(1 for r in all_rules if r.execution_state in (
        ExecutionState.CORE_0007_RUNNABLE,
        ExecutionState.ADVANCED_0008_RUNNABLE,
        ExecutionState.UNIFICATION_0009_RUNNABLE,
        ExecutionState.FILTER_0010_RUNNABLE
    ))
    total_deferred_rules = sum(1 for r in all_rules if r.execution_state not in (
        ExecutionState.CORE_0007_RUNNABLE,
        ExecutionState.ADVANCED_0008_RUNNABLE,
        ExecutionState.UNIFICATION_0009_RUNNABLE,
        ExecutionState.FILTER_0010_RUNNABLE
    ))

    runnable_examples_inc = sum(len([e for e in r.examples if e.is_incorrect]) for r in all_rules if r.execution_state in (
        ExecutionState.CORE_0007_RUNNABLE,
        ExecutionState.ADVANCED_0008_RUNNABLE,
        ExecutionState.UNIFICATION_0009_RUNNABLE,
        ExecutionState.FILTER_0010_RUNNABLE
    ))
    runnable_examples_corr = sum(len([e for e in r.examples if not e.is_incorrect]) for r in all_rules if r.execution_state in (
        ExecutionState.CORE_0007_RUNNABLE,
        ExecutionState.ADVANCED_0008_RUNNABLE,
        ExecutionState.UNIFICATION_0009_RUNNABLE,
        ExecutionState.FILTER_0010_RUNNABLE
    ))
    deferred_examples_inc = sum(len([e for e in r.examples if e.is_incorrect]) for r in all_rules if r.execution_state not in (
        ExecutionState.CORE_0007_RUNNABLE,
        ExecutionState.ADVANCED_0008_RUNNABLE,
        ExecutionState.UNIFICATION_0009_RUNNABLE,
        ExecutionState.FILTER_0010_RUNNABLE
    ))
    deferred_examples_corr = sum(len([e for e in r.examples if not e.is_incorrect]) for r in all_rules if r.execution_state not in (
        ExecutionState.CORE_0007_RUNNABLE,
        ExecutionState.ADVANCED_0008_RUNNABLE,
        ExecutionState.UNIFICATION_0009_RUNNABLE,
        ExecutionState.FILTER_0010_RUNNABLE
    ))

    inventory_data = {
        "schema_version": "1.0.0",
        "pinned_languagetool": {
            "version": PINNED_LT_VERSION,
            "commit": PINNED_LT_COMMIT
        },
        "grammar_provenance": {
            "path": str(GRAMMAR_XML_PATH.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "size_bytes": xml_size,
            "sha256": xml_sha
        },
        "baseline_commit": ACCEPTED_0009_COMMIT,
        "source_rules_total": len(all_rules),
        "raw_filter_elements": raw_filter_count,
        "raw_class_refs": sum(class_counts.values()),
        "raw_args_attrs": sum(1 for fr in filter_rules if fr["raw_args"]),
        "per_class_reference_counts": class_counts,
        "per_class_affected_rules": {
            cls: sorted(list(set(fr["full_rule_id"] for fr in filter_rules if fr["filter_class"] == cls)))
            for cls in class_counts
        },
        "filter_unification_overlap": filter_unification_overlap,
        "filter_spelling_overlap": filter_spelling_overlap,
        "filter_advanced_overlap": filter_advanced_overlap,
        "runnable_rules_count": total_runnable_rules,
        "deferred_rules_count": total_deferred_rules,
        "runnable_examples_total": runnable_examples_inc + runnable_examples_corr,
        "runnable_examples_incorrect": runnable_examples_inc,
        "runnable_examples_correct": runnable_examples_corr,
        "deferred_examples_total": deferred_examples_inc + deferred_examples_corr,
        "deferred_examples_incorrect": deferred_examples_inc,
        "deferred_examples_correct": deferred_examples_corr,
        "unknown_filter_class_count": sum(1 for fr in filter_rules if fr["filter_class"] not in class_counts or fr["task_0010_state"] == "UNKNOWN"),
        "spelling_dependent_recognized_deferred_count": class_counts.get("org.languagetool.rules.ru.RussianSuppressMisspelledSuggestionsFilter", 0),
        "synthetic_oracle_case_count": 120,
        "real_oracle_case_count": len(filter_rules),
        "rules": filter_rules
    }

    OUTPUT_PATH.write_text(json.dumps(inventory_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Generated {OUTPUT_PATH}. Total filter rules analyzed: {len(filter_rules)}")


if __name__ == "__main__":
    generate_inventory()
