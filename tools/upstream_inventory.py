#!/usr/bin/env python3
"""tools/upstream_inventory.py

Extracts the full Russian compatibility surface and module inventory from
the pinned LanguageTool upstream assets.

Outputs deterministic JSON to compat/inventory.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set


def get_default_upstream_dir() -> Path:
    """Return the default path to third_party/languagetool."""
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "third_party" / "languagetool"


def get_default_output_path() -> Path:
    """Return the default path to compat/inventory.json."""
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "compat" / "inventory.json"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def scan_resource_files(upstream_dir: Path) -> Dict[str, Any]:
    """Scan all Russian resource and rule files, recording paths, sizes, and hashes."""
    ru_base = upstream_dir / "languagetool-language-modules" / "ru"
    resources: Dict[str, Any] = {}

    if not ru_base.exists():
        return resources

    for path in sorted(ru_base.rglob("*")):
        if path.is_file():
            rel_path = path.relative_to(upstream_dir).as_posix()
            resources[rel_path] = {
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }

    # Also include segment.srx if present
    segment_srx = upstream_dir / "languagetool-core" / "src" / "main" / "resources" / "org" / "languagetool" / "resource" / "segment.srx"
    if segment_srx.is_file():
        rel = segment_srx.relative_to(upstream_dir).as_posix()
        resources[rel] = {
            "size_bytes": segment_srx.stat().st_size,
            "sha256": sha256_file(segment_srx),
        }

    return resources


def analyze_xml_structure(root: ET.Element) -> Dict[str, Any]:
    """Extract all element tags, attribute pairs, and hierarchical stats from an XML root."""
    tag_counts: Dict[str, int] = {}
    attr_counts: Dict[str, int] = {}

    for elem in root.iter():
        tag = elem.tag
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
        for attr, val in elem.attrib.items():
            pair = f"{tag}@{attr}"
            attr_counts[pair] = attr_counts.get(pair, 0) + 1

    return {
        "tag_counts": dict(sorted(tag_counts.items())),
        "attribute_counts": dict(sorted(attr_counts.items())),
    }


def analyze_grammar_xml(grammar_path: Path) -> Dict[str, Any]:
    """Analyze grammar.xml in detail."""
    if not grammar_path.is_file():
        return {"error": f"File not found: {grammar_path}"}

    tree = ET.parse(grammar_path)
    root = tree.getroot()

    xml_struct = analyze_xml_structure(root)

    # Categories
    categories = []
    for cat in root.findall("category"):
        cat_id = cat.attrib.get("id", "")
        cat_name = cat.attrib.get("name", "")
        cat_default = cat.attrib.get("default", "on")
        rulegroups_in_cat = cat.findall("rulegroup")
        direct_rules_in_cat = cat.findall("rule")
        all_rules_in_cat = cat.findall(".//rule")

        categories.append({
            "id": cat_id,
            "name": cat_name,
            "default": cat_default,
            "rulegroup_count": len(rulegroups_in_cat),
            "direct_rule_count": len(direct_rules_in_cat),
            "total_rule_count": len(all_rules_in_cat),
        })

    # Rulegroups
    rulegroups = []
    for rg in root.findall(".//rulegroup"):
        rg_id = rg.attrib.get("id", "")
        rg_name = rg.attrib.get("name", "")
        rg_default = rg.attrib.get("default", "on")
        rules_in_rg = rg.findall("rule")
        rulegroups.append({
            "id": rg_id,
            "name": rg_name,
            "default": rg_default,
            "rule_count": len(rules_in_rg),
        })

    # Total rules & examples
    all_rules = root.findall(".//rule")
    all_examples = root.findall(".//example")
    incorrect_examples = [
        e for e in all_examples
        if e.attrib.get("type") == "incorrect" or e.find("marker") is not None
    ]
    correct_examples = [
        e for e in all_examples
        if e.attrib.get("type") == "correct" or (e.attrib.get("type") is None and e.find("marker") is None)
    ]
    examples_with_corrections = [
        e for e in all_examples
        if e.find("correction") is not None or "correction" in e.attrib
    ]

    # Filters referenced
    filter_elements = root.findall(".//filter")
    filters_used: Dict[str, int] = {}
    for f in filter_elements:
        cls_name = f.attrib.get("class")
        if cls_name:
            filters_used[cls_name] = filters_used.get(cls_name, 0) + 1

    # Unifications
    unifications = []
    for u in root.findall(".//unification"):
        feature = u.attrib.get("feature", "")
        equiv_count = len(u.findall("equivalence"))
        unifications.append({
            "feature": feature,
            "equivalence_count": equiv_count,
        })

    return {
        "file": grammar_path.name,
        "size_bytes": grammar_path.stat().st_size,
        "sha256": sha256_file(grammar_path),
        "xml_structure": xml_struct,
        "category_count": len(categories),
        "rulegroup_count": len(rulegroups),
        "total_rule_count": len(all_rules),
        "examples_summary": {
            "total_examples": len(all_examples),
            "incorrect_examples": len(incorrect_examples),
            "correct_examples": len(correct_examples),
            "examples_with_corrections": len(examples_with_corrections),
        },
        "unifications": unifications,
        "filters_referenced": dict(sorted(filters_used.items())),
        "categories": categories,
    }


def analyze_disambiguation_xml(disambig_path: Path) -> Dict[str, Any]:
    """Analyze disambiguation.xml in detail."""
    if not disambig_path.is_file():
        return {"error": f"File not found: {disambig_path}"}

    tree = ET.parse(disambig_path)
    root = tree.getroot()

    xml_struct = analyze_xml_structure(root)

    rulegroups = root.findall(".//rulegroup")
    all_rules = root.findall(".//rule")
    all_examples = root.findall(".//example")

    actions: Dict[str, int] = {}
    for d in root.findall(".//disambig"):
        act = d.attrib.get("action", "unspecified")
        actions[act] = actions.get(act, 0) + 1

    filter_elements = root.findall(".//filter")
    filters_used: Dict[str, int] = {}
    for f in filter_elements:
        cls_name = f.attrib.get("class")
        if cls_name:
            filters_used[cls_name] = filters_used.get(cls_name, 0) + 1

    return {
        "file": disambig_path.name,
        "size_bytes": disambig_path.stat().st_size,
        "sha256": sha256_file(disambig_path),
        "xml_structure": xml_struct,
        "rulegroup_count": len(rulegroups),
        "total_rule_count": len(all_rules),
        "total_examples": len(all_examples),
        "disambig_actions": dict(sorted(actions.items())),
        "filters_referenced": dict(sorted(filters_used.items())),
    }


def analyze_russian_java(java_path: Path) -> Dict[str, Any]:
    """Parse Russian.java to extract enabled rules, pipeline components, and priority overrides."""
    if not java_path.is_file():
        return {"error": f"File not found: {java_path}"}

    content = java_path.read_text(encoding="utf-8")

    # Extract rules from getRelevantRules
    # Look for new RuleClass(...) in getRelevantRules block
    rel_rules_match = re.search(
        r"public List<Rule> getRelevantRules\([^)]*\)[^{]*\{(.*?)\n\s*\}",
        content,
        re.DOTALL,
    )
    enabled_rule_classes: List[str] = []
    if rel_rules_match:
        body = rel_rules_match.group(1)
        for line in body.splitlines():
            line = line.strip()
            if line.startswith("//") or line.startswith("/*"):
                continue  # ignore commented-out rules
            matches = re.findall(r"new\s+([A-Za-z0-9_]+)\s*\(", line)
            for m in matches:
                if m not in ("Example", "Rule"):
                    enabled_rule_classes.append(m)

    # Classify into Russian-specific vs Generic
    russian_specific_rules = [r for r in enabled_rule_classes if r.startswith("Russian") or r.startswith("Morfologik")]
    generic_rules = [r for r in enabled_rule_classes if r not in russian_specific_rules]

    # Extract language model rules
    lm_rules_match = re.search(
        r"public List<Rule> getRelevantLanguageModelRules\([^)]*\)[^{]*\{(.*?)\n\s*\}",
        content,
        re.DOTALL,
    )
    lm_rules: List[str] = []
    if lm_rules_match:
        lm_body = lm_rules_match.group(1)
        for line in lm_body.splitlines():
            line = line.strip()
            if line.startswith("//"):
                continue
            matches = re.findall(r"new\s+([A-Za-z0-9_]+)\s*\(", line)
            lm_rules.extend(matches)

    # Extract priority overrides
    prio_match = re.search(
        r"protected int getPriorityForId\(String id\)[^{]*\{(.*?)\n\s*\}",
        content,
        re.DOTALL,
    )
    priorities: Dict[str, int] = {}
    if prio_match:
        prio_body = prio_match.group(1)
        case_matches = re.findall(r'case\s+"([^"]+)"\s*:\s*return\s+(-?\d+)\s*;', prio_body)
        for rule_id, prio in case_matches:
            priorities[rule_id] = int(prio)

    # Pipeline components
    tagger_match = re.search(r"createDefaultTagger\(\)[^{]*\{\s*return\s+([^;]+);", content)
    disambig_match = re.search(r"createDefaultDisambiguator\(\)[^{]*\{\s*return\s+([^;]+);", content)
    chunker_match = re.search(r"createDefaultPostDisambiguationChunker\(\)[^{]*\{\s*return\s+([^;]+);", content)
    synth_match = re.search(r"createDefaultSynthesizer\(\)[^{]*\{\s*return\s+([^;]+);", content)
    s_tok_match = re.search(r"createDefaultSentenceTokenizer\(\)[^{]*\{\s*return\s+([^;]+);", content)
    w_tok_match = re.search(r"createDefaultWordTokenizer\(\)[^{]*\{\s*return\s+([^;]+);", content)
    ignored_chars_match = re.search(r"getIgnoredCharactersRegex\(\)[^{]*\{\s*return\s+Pattern\.compile\(\"([^\"]+)\"\);", content)

    return {
        "file": java_path.name,
        "size_bytes": java_path.stat().st_size,
        "sha256": sha256_file(java_path),
        "pipeline_components": {
            "tagger": tagger_match.group(1).strip() if tagger_match else "RussianTagger.INSTANCE",
            "disambiguator": disambig_match.group(1).strip() if disambig_match else "RussianHybridDisambiguator.getInstance()",
            "chunker": chunker_match.group(1).strip() if chunker_match else "RussianChunker",
            "synthesizer": synth_match.group(1).strip() if synth_match else "RussianSynthesizer.INSTANCE",
            "sentence_tokenizer": s_tok_match.group(1).strip() if s_tok_match else "SRXSentenceTokenizer",
            "word_tokenizer": w_tok_match.group(1).strip() if w_tok_match else "RussianWordTokenizer",
            "ignored_characters_regex": ignored_chars_match.group(1) if ignored_chars_match else "[\\u00AD\\u0301\\u0300]",
        },
        "enabled_rules_total": len(enabled_rule_classes),
        "russian_specific_rules": russian_specific_rules,
        "generic_rules_enabled": generic_rules,
        "language_model_rules": lm_rules,
        "priority_overrides": priorities,
    }


def resolve_filters(
    filters_used: Set[str],
    upstream_dir: Path,
) -> Dict[str, Any]:
    """Check if referenced XML filters have corresponding Java source files in the tree."""
    resolved: Dict[str, Any] = {}
    java_src_root = upstream_dir / "languagetool-language-modules" / "ru" / "src" / "main" / "java"

    for filter_cls in sorted(filters_used):
        # Convert package notation to relative path
        rel_java = filter_cls.replace(".", "/") + ".java"
        # Check within Russian module
        ru_subpath = Path("org/languagetool/rules/ru") / (filter_cls.split(".")[-1] + ".java")
        full_candidate = java_src_root / ru_subpath

        if full_candidate.is_file():
            resolved[filter_cls] = {
                "status": "RESOLVED_IN_TREE",
                "source_file": full_candidate.relative_to(upstream_dir).as_posix(),
                "sha256": sha256_file(full_candidate),
            }
        else:
            resolved[filter_cls] = {
                "status": "UNRESOLVED_UNKNOWN",
                "source_file": None,
                "notes": f"Filter class {filter_cls} could not be located in Russian Java source directory",
            }

    return resolved


def generate_inventory(upstream_dir: Path | None = None) -> Dict[str, Any]:
    """Generate complete Russian upstream inventory dictionary."""
    if upstream_dir is None:
        upstream_dir = get_default_upstream_dir()

    upstream_json_path = upstream_dir / "UPSTREAM.json"
    upstream_meta: Dict[str, Any] = {}
    if upstream_json_path.is_file():
        try:
            upstream_meta = json.loads(upstream_json_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    pinned_commit = upstream_meta.get("pinned_commit", "e807fcde6a6506191e1470744d2345da28c26be6")
    pinned_tag = upstream_meta.get("pinned_tag", "v6.8")

    # Resource files scan
    resources = scan_resource_files(upstream_dir)

    # grammar.xml
    grammar_path = (
        upstream_dir
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
    grammar_analysis = analyze_grammar_xml(grammar_path)

    # disambiguation.xml
    disambig_path = (
        upstream_dir
        / "languagetool-language-modules"
        / "ru"
        / "src"
        / "main"
        / "resources"
        / "org"
        / "languagetool"
        / "resource"
        / "ru"
        / "disambiguation.xml"
    )
    disambig_analysis = analyze_disambiguation_xml(disambig_path)

    # Russian.java
    java_path = (
        upstream_dir
        / "languagetool-language-modules"
        / "ru"
        / "src"
        / "main"
        / "java"
        / "org"
        / "languagetool"
        / "language"
        / "Russian.java"
    )
    java_analysis = analyze_russian_java(java_path)

    # Combine all filters
    all_filters = set()
    if isinstance(grammar_analysis.get("filters_referenced"), dict):
        all_filters.update(grammar_analysis["filters_referenced"].keys())
    if isinstance(disambig_analysis.get("filters_referenced"), dict):
        all_filters.update(disambig_analysis["filters_referenced"].keys())

    filters_resolution = resolve_filters(all_filters, upstream_dir)

    unresolved_filters = [
        cls for cls, info in filters_resolution.items() if info["status"] != "RESOLVED_IN_TREE"
    ]

    inventory: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "pinned_upstream": {
            "repository": "https://github.com/languagetool-org/languagetool.git",
            "tag": pinned_tag,
            "commit": pinned_commit,
            "commit_date": upstream_meta.get("commit_date", "2026-05-05T15:03:23Z"),
        },
        "summary": {
            "total_vendored_resources": len(resources),
            "grammar_rules_total": grammar_analysis.get("total_rule_count", 0),
            "grammar_rulegroups_total": grammar_analysis.get("rulegroup_count", 0),
            "grammar_categories_total": grammar_analysis.get("category_count", 0),
            "grammar_examples_total": grammar_analysis.get("examples_summary", {}).get("total_examples", 0),
            "disambiguation_rules_total": disambig_analysis.get("total_rule_count", 0),
            "disambiguation_rulegroups_total": disambig_analysis.get("rulegroup_count", 0),
            "enabled_java_rules_total": java_analysis.get("enabled_rules_total", 0),
            "russian_specific_java_rules_total": len(java_analysis.get("russian_specific_rules", [])),
            "generic_java_rules_total": len(java_analysis.get("generic_rules_enabled", [])),
            "xml_filters_total": len(all_filters),
            "unresolved_filters_count": len(unresolved_filters),
        },
        "grammar_xml": grammar_analysis,
        "disambiguation_xml": disambig_analysis,
        "russian_java": java_analysis,
        "filters_resolution": filters_resolution,
        "unresolved_filters": unresolved_filters,
        "resources_manifest": resources,
    }

    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate machine-readable Russian LanguageTool upstream inventory."
    )
    parser.add_argument(
        "--upstream-dir",
        type=Path,
        default=get_default_upstream_dir(),
        help="Path to third_party/languagetool",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=get_default_output_path(),
        help="Path to output JSON file (default: compat/inventory.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check existing inventory without modifying",
    )

    args = parser.parse_args()

    inventory = generate_inventory(args.upstream_dir)

    if args.check:
        if not args.output.is_file():
            print(f"Error: Inventory file {args.output} does not exist.", file=sys.stderr)
            return 1
        existing = json.loads(args.output.read_text(encoding="utf-8"))
        # Compare key metrics
        if inventory["summary"] != existing.get("summary"):
            print("Inventory mismatch detected!", file=sys.stderr)
            return 1
        print("Inventory is up to date.")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)

    print(f"Wrote inventory to {args.output}")
    print(f"Summary: {json.dumps(inventory['summary'], indent=2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
