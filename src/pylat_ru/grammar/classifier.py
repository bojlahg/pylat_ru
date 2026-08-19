"""src/pylat_ru/grammar/classifier.py

Deterministic rule classifier identifying runnable rules (Core 0007 & Advanced 0008)
vs deferred future tasks (0009 Unification, 0010 Java Filters, 0012 Spelling/Suppression).
"""

from __future__ import annotations

from typing import List, Tuple
import xml.etree.ElementTree as ET

from pylat_ru.grammar.model import ExecutionState, RuleBlocker


def classify_rule_element(rule_elem: ET.Element) -> Tuple[ExecutionState, List[RuleBlocker]]:
    """Inspect XML rule element and determine its execution state and remaining blockers."""
    remaining_blockers: List[RuleBlocker] = []
    uses_0008_advanced: bool = False

    # Check patterns
    for pat in rule_elem.findall("pattern"):
        if pat.attrib.get("raw_pos") == "yes":
            uses_0008_advanced = True

        if pat.findall(".//and"):
            uses_0008_advanced = True
        if pat.findall(".//or"):
            uses_0008_advanced = True
        if pat.findall(".//phrase"):
            uses_0008_advanced = True

        if pat.findall(".//unify"):
            remaining_blockers.append(RuleBlocker("pattern:unify", "0009", "<unify> feature agreement"))
        if pat.findall(".//unify-ignore"):
            remaining_blockers.append(RuleBlocker("pattern:unify-ignore", "0009", "<unify-ignore> feature agreement"))

        for tok in pat.findall(".//token"):
            if "raw_pos" in tok.attrib:
                uses_0008_advanced = True
            if "skip" in tok.attrib:
                uses_0008_advanced = True
            if "min" in tok.attrib or "max" in tok.attrib:
                uses_0008_advanced = True
            if "spacebefore" in tok.attrib:
                uses_0008_advanced = True
            if "chunk" in tok.attrib:
                uses_0008_advanced = True
            if tok.findall("match"):
                uses_0008_advanced = True

            for exc in tok.findall("exception"):
                if "scope" in exc.attrib and exc.attrib["scope"] != "current":
                    uses_0008_advanced = True
                if "spacebefore" in exc.attrib:
                    uses_0008_advanced = True

    # Antipatterns (supported in Task 0008)
    if rule_elem.findall("antipattern"):
        uses_0008_advanced = True

    # Generic <match> attributes in message and suggestion (supported in Task 0008)
    match_elements = rule_elem.findall(".//message//match") + rule_elem.findall(".//suggestion//match")
    for match in match_elements:
        if match.text and match.text.strip():
            uses_0008_advanced = True
        complex_attrs = set(match.attrib.keys()) - {"no"}
        if complex_attrs:
            uses_0008_advanced = True

    # Java/XML Filters (deferred to Task 0010)
    for filt in rule_elem.findall("filter"):
        cls_name = filt.attrib.get("class", "unknown")
        remaining_blockers.append(RuleBlocker(f"filter:{cls_name}", "0010", f"Filter class {cls_name}"))

    # Suppress misspelled (deferred to Task 0012)
    for msg in rule_elem.findall("message"):
        if msg.attrib.get("suppress_misspelled") == "yes":
            remaining_blockers.append(
                RuleBlocker(
                    "message@suppress_misspelled",
                    "0012",
                    "Message suppress_misspelled attribute",
                )
            )
    for sug in rule_elem.findall(".//suggestion"):
        if sug.attrib.get("suppress_misspelled") == "yes":
            remaining_blockers.append(
                RuleBlocker(
                    "suggestion@suppress_misspelled",
                    "0012",
                    "Suggestion suppress_misspelled attribute",
                )
            )

    # Deduplicate remaining blockers preserving order
    unique_blockers: List[RuleBlocker] = []
    seen: set[Tuple[str, str]] = set()
    for b in remaining_blockers:
        key = (b.feature, b.target_task)
        if key not in seen:
            seen.add(key)
            unique_blockers.append(b)

    if not unique_blockers:
        if uses_0008_advanced:
            return ExecutionState.ADVANCED_0008_RUNNABLE, []
        return ExecutionState.CORE_0007_RUNNABLE, []

    tasks = {b.target_task for b in unique_blockers}
    if len(tasks) > 1:
        return ExecutionState.MULTI_BLOCKER, unique_blockers
    elif "0009" in tasks:
        return ExecutionState.DEFERRED_0009_UNIFICATION, unique_blockers
    elif "0010" in tasks:
        return ExecutionState.DEFERRED_0010_FILTER, unique_blockers
    elif "0012" in tasks:
        return ExecutionState.DEFERRED_0012_SPELLING_OR_SUPPRESSION, unique_blockers
    else:
        return ExecutionState.UNKNOWN, unique_blockers
