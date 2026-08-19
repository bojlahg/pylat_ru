"""tools/russian_disambiguator_inventory.py

Deterministic generator for compat/russian_disambiguator_inventory.json.
Extracts comprehensive metadata, hashes, rule IDs, active XML tags, attributes by element,
exception scopes, actions, match/wd attributes, skip distributions, pattern constructs,
filters, multiword statistics, and test examples directly from pinned upstream LanguageTool
Russian disambiguation resources and source files.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
INVENTORY_OUTPUT_PATH = REPO_ROOT / "compat" / "russian_disambiguator_inventory.json"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def analyze_multiwords_file(path: Path) -> Dict[str, Any]:
    """Parse and calculate exact statistics for multiwords.txt."""
    lines = path.read_text(encoding="utf-8").splitlines()
    data_lines = []
    tags: Set[str] = set()
    length_distribution: Dict[str, int] = {}
    phrases: List[str] = []
    seen_phrases: Set[str] = set()
    duplicates: List[str] = []
    single_token_entries: List[str] = []

    for line in lines:
        s = line.strip(" \t\r\n")
        if not s or s.startswith("#"):
            continue
        clean = s.split("#", 1)[0].strip(" \t\r\n")
        if not clean:
            continue
        data_lines.append(clean)
        parts = clean.split("\t")
        if len(parts) == 2:
            phrase, tag = parts[0].strip(), parts[1].strip()
            tags.add(tag)
            if phrase in seen_phrases:
                duplicates.append(phrase)
            seen_phrases.add(phrase)
            phrases.append(phrase)

            words = phrase.split(" ")
            n_words = len(words)
            if n_words == 1:
                single_token_entries.append(phrase)
            key = f"{n_words}_words"
            length_distribution[key] = length_distribution.get(key, 0) + 1

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "total_lines_count": len(lines),
        "data_lines_count": len(data_lines),
        "distinct_phrases_count": len(seen_phrases),
        "duplicate_phrases_count": len(duplicates),
        "duplicate_phrases": duplicates,
        "single_token_entries_count": len(single_token_entries),
        "single_token_entries": single_token_entries,
        "unique_tags_count": len(tags),
        "unique_tags": sorted(list(tags)),
        "phrase_length_distribution": dict(sorted(length_distribution.items())),
        "max_phrase_words_count": max((len(p.split(" ")) for p in phrases), default=0),
    }


def analyze_disambiguation_xml(path: Path) -> Dict[str, Any]:
    """Parse and calculate exhaustive statistics for disambiguation.xml."""
    tree = ET.parse(str(path))
    root = tree.getroot()

    all_rules = root.findall(".//rule")
    rulegroups = root.findall("rulegroup")
    top_rules = [c for c in root if c.tag == "rule"]

    used_tags: Set[str] = set()
    attrs_by_tag: Dict[str, Set[str]] = {}

    for elem in root.iter():
        if isinstance(elem.tag, str):
            used_tags.add(elem.tag)
            if elem.tag not in attrs_by_tag:
                attrs_by_tag[elem.tag] = set()
            for a in elem.attrib:
                attrs_by_tag[elem.tag].add(a)

    actions_count: Dict[str, int] = {}
    default_actions_count = 0
    filters_list: List[Dict[str, str]] = []
    filter_classes: Set[str] = set()
    filter_arg_keys: Set[str] = set()
    rule_ids: List[str] = []
    full_rule_ids: List[str] = []
    examples: List[Dict[str, Any]] = []

    exception_scopes: Dict[str, int] = {}
    skip_values: Dict[str, int] = {}
    match_attributes: Set[str] = set()
    wd_attributes: Set[str] = set()

    marker_count = 0
    antipattern_count = 0
    and_count = 0
    exception_count = 0
    regexp_count = 0
    postag_regexp_count = 0
    inflected_count = 0
    negate_count = 0
    negate_pos_count = 0
    case_sensitive_count = 0

    def _collect_rule_stats(rule_elem: ET.Element) -> None:
        nonlocal marker_count, antipattern_count, and_count, exception_count
        nonlocal regexp_count, postag_regexp_count, inflected_count, negate_count, negate_pos_count, case_sensitive_count
        nonlocal default_actions_count

        for ap in rule_elem.findall("antipattern"):
            antipattern_count += 1

        pattern = rule_elem.find("pattern")
        if pattern is not None:
            if pattern.attrib.get("case_sensitive", "no").lower() in ("yes", "true", "1"):
                case_sensitive_count += 1

            for m in pattern.findall(".//marker"):
                marker_count += 1
            for a in pattern.findall(".//and"):
                and_count += 1

            for tok in pattern.findall(".//token"):
                if tok.attrib.get("regexp", "no").lower() in ("yes", "true", "1"):
                    regexp_count += 1
                if tok.attrib.get("postag_regexp", "no").lower() in ("yes", "true", "1"):
                    postag_regexp_count += 1
                if tok.attrib.get("inflected", "no").lower() in ("yes", "true", "1"):
                    inflected_count += 1
                if tok.attrib.get("negate", "no").lower() in ("yes", "true", "1"):
                    negate_count += 1
                if tok.attrib.get("negate_pos", "no").lower() in ("yes", "true", "1"):
                    negate_pos_count += 1
                if tok.attrib.get("case_sensitive", "no").lower() in ("yes", "true", "1"):
                    case_sensitive_count += 1
                if "skip" in tok.attrib:
                    s_val = tok.attrib["skip"]
                    skip_values[s_val] = skip_values.get(s_val, 0) + 1

                for exc in tok.findall("exception"):
                    exception_count += 1
                    sc = exc.attrib.get("scope", "current")
                    exception_scopes[sc] = exception_scopes.get(sc, 0) + 1
                    if exc.attrib.get("regexp", "no").lower() in ("yes", "true", "1"):
                        regexp_count += 1
                    if exc.attrib.get("postag_regexp", "no").lower() in ("yes", "true", "1"):
                        postag_regexp_count += 1
                    if exc.attrib.get("inflected", "no").lower() in ("yes", "true", "1"):
                        inflected_count += 1
                    if exc.attrib.get("negate", "no").lower() in ("yes", "true", "1"):
                        negate_count += 1
                    if exc.attrib.get("negate_pos", "no").lower() in ("yes", "true", "1"):
                        negate_pos_count += 1
                    if exc.attrib.get("case_sensitive", "no").lower() in ("yes", "true", "1"):
                        case_sensitive_count += 1

        disambig = rule_elem.find("disambig")
        if disambig is not None:
            if "action" in disambig.attrib:
                act = disambig.attrib["action"]
                actions_count[act] = actions_count.get(act, 0) + 1
            else:
                default_actions_count += 1
                actions_count["replace (default)"] = actions_count.get("replace (default)", 0) + 1

            for wd in disambig.findall("wd"):
                for a in wd.attrib:
                    wd_attributes.add(a)

            for m in disambig.findall("match"):
                for a in m.attrib:
                    match_attributes.add(a)

        filt = rule_elem.find("filter")
        if filt is not None:
            f_cls = filt.attrib.get("class", "")
            f_args = filt.attrib.get("args", "")
            filter_classes.add(f_cls)
            for pair in f_args.strip().split():
                if ":" in pair:
                    k, _ = pair.split(":", 1)
                    filter_arg_keys.add(k)
            filters_list.append({
                "rule_id": rule_elem.attrib.get("id") or rule_elem.attrib.get("name", ""),
                "class": f_cls,
                "args": f_args,
            })

        for ex in rule_elem.findall("example"):
            raw_xml = (ex.text or "") + "".join(ET.tostring(c, encoding="unicode") for c in ex)
            examples.append({
                "rule_id": rule_elem.attrib.get("id") or rule_elem.attrib.get("name", ""),
                "type": ex.attrib.get("type", "ambiguous"),
                "inputform": ex.attrib.get("inputform"),
                "outputform": ex.attrib.get("outputform"),
                "raw_xml": raw_xml.strip(),
            })

    rule_counter = 0
    for child in root:
        if child.tag == "rulegroup":
            rg_id = child.attrib.get("id", "")
            for ap in child.findall("antipattern"):
                antipattern_count += 1
            for sub_idx, sub_rule in enumerate(child.findall("rule"), 1):
                rule_counter += 1
                sub_id = sub_rule.attrib.get("id")
                full_id = f"{rg_id}[{sub_id}]" if sub_id else f"{rg_id}[{sub_idx}]"
                r_id = sub_id or rg_id
                rule_ids.append(r_id)
                full_rule_ids.append(full_id)
                _collect_rule_stats(sub_rule)
        elif child.tag == "rule":
            rule_counter += 1
            r_id = child.attrib.get("id") or child.attrib.get("name", f"rule_{rule_counter}")
            rule_ids.append(r_id)
            full_rule_ids.append(r_id)
            _collect_rule_stats(child)

    formatted_attrs_by_tag = {
        tag: sorted(list(attrs)) for tag, attrs in sorted(attrs_by_tag.items())
    }

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "total_rules_count": len(all_rules),
        "top_level_rules_count": len(top_rules),
        "rulegroups_count": len(rulegroups),
        "used_xml_tags": sorted(list(used_tags)),
        "attributes_by_element": formatted_attrs_by_tag,
        "actions_distribution": dict(sorted(actions_count.items())),
        "default_actions_count": default_actions_count,
        "match_attributes": sorted(list(match_attributes)),
        "wd_attributes": sorted(list(wd_attributes)),
        "skip_values_distribution": dict(sorted(skip_values.items())),
        "exception_scopes_distribution": dict(sorted(exception_scopes.items())),
        "construct_counts": {
            "markers": marker_count,
            "antipatterns": antipattern_count,
            "and_conjunctions": and_count,
            "exceptions": exception_count,
            "regexp_attributes": regexp_count,
            "postag_regexp_attributes": postag_regexp_count,
            "inflected_attributes": inflected_count,
            "negate_attributes": negate_count,
            "negate_pos_attributes": negate_pos_count,
            "case_sensitive_attributes": case_sensitive_count,
        },
        "filters_count": len(filters_list),
        "filter_classes": sorted(list(filter_classes)),
        "filter_argument_keys": sorted(list(filter_arg_keys)),
        "filters": filters_list,
        "examples_count": len(examples),
        "examples": examples,
        "rule_ids_source_order": rule_ids,
        "full_rule_ids_source_order": full_rule_ids,
    }


def generate_russian_disambiguator_inventory() -> Dict[str, Any]:
    """Generate complete compatibility inventory for Russian disambiguator."""
    upstream = json.loads(UPSTREAM_JSON_PATH.read_text(encoding="utf-8"))
    ru_res_dir = (
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
        / "resource"
        / "ru"
    )

    ru_src_dir = (
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
    )

    hybrid_src = ru_src_dir / "tagging" / "disambiguation" / "ru" / "RussianHybridDisambiguator.java"
    filter_src = ru_src_dir / "rules" / "ru" / "NoDisambiguationRussianPartialPosTagFilter.java"

    multiwords_path = ru_res_dir / "multiwords.txt"
    disambig_path = ru_res_dir / "disambiguation.xml"

    multiwords_analysis = analyze_multiwords_file(multiwords_path)
    disambig_analysis = analyze_disambiguation_xml(disambig_path)

    pkg_res_dir = REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru"
    pkg_multiwords = pkg_res_dir / "multiwords.txt"
    pkg_disambig = pkg_res_dir / "disambiguation.xml"

    packaged_resources = {
        "multiwords.txt": {
            "path": str(pkg_multiwords.relative_to(REPO_ROOT)).replace("\\", "/"),
            "size": pkg_multiwords.stat().st_size if pkg_multiwords.is_file() else None,
            "sha256": sha256_file(pkg_multiwords) if pkg_multiwords.is_file() else None,
            "matches_upstream": sha256_file(pkg_multiwords) == multiwords_analysis["sha256"] if pkg_multiwords.is_file() else False,
        },
        "disambiguation.xml": {
            "path": str(pkg_disambig.relative_to(REPO_ROOT)).replace("\\", "/"),
            "size": pkg_disambig.stat().st_size if pkg_disambig.is_file() else None,
            "sha256": sha256_file(pkg_disambig) if pkg_disambig.is_file() else None,
            "matches_upstream": sha256_file(pkg_disambig) == disambig_analysis["sha256"] if pkg_disambig.is_file() else False,
        },
    }

    upstream_source_files = {
        "RussianHybridDisambiguator.java": {
            "path": str(hybrid_src.relative_to(REPO_ROOT)).replace("\\", "/"),
            "size": hybrid_src.stat().st_size if hybrid_src.is_file() else None,
            "sha256": sha256_file(hybrid_src) if hybrid_src.is_file() else None,
        },
        "NoDisambiguationRussianPartialPosTagFilter.java": {
            "path": str(filter_src.relative_to(REPO_ROOT)).replace("\\", "/"),
            "size": filter_src.stat().st_size if filter_src.is_file() else None,
            "sha256": sha256_file(filter_src) if filter_src.is_file() else None,
        },
    }

    return {
        "schema_version": "1.0.0",
        "pinned_upstream": {
            "commit": upstream["pinned_commit"],
            "tag": upstream["pinned_tag"],
            "commit_date": upstream["commit_date"],
        },
        "upstream_source_files": upstream_source_files,
        "multiwords": multiwords_analysis,
        "disambiguation_xml": disambig_analysis,
        "packaged_runtime_resources": packaged_resources,
        "pipeline_status": {
            "RussianSentenceAnalyzer": "SUPPORTED",
            "MultiWordChunker": "SUPPORTED",
            "XmlRuleDisambiguator": "SUPPORTED",
            "RussianHybridDisambiguator": "SUPPORTED",
            "NoDisambiguationRussianPartialPosTagFilter": "SUPPORTED",
        },
    }


def main() -> int:
    inventory = generate_russian_disambiguator_inventory()
    INVENTORY_OUTPUT_PATH.write_text(
        json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Generated {INVENTORY_OUTPUT_PATH}")
    print(f"  Multiwords distinct phrases: {inventory['multiwords']['distinct_phrases_count']}")
    print(f"  Disambiguation XML total rules: {inventory['disambiguation_xml']['total_rules_count']}")
    print(f"  Disambiguation XML filters: {inventory['disambiguation_xml']['filters_count']}")
    print(f"  Disambiguation XML examples: {inventory['disambiguation_xml']['examples_count']}")
    print(f"  Construct counts: {inventory['disambiguation_xml']['construct_counts']}")
    return 0


if __name__ == "__main__":
    main()
