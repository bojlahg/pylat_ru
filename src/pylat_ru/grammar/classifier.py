"""src/pylat_ru/grammar/classifier.py

Deterministic rule classifier identifying core-runnable rules vs deferred tasks.
"""

from __future__ import annotations

from typing import List, Tuple
import xml.etree.ElementTree as ET

from pylat_ru.grammar.model import ExecutionState, RuleBlocker


def classify_rule_element(rule_elem: ET.Element) -> Tuple[ExecutionState, List[RuleBlocker]]:
    """Inspect XML rule element and determine its execution state and blockers."""
    blockers: List[RuleBlocker] = []

    # Check patterns
    for pat in rule_elem.findall("pattern"):
        if pat.attrib.get("raw_pos") == "yes":
            blockers.append(RuleBlocker("pattern@raw_pos", "0008", "Pattern raw_pos attribute"))

        if pat.findall(".//and"):
            blockers.append(RuleBlocker("pattern:and", "0008", "<and> token construct"))
        if pat.findall(".//or"):
            blockers.append(RuleBlocker("pattern:or", "0008", "<or> token construct"))
        if pat.findall(".//unify"):
            blockers.append(RuleBlocker("pattern:unify", "0009", "<unify> feature agreement"))
        if pat.findall(".//unify-ignore"):
            blockers.append(RuleBlocker("pattern:unify-ignore", "0009", "<unify-ignore> feature agreement"))

        for tok in pat.findall(".//token"):
            if "skip" in tok.attrib:
                blockers.append(RuleBlocker("token@skip", "0008", "Token skip attribute"))
            if "min" in tok.attrib or "max" in tok.attrib:
                blockers.append(RuleBlocker("token@min_max", "0008", "Token min/max quantifier attributes"))
            if "spacebefore" in tok.attrib:
                blockers.append(RuleBlocker("token@spacebefore", "0008", "Token spacebefore attribute"))
            if "chunk" in tok.attrib:
                blockers.append(RuleBlocker("token@chunk", "0008", "Token chunk attribute"))

            for exc in tok.findall("exception"):
                if "scope" in exc.attrib and exc.attrib["scope"] != "current":
                    blockers.append(
                        RuleBlocker(
                            f"exception@scope={exc.attrib['scope']}",
                            "0008",
                            f"Exception scope={exc.attrib['scope']}",
                        )
                    )
                if "spacebefore" in exc.attrib:
                    blockers.append(RuleBlocker("exception@spacebefore", "0008", "Exception spacebefore attribute"))

    # Antipatterns
    if rule_elem.findall("antipattern"):
        blockers.append(RuleBlocker("antipattern", "0008", "Rule contains antipattern(s)"))

    # Filters
    for filt in rule_elem.findall("filter"):
        cls_name = filt.attrib.get("class", "unknown")
        blockers.append(RuleBlocker(f"filter:{cls_name}", "0010", f"Filter class {cls_name}"))

    # Complex match attributes in message and suggestion
    match_elements = rule_elem.findall(".//message//match") + rule_elem.findall(".//suggestion//match")
    for match in match_elements:
        complex_attrs = set(match.attrib.keys()) - {"no"}
        for attr in sorted(list(complex_attrs)):
            target_task = "0008" if attr in ("include_skipped", "case_conversion") else "0010"
            blockers.append(RuleBlocker(f"match@{attr}", target_task, f"Match element attribute @{attr}"))

    # Suppress misspelled
    for msg in rule_elem.findall("message"):
        if msg.attrib.get("suppress_misspelled") == "yes":
            blockers.append(
                RuleBlocker(
                    "message@suppress_misspelled",
                    "0012",
                    "Message suppress_misspelled attribute",
                )
            )
    for sug in rule_elem.findall(".//suggestion"):
        if sug.attrib.get("suppress_misspelled") == "yes":
            blockers.append(
                RuleBlocker(
                    "suggestion@suppress_misspelled",
                    "0012",
                    "Suggestion suppress_misspelled attribute",
                )
            )

    # Deduplicate blockers preserving order
    unique_blockers: List[RuleBlocker] = []
    seen: set[Tuple[str, str]] = set()
    for b in blockers:
        key = (b.feature, b.target_task)
        if key not in seen:
            seen.add(key)
            unique_blockers.append(b)

    if not unique_blockers:
        return ExecutionState.CORE_0007_RUNNABLE, []

    tasks = {b.target_task for b in unique_blockers}
    if len(tasks) > 1:
        return ExecutionState.MULTI_BLOCKER, unique_blockers
    elif "0008" in tasks:
        return ExecutionState.DEFERRED_0008_ADVANCED_MATCHING, unique_blockers
    elif "0009" in tasks:
        return ExecutionState.DEFERRED_0009_UNIFICATION, unique_blockers
    elif "0010" in tasks:
        return ExecutionState.DEFERRED_0010_FILTER, unique_blockers
    elif "0012" in tasks:
        return ExecutionState.DEFERRED_0012_SPELLING_OR_SUPPRESSION, unique_blockers
    else:
        return ExecutionState.UNKNOWN, unique_blockers
