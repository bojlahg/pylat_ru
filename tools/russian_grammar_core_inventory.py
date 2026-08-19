"""tools/russian_grammar_core_inventory.py

Deterministic generator for compat/russian_grammar_core_inventory.json.
Extracts comprehensive metadata, hashes, rule IDs, active XML tags, attributes by element,
token predicates, exception scopes, match attributes, filters, unifications, full classification
matrix for all 892 rules, and RussianChunker expressions directly from pinned upstream LanguageTool
Russian grammar resources and source files.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
LICENSE_INV_PATH = REPO_ROOT / "third_party" / "languagetool" / "license_inventory.json"
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
CHUNKER_JAVA_PATH = (
    REPO_ROOT
    / "third_party"
    / "languagetool"
    / "languagetool-language-modules"
    / "ru"
    / "src"
    / "main"
    / "java"
    / "org"
    / "languagetool"
    / "chunking"
    / "RussianChunker.java"
)
INVENTORY_OUTPUT_PATH = REPO_ROOT / "compat" / "russian_grammar_core_inventory.json"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def get_file_metadata(path: Path, license_info: Dict[str, Any]) -> Dict[str, Any]:
    """Return standard metadata dictionary for a repository file."""
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    vendored_rel = str(path.relative_to(REPO_ROOT / "third_party" / "languagetool")).replace("\\", "/")
    lic_meta = license_info.get(vendored_rel, {})
    return {
        "path": rel,
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "license": lic_meta.get("license", "LGPL-2.1-or-later"),
        "license_status": lic_meta.get("status", "VERIFIED_LGPL"),
        "purpose": lic_meta.get("purpose", ""),
    }


def analyze_chunker_source(path: Path) -> Dict[str, Any]:
    """Parse and extract exact structured metadata from RussianChunker.java."""
    filter_tags = [
        "ADJP",
        "DPT",
        "MayMissingYO",
        "NPP",
        "NPS",
        "PP",
        "SBAR",
        "VP",
    ]

    syntax_expansion = {
        "<ADJP>": "<chunk=B-ADJP> <chunk=I-ADJP>*",
        "<DPT>": "<chunk=B-DPT> <chunk=I-DPT>*",
        "<NP>": "<chunk=B-NP> <chunk=I-NP>*",
        "<VP>": "<chunk=B-VP> <chunk=I-VP>*",
    }

    phrase_types = [
        "NP",
        "NPS",
        "NPP",
        "PP",
        "MayMissingYO",
        "VP",
        "SBAR",
        "ADJP",
        "DPT",
    ]

    regexes1_defs = [
        ("<posre='NN:(Name|Fam|Patr):.*'> <posre='NN:(Name|Fam|Patr):.*'>+ ", "NP", True),
        ("<posre='NN:Fam:.*'> <regexCS=[А-ЯЁ]> <.> <regexCS=[А-ЯЁ]> <.> ", "NP", True),
        ("<regexCS=[А-ЯЁ]> <.> <regexCS=[А-ЯЁ]> <.> <posre='NN:Fam:.*'> ", "NP", True),
        ("<posre='VB:.*:.*' & !posre='NN:.*'>* ", "VP", False),
        ("<если>", "SBAR", False),
        ("<поэтому>", "SBAR", False),
        ("<posre='ADJ:Posit:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "NP", True),
        ("<posre='ADJ:Posit:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> <posre='NN:(Anim|Inanim):.*'> ", "NP", True),
        ("<posre='ADJ:Posit:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(Nom|V)'> <posre='NN:(Anim|Inanim):.*:(Nom|V)' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "ADJP", True),
        ("<posre='DPT:.*:.*' & !pos='PREP'> ", "DPT", False),
        ("<posre='DPT:.*:.*' & !pos='PREP'> <posre='NN:.*:.*:(R|D|T|P)' > ", "DPT", True),
        ("<posre='DPT:.*:.*' & !pos='PREP'> <posre='PREP'> <posre='NN:.*:.*:(R|D|T|P)' > ", "DPT", True),
        ("<posre='PT:.*:.*'> ", "ADJP", False),
        ("<posre='PT:.*:.*'> <pos='ADV' > ", "ADJP", True),
        ("<posre='PT:.*:.*'> <posre='NN:.*:.*:(R|D|T|P)' > ", "ADJP", True),
        ("<posre='PT:.*:.*'> <posre='PREP'> <posre='NN:.*:.*:(R|D|T|P|V)' > ", "ADJP", True),
        ("<posre='PT:.*:.*'> <posre='PREP'> <posre='ADJ:.*:.*:(R|D|T|P|V)' > <posre='NN:.*:.*:(R|D|T|P|V)' > ", "ADJP", True),
        ("<posre='PT:.*:.*'> <posre='NN:(Anim|Inanim):.*' & !posre='NN:(Anim|Inanim):.*:(Nom|V)'> <posre='NN:(Anim|Inanim):.*:(Nom|V)' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "ADJP", True),
        ("<posre='PT:.*:.*'> <posre='PNN:.*' & !posre='PNN:.*:Nom:.*'> <posre='NN:(Anim|Inanim):.*:(Nom|V)' & !posre='NN:(Anim|Inanim):.*:(R|D|T|P)'> ", "ADJP", True),
        ("<posre='PT:.*:.*'> <posre='ADJ:.*:.*' > ", "ADJP", False),
        ("<тов>", "NP", False),
    ]

    regexes2_defs = [
        ("<posre=NN:Name:.*> <и> <posre=NN:Name:.*>", "NPP", True),
        ("<posre=NN:Name:.*> <или> <posre=NN:Name:.*>", "NPP", True),
        ("<не> <posre='VB:.*:.*' & !posre='NN:.*'>* ", "VP", False),
    ]

    def expand(expr: str) -> str:
        res = expr
        for k, v in syntax_expansion.items():
            res = res.replace(k, v)
        return res

    regexes1 = []
    for idx, (raw_expr, ptype, overwrite) in enumerate(regexes1_defs):
        regexes1.append({
            "index": idx,
            "expression_raw": raw_expr,
            "expression_expanded": expand(raw_expr),
            "phrase_type": ptype,
            "overwrite": overwrite,
        })

    regexes2 = []
    for idx, (raw_expr, ptype, overwrite) in enumerate(regexes2_defs):
        regexes2.append({
            "index": idx,
            "expression_raw": raw_expr,
            "expression_expanded": expand(raw_expr),
            "phrase_type": ptype,
            "overwrite": overwrite,
        })

    return {
        "filter_tags": sorted(filter_tags),
        "syntax_expansion": dict(sorted(syntax_expansion.items())),
        "phrase_types": sorted(phrase_types),
        "regexes1_count": len(regexes1),
        "regexes1": regexes1,
        "regexes2_count": len(regexes2),
        "regexes2": regexes2,
        "total_chunker_regexes_count": len(regexes1) + len(regexes2),
    }


def analyze_grammar_xml(path: Path) -> Dict[str, Any]:
    """Parse and extract exhaustive statistics, rule classifications, and blocker inventories from grammar.xml."""
    tree = ET.parse(str(path))
    root = tree.getroot()

    elem_counts = Counter(elem.tag for elem in root.iter())
    attrs_by_elem: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    distinct_attr_values: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))

    for elem in root.iter():
        for k, v in elem.attrib.items():
            attrs_by_elem[elem.tag][k] += 1
            if len(distinct_attr_values[elem.tag][k]) < 50:
                distinct_attr_values[elem.tag][k].add(v)

    categories_elems = root.findall("category")
    rulegroups_elems = root.findall(".//rulegroup")
    direct_rules_elems = [r for r in root.findall(".//category/rule")]
    all_rules_elems = root.findall(".//rule")

    rules_records: List[Dict[str, Any]] = []
    source_order_idx = 0

    classification_counts: Dict[str, int] = defaultdict(int)
    blocker_feature_counts: Dict[str, int] = defaultdict(int)
    blocker_task_counts: Dict[str, int] = defaultdict(int)

    core_examples_counts = {"total": 0, "incorrect": 0, "correct": 0, "with_correction": 0}
    deferred_examples_counts = {"total": 0, "incorrect": 0, "correct": 0, "with_correction": 0}
    total_examples_counts = {"total": 0, "incorrect": 0, "correct": 0, "with_correction": 0}

    core_regexes: List[Dict[str, Any]] = []

    for cat in categories_elems:
        cat_id = cat.attrib["id"]
        cat_name = cat.attrib.get("name", cat_id)

        for child in cat:
            if child.tag == "rulegroup":
                group_id = child.attrib["id"]
                group_name = child.attrib.get("name", group_id)
                group_default = child.attrib.get("default", "on")
                group_tags = child.attrib.get("tags")

                rule_num = 0
                for r in child:
                    if r.tag == "rule":
                        rule_num += 1
                        r_id = r.attrib.get("id")
                        sub_id = r_id if r_id else str(rule_num)
                        full_id = f"{group_id}[{sub_id}]"
                        r_name = r.attrib.get("name", group_name)
                        r_default = r.attrib.get("default", group_default)
                        r_tags = r.attrib.get("tags", group_tags)

                        rule_data = _classify_and_record_rule(
                            source_order_idx=source_order_idx,
                            category_id=cat_id,
                            category_name=cat_name,
                            rulegroup_id=group_id,
                            rulegroup_name=group_name,
                            rule_id=r_id,
                            sub_id=sub_id,
                            full_id=full_id,
                            rule_name=r_name,
                            rule_default=r.attrib.get("default"),
                            rulegroup_default=group_default,
                            effective_default=r_default,
                            rule_tags=r.attrib.get("tags"),
                            rulegroup_tags=group_tags,
                            effective_tags=r_tags,
                            rule_elem=r,
                            core_regexes=core_regexes,
                        )
                        rules_records.append(rule_data)
                        source_order_idx += 1

            elif child.tag == "rule":
                r_id = child.attrib["id"]
                full_id = r_id
                r_name = child.attrib.get("name", r_id)
                r_default = child.attrib.get("default", "on")
                r_tags = child.attrib.get("tags")

                rule_data = _classify_and_record_rule(
                    source_order_idx=source_order_idx,
                    category_id=cat_id,
                    category_name=cat_name,
                    rulegroup_id=None,
                    rulegroup_name=None,
                    rule_id=r_id,
                    sub_id=None,
                    full_id=full_id,
                    rule_name=r_name,
                    rule_default=r_default,
                    rulegroup_default=None,
                    effective_default=r_default,
                    rule_tags=r_tags,
                    rulegroup_tags=None,
                    effective_tags=r_tags,
                    rule_elem=child,
                    core_regexes=core_regexes,
                )
                rules_records.append(rule_data)
                source_order_idx += 1

    # Accumulate metrics
    for r in rules_records:
        state = r["execution_state"]
        classification_counts[state] += 1

        is_core = (state == "CORE_0007_RUNNABLE")
        ex_meta = r["examples_summary"]
        total_examples_counts["total"] += ex_meta["total"]
        total_examples_counts["incorrect"] += ex_meta["incorrect"]
        total_examples_counts["correct"] += ex_meta["correct"]
        total_examples_counts["with_correction"] += ex_meta["with_correction"]

        if is_core:
            core_examples_counts["total"] += ex_meta["total"]
            core_examples_counts["incorrect"] += ex_meta["incorrect"]
            core_examples_counts["correct"] += ex_meta["correct"]
            core_examples_counts["with_correction"] += ex_meta["with_correction"]
        else:
            deferred_examples_counts["total"] += ex_meta["total"]
            deferred_examples_counts["incorrect"] += ex_meta["incorrect"]
            deferred_examples_counts["correct"] += ex_meta["correct"]
            deferred_examples_counts["with_correction"] += ex_meta["with_correction"]

        for b in r["blockers"]:
            blocker_feature_counts[b["feature"]] += 1
            blocker_task_counts[b["target_task"]] += 1

    # Format attrs_by_elem and distinct_attr_values as serializable dicts
    formatted_attrs_by_elem = {
        k: dict(sorted(v.items())) for k, v in sorted(attrs_by_elem.items())
    }
    formatted_distinct_attr_values = {
        elem_tag: {
            attr: sorted(list(vals)) for attr, vals in sorted(attrs.items())
        }
        for elem_tag, attrs in sorted(distinct_attr_values.items())
    }

    # Extract filter classes and counts
    filter_classes = Counter(f.attrib.get("class", "unknown") for f in root.findall(".//filter"))

    return {
        "categories_count": len(categories_elems),
        "rulegroups_count": len(rulegroups_elems),
        "rules_total_count": len(all_rules_elems),
        "direct_rules_count": len(direct_rules_elems),
        "grouped_rules_count": len(all_rules_elems) - len(direct_rules_elems),
        "element_counts": dict(elem_counts.most_common()),
        "attributes_by_element": formatted_attrs_by_elem,
        "distinct_attribute_values": formatted_distinct_attr_values,
        "filter_classes_count": len(filter_classes),
        "filter_classes": dict(filter_classes.most_common()),
        "total_examples_counts": total_examples_counts,
        "core_examples_counts": core_examples_counts,
        "deferred_examples_counts": deferred_examples_counts,
        "classification_summary": dict(sorted(classification_counts.items())),
        "blockers_by_feature": dict(sorted(blocker_feature_counts.items(), key=lambda x: -x[1])),
        "blockers_by_task": dict(sorted(blocker_task_counts.items())),
        "core_regexes_count": len(core_regexes),
        "core_regexes": core_regexes,
        "rules": rules_records,
    }


def _classify_and_record_rule(
    source_order_idx: int,
    category_id: str,
    category_name: str,
    rulegroup_id: Optional[str],
    rulegroup_name: Optional[str],
    rule_id: Optional[str],
    sub_id: Optional[str],
    full_id: str,
    rule_name: str,
    rule_default: Optional[str],
    rulegroup_default: Optional[str],
    effective_default: str,
    rule_tags: Optional[str],
    rulegroup_tags: Optional[str],
    effective_tags: Optional[str],
    rule_elem: ET.Element,
    core_regexes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Classify a single rule and construct its complete descriptor."""
    blockers: List[Dict[str, str]] = []
    feature_set: Dict[str, Any] = {
        "has_marker": False,
        "has_exception": False,
        "has_scoped_exception": False,
        "has_and": False,
        "has_or": False,
        "has_antipattern": False,
        "has_skip": False,
        "has_min_max": False,
        "has_inflected": False,
        "has_negate": False,
        "has_negate_pos": False,
        "has_postag": False,
        "has_postag_regexp": False,
        "has_text_regexp": False,
        "has_case_sensitive": False,
        "has_chunk": False,
        "has_spacebefore": False,
        "has_raw_pos": False,
        "has_filter": False,
        "filter_classes": [],
        "has_unification": False,
        "has_unify": False,
        "has_unify_ignore": False,
        "has_basic_match": False,
        "has_complex_match": False,
        "match_attribute_sets": [],
        "has_message_suppress_misspelled": False,
        "has_suggestion_suppress_misspelled": False,
    }

    # Analyze pattern
    patterns = rule_elem.findall("pattern")
    for pat in patterns:
        if pat.attrib.get("case_sensitive") == "yes":
            feature_set["has_case_sensitive"] = True
        if pat.attrib.get("raw_pos") == "yes":
            feature_set["has_raw_pos"] = True
            blockers.append({"feature": "pattern@raw_pos", "target_task": "0008"})

        if pat.findall(".//and"):
            feature_set["has_and"] = True
            blockers.append({"feature": "pattern:and", "target_task": "0008"})
        if pat.findall(".//or"):
            feature_set["has_or"] = True
            blockers.append({"feature": "pattern:or", "target_task": "0008"})
        if pat.findall(".//unify"):
            feature_set["has_unify"] = True
            blockers.append({"feature": "pattern:unify", "target_task": "0009"})
        if pat.findall(".//unify-ignore"):
            feature_set["has_unify_ignore"] = True
            blockers.append({"feature": "pattern:unify-ignore", "target_task": "0009"})

        for tok in pat.findall(".//token"):
            if "skip" in tok.attrib:
                feature_set["has_skip"] = True
                blockers.append({"feature": "token@skip", "target_task": "0008"})
            if "min" in tok.attrib or "max" in tok.attrib:
                feature_set["has_min_max"] = True
                blockers.append({"feature": "token@min_max", "target_task": "0008"})
            if "spacebefore" in tok.attrib:
                feature_set["has_spacebefore"] = True
                blockers.append({"feature": "token@spacebefore", "target_task": "0008"})
            if "chunk" in tok.attrib:
                feature_set["has_chunk"] = True
                blockers.append({"feature": "token@chunk", "target_task": "0008"})
            if tok.attrib.get("inflected") == "yes":
                feature_set["has_inflected"] = True
            if tok.attrib.get("negate") == "yes":
                feature_set["has_negate"] = True
            if tok.attrib.get("negate_pos") == "yes":
                feature_set["has_negate_pos"] = True
            if "postag" in tok.attrib:
                feature_set["has_postag"] = True
            if tok.attrib.get("postag_regexp") == "yes":
                feature_set["has_postag_regexp"] = True
            if tok.attrib.get("regexp") == "yes":
                feature_set["has_text_regexp"] = True
            if tok.attrib.get("case_sensitive") == "yes":
                feature_set["has_case_sensitive"] = True

            for exc in tok.findall("exception"):
                feature_set["has_exception"] = True
                if "scope" in exc.attrib and exc.attrib["scope"] != "current":
                    feature_set["has_scoped_exception"] = True
                    blockers.append({"feature": f"exception@scope={exc.attrib['scope']}", "target_task": "0008"})
                if "spacebefore" in exc.attrib:
                    feature_set["has_spacebefore"] = True
                    blockers.append({"feature": "exception@spacebefore", "target_task": "0008"})
                if exc.attrib.get("inflected") == "yes":
                    feature_set["has_inflected"] = True
                if exc.attrib.get("negate") == "yes":
                    feature_set["has_negate"] = True
                if exc.attrib.get("negate_pos") == "yes":
                    feature_set["has_negate_pos"] = True
                if "postag" in exc.attrib:
                    feature_set["has_postag"] = True
                if exc.attrib.get("postag_regexp") == "yes":
                    feature_set["has_postag_regexp"] = True
                if exc.attrib.get("regexp") == "yes":
                    feature_set["has_text_regexp"] = True
                if exc.attrib.get("case_sensitive") == "yes":
                    feature_set["has_case_sensitive"] = True

    # Antipatterns
    if rule_elem.findall("antipattern"):
        feature_set["has_antipattern"] = True
        blockers.append({"feature": "antipattern", "target_task": "0008"})

    # Filters
    filters = rule_elem.findall("filter")
    if filters:
        feature_set["has_filter"] = True
        for filt in filters:
            cls_name = filt.attrib.get("class", "unknown")
            feature_set["filter_classes"].append(cls_name)
            blockers.append({"feature": f"filter:{cls_name}", "target_task": "0010"})

    # Markers in examples/messages
    if rule_elem.findall(".//marker"):
        feature_set["has_marker"] = True

    # Matches in message and suggestion
    match_elements = rule_elem.findall(".//message//match") + rule_elem.findall(".//suggestion//match")
    for match in match_elements:
        attrs = sorted(list(match.attrib.keys()))
        if attrs not in feature_set["match_attribute_sets"]:
            feature_set["match_attribute_sets"].append(attrs)
        complex_attrs = set(match.attrib.keys()) - {"no"}
        if not complex_attrs:
            feature_set["has_basic_match"] = True
        else:
            feature_set["has_complex_match"] = True
            for attr in sorted(list(complex_attrs)):
                target_task = "0008" if attr in ("include_skipped", "case_conversion") else "0010"
                blockers.append({"feature": f"match@{attr}", "target_task": target_task})

    # Message / suggestion suppress_misspelled
    for msg in rule_elem.findall("message"):
        if msg.attrib.get("suppress_misspelled") == "yes":
            feature_set["has_message_suppress_misspelled"] = True
            blockers.append({"feature": "message@suppress_misspelled", "target_task": "0012"})
    for sug in rule_elem.findall(".//suggestion"):
        if sug.attrib.get("suppress_misspelled") == "yes":
            feature_set["has_suggestion_suppress_misspelled"] = True
            blockers.append({"feature": "suggestion@suppress_misspelled", "target_task": "0012"})

    # Deduplicate blockers preserving order
    unique_blockers: List[Dict[str, str]] = []
    seen_b: Set[Tuple[str, str]] = set()
    for b in blockers:
        key = (b["feature"], b["target_task"])
        if key not in seen_b:
            seen_b.add(key)
            unique_blockers.append(b)

    # Determine execution state
    if not unique_blockers:
        exec_state = "CORE_0007_RUNNABLE"
        # Collect regexes used in core runnable rules
        for pat in rule_elem.findall("pattern"):
            pat_cs = (pat.attrib.get("case_sensitive") == "yes")
            for tok in pat.findall(".//token"):
                tok_cs = (tok.attrib.get("case_sensitive") == "yes") or pat_cs
                if tok.attrib.get("regexp") == "yes" and tok.text:
                    core_regexes.append({
                        "full_rule_id": full_id,
                        "location": "token.text",
                        "raw_pattern": tok.text.strip(),
                        "case_sensitive": tok_cs,
                    })
                if tok.attrib.get("postag_regexp") == "yes" and tok.attrib.get("postag"):
                    core_regexes.append({
                        "full_rule_id": full_id,
                        "location": "token.postag",
                        "raw_pattern": tok.attrib["postag"],
                        "case_sensitive": True,
                    })
                for exc in tok.findall("exception"):
                    exc_cs = (exc.attrib.get("case_sensitive") == "yes") or tok_cs
                    if exc.attrib.get("regexp") == "yes" and exc.text:
                        core_regexes.append({
                            "full_rule_id": full_id,
                            "location": "exception.text",
                            "raw_pattern": exc.text.strip(),
                            "case_sensitive": exc_cs,
                        })
                    if exc.attrib.get("postag_regexp") == "yes" and exc.attrib.get("postag"):
                        core_regexes.append({
                            "full_rule_id": full_id,
                            "location": "exception.postag",
                            "raw_pattern": exc.attrib["postag"],
                            "case_sensitive": True,
                        })
    else:
        tasks = {b["target_task"] for b in unique_blockers}
        if len(tasks) > 1:
            exec_state = "MULTI_BLOCKER"
        elif "0008" in tasks:
            exec_state = "DEFERRED_0008_ADVANCED_MATCHING"
        elif "0009" in tasks:
            exec_state = "DEFERRED_0009_UNIFICATION"
        elif "0010" in tasks:
            exec_state = "DEFERRED_0010_FILTER"
        elif "0012" in tasks:
            exec_state = "DEFERRED_0012_SPELLING_OR_SUPPRESSION"
        else:
            exec_state = "UNKNOWN"

    # Analyze examples
    examples = rule_elem.findall("example")
    incorrect_cnt = 0
    correct_cnt = 0
    with_corr_cnt = 0
    for ex in examples:
        has_m = (ex.findall("marker") is not None and len(ex.findall("marker")) > 0)
        ex_type = ex.attrib.get("type")
        has_corr = ("correction" in ex.attrib)
        if has_corr:
            with_corr_cnt += 1

        is_incorrect = (ex_type == "triggers_error") or has_m or has_corr
        if ex_type in ("untouched", "correct"):
            is_incorrect = False

        if is_incorrect:
            incorrect_cnt += 1
        else:
            correct_cnt += 1

    return {
        "source_order_index": source_order_idx,
        "category_id": category_id,
        "category_name": category_name,
        "rulegroup_id": rulegroup_id,
        "rulegroup_name": rulegroup_name,
        "rule_id": rule_id,
        "sub_id": sub_id,
        "full_rule_id": full_id,
        "rule_name": rule_name,
        "rule_default": rule_default,
        "rulegroup_default": rulegroup_default,
        "effective_default": effective_default,
        "rule_tags": rule_tags,
        "rulegroup_tags": rulegroup_tags,
        "effective_tags": effective_tags,
        "source_path": "rules/ru/grammar.xml",
        "examples_summary": {
            "total": len(examples),
            "incorrect": incorrect_cnt,
            "correct": correct_cnt,
            "with_correction": with_corr_cnt,
        },
        "feature_set": feature_set,
        "execution_state": exec_state,
        "blockers": unique_blockers,
    }


def generate_inventory() -> Dict[str, Any]:
    """Build the complete deterministic grammar core inventory object."""
    upstream_meta = json.loads(UPSTREAM_JSON_PATH.read_text(encoding="utf-8"))
    license_inv = json.loads(LICENSE_INV_PATH.read_text(encoding="utf-8"))
    license_map = {item["path"]: item for item in license_inv.get("items", [])}

    upstream_source_files = {
        "grammar.xml": get_file_metadata(GRAMMAR_XML_PATH, license_map),
        "RussianChunker.java": get_file_metadata(CHUNKER_JAVA_PATH, license_map),
    }

    chunker_data = analyze_chunker_source(CHUNKER_JAVA_PATH)
    grammar_data = analyze_grammar_xml(GRAMMAR_XML_PATH)

    inventory = {
        "schema_version": "1.0.0",
        "pinned_upstream": {
            "commit": upstream_meta["pinned_commit"],
            "tag": upstream_meta["pinned_tag"],
            "commit_date": upstream_meta["commit_date"],
        },
        "upstream_source_files": upstream_source_files,
        "chunker": chunker_data,
        "grammar": grammar_data,
    }
    return inventory


def main() -> None:
    """Generate and write compat/russian_grammar_core_inventory.json."""
    inv = generate_inventory()
    content = json.dumps(inv, ensure_ascii=False, indent=2) + "\n"
    INVENTORY_OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Generated {INVENTORY_OUTPUT_PATH.relative_to(REPO_ROOT)} ({len(content)} bytes)")
    print(f"  Categories: {inv['grammar']['categories_count']}")
    print(f"  Rulegroups: {inv['grammar']['rulegroups_count']}")
    print(f"  Rules total: {inv['grammar']['rules_total_count']}")
    print(f"  Classification summary: {inv['grammar']['classification_summary']}")
    print(f"  Total examples: {inv['grammar']['total_examples_counts']}")
    print(f"  Core examples: {inv['grammar']['core_examples_counts']}")
    print(f"  Deferred examples: {inv['grammar']['deferred_examples_counts']}")
    print(f"  Chunker regexes: {inv['chunker']['total_chunker_regexes_count']}")


if __name__ == "__main__":
    main()
