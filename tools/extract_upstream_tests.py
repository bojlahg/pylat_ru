#!/usr/bin/env python3
"""tools/extract_upstream_tests.py

Extracts Russian upstream test fixtures from LanguageTool sources:
1. All executable examples from grammar.xml (with markers, offsets, corrections, and rule metadata)
2. Upstream JUnit test inventory categorized by component and porting strategy
3. Disambiguation examples from disambiguation.xml

Outputs to:
- compat/extracted_grammar_examples.json
- compat/upstream_test_inventory.json
- tests/fixtures/extracted_grammar_examples.json
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
from typing import Any, Dict, List, Optional, Tuple


def get_default_upstream_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "third_party" / "languagetool"


def get_default_compat_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "compat"


def get_default_fixtures_dir() -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "tests" / "fixtures"


def parse_example_element(
    example_elem: ET.Element,
    rule_id: str,
    rule_name: str,
    rulegroup_id: Optional[str],
    rulegroup_name: Optional[str],
    category_id: str,
    category_name: str,
    example_index: int,
) -> Dict[str, Any]:
    """Parse a single <example> XML element into a structured dictionary."""
    has_marker = example_elem.find("marker") is not None
    is_incorrect = (
        example_elem.attrib.get("type") == "incorrect"
        or has_marker
        or ("correction" in example_elem.attrib)
    )
    example_type = "incorrect" if is_incorrect else "correct"

    # Corrections from attribute
    corrections: List[str] = []
    if "correction" in example_elem.attrib:
        corr_attr = example_elem.attrib["correction"]
        if corr_attr:
            corrections.extend([c.strip() for c in corr_attr.split("|") if c.strip()])

    full_text_parts: List[str] = []
    marker_text: Optional[str] = None
    marker_start: Optional[int] = None
    marker_end: Optional[int] = None

    if example_elem.text:
        full_text_parts.append(example_elem.text)

    for child in example_elem:
        if child.tag == "marker":
            m_text = "".join(child.itertext())
            m_start = sum(len(p) for p in full_text_parts)
            full_text_parts.append(m_text)
            m_end = sum(len(p) for p in full_text_parts)
            marker_text = m_text
            marker_start = m_start
            marker_end = m_end
        elif child.tag == "correction":
            c_text = "".join(child.itertext()).strip()
            if c_text and c_text not in corrections:
                corrections.append(c_text)
        else:
            c_text = "".join(child.itertext())
            full_text_parts.append(c_text)

        if child.tail:
            full_text_parts.append(child.tail)

    clean_text = "".join(full_text_parts)

    return {
        "example_id": f"{rule_id}_ex{example_index + 1}",
        "rule_id": rule_id,
        "rule_name": rule_name,
        "rulegroup_id": rulegroup_id,
        "rulegroup_name": rulegroup_name,
        "category_id": category_id,
        "category_name": category_name,
        "example_index": example_index,
        "type": example_type,
        "text": clean_text,
        "has_marker": has_marker,
        "marker_text": marker_text,
        "marker_offset": marker_start,
        "marker_length": (marker_end - marker_start) if (marker_start is not None and marker_end is not None) else None,
        "corrections": corrections,
        "reason": example_elem.attrib.get("reason"),
    }


def extract_grammar_examples(grammar_path: Path) -> Dict[str, Any]:
    """Extract all examples from grammar.xml."""
    if not grammar_path.is_file():
        raise FileNotFoundError(f"grammar.xml not found at {grammar_path}")

    tree = ET.parse(grammar_path)
    root = tree.getroot()

    all_examples: List[Dict[str, Any]] = []

    for cat in root.findall("category"):
        cat_id = cat.attrib.get("id", "UNKNOWN_CATEGORY")
        cat_name = cat.attrib.get("name", "")

        # Top-level rules in category
        for rule in cat.findall("rule"):
            rule_id = rule.attrib.get("id", "UNKNOWN_RULE")
            rule_name = rule.attrib.get("name", "")
            for ex_idx, ex in enumerate(rule.findall("example")):
                all_examples.append(
                    parse_example_element(
                        ex,
                        rule_id=rule_id,
                        rule_name=rule_name,
                        rulegroup_id=None,
                        rulegroup_name=None,
                        category_id=cat_id,
                        category_name=cat_name,
                        example_index=ex_idx,
                    )
                )

        # Rulegroups in category
        for rg in cat.findall("rulegroup"):
            rg_id = rg.attrib.get("id", "UNKNOWN_RULEGROUP")
            rg_name = rg.attrib.get("name", "")
            for rule_idx, rule in enumerate(rg.findall("rule")):
                rule_id = rule.attrib.get("id", f"{rg_id}_{rule_idx + 1}")
                rule_name = rule.attrib.get("name", rg_name)
                for ex_idx, ex in enumerate(rule.findall("example")):
                    all_examples.append(
                        parse_example_element(
                            ex,
                            rule_id=rule_id,
                            rule_name=rule_name,
                            rulegroup_id=rg_id,
                            rulegroup_name=rg_name,
                            category_id=cat_id,
                            category_name=cat_name,
                            example_index=ex_idx,
                        )
                    )

            # Rulegroup-level examples (if any)
            for ex_idx, ex in enumerate(rg.findall("example")):
                all_examples.append(
                    parse_example_element(
                        ex,
                        rule_id=rg_id,
                        rule_name=rg_name,
                        rulegroup_id=rg_id,
                        rulegroup_name=rg_name,
                        category_id=cat_id,
                        category_name=cat_name,
                        example_index=ex_idx,
                    )
                )

    incorrect_examples = [e for e in all_examples if e["type"] == "incorrect"]
    correct_examples = [e for e in all_examples if e["type"] == "correct"]
    with_markers = [e for e in all_examples if e["has_marker"]]
    with_corrections = [e for e in all_examples if e["corrections"]]

    return {
        "schema_version": "1.0.0",
        "source_file": grammar_path.name,
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "summary": {
            "total_examples": len(all_examples),
            "incorrect_examples": len(incorrect_examples),
            "correct_examples": len(correct_examples),
            "examples_with_markers": len(with_markers),
            "examples_with_corrections": len(with_corrections),
        },
        "examples": all_examples,
    }


def inventory_junit_tests(upstream_dir: Path) -> Dict[str, Any]:
    """Inventory Russian JUnit test files in the upstream tree."""
    test_src_dir = (
        upstream_dir
        / "languagetool-language-modules"
        / "ru"
        / "src"
        / "test"
        / "java"
    )
    if not test_src_dir.exists():
        return {"error": f"Test source dir not found: {test_src_dir}"}

    test_files: List[Dict[str, Any]] = []

    for path in sorted(test_src_dir.rglob("*Test.java")):
        rel_path = path.relative_to(upstream_dir).as_posix()
        content = path.read_text(encoding="utf-8")

        # Find test methods
        test_methods = re.findall(r"public\s+void\s+([A-Za-z0-9_]+)\s*\(\s*\)", content)
        has_test_annot = bool(re.search(r"@Test\b", content))

        # Categorize component and strategy
        name = path.name
        strategy = "semantic_port"
        target_component = "rules"

        if "PatternRuleTest" in name:
            strategy = "fixture_driven"
            target_component = "rule_engine_xml"
        elif "SRXSentenceTokenizerTest" in name:
            strategy = "mechanical"
            target_component = "sentence_tokenizer"
        elif "DateCheckFilterTest" in name:
            strategy = "mechanical"
            target_component = "xml_filters"
        elif "SynthesizerTest" in name:
            strategy = "semantic_port"
            target_component = "synthesizer"
        elif "TaggerTest" in name:
            strategy = "semantic_port"
            target_component = "tagger"
        elif "SpellcheckerTest" in name or "SpellerRuleTest" in name:
            strategy = "semantic_port"
            target_component = "spelling"
        elif "ConcurrencyTest" in name:
            strategy = "semantic_port"
            target_component = "concurrency"
        elif name == "RussianTest.java":
            strategy = "mechanical"
            target_component = "module_metadata"

        test_files.append({
            "file_name": name,
            "rel_path": rel_path,
            "size_bytes": path.stat().st_size,
            "has_test_annotation": has_test_annot,
            "test_methods": test_methods,
            "test_method_count": len(test_methods),
            "target_component": target_component,
            "porting_strategy": strategy,
        })

    return {
        "schema_version": "1.0.0",
        "total_test_files": len(test_files),
        "total_test_methods": sum(tf["test_method_count"] for tf in test_files),
        "test_files": test_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract LanguageTool Russian tests and grammar examples."
    )
    parser.add_argument(
        "--upstream-dir",
        type=Path,
        default=get_default_upstream_dir(),
        help="Path to third_party/languagetool",
    )
    parser.add_argument(
        "--compat-dir",
        type=Path,
        default=get_default_compat_dir(),
        help="Path to compat directory",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=Path,
        default=get_default_fixtures_dir(),
        help="Path to tests/fixtures directory",
    )

    args = parser.parse_args()

    grammar_path = (
        args.upstream_dir
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

    # 1. Extract grammar examples
    extracted_examples = extract_grammar_examples(grammar_path)

    # 2. Inventory JUnit tests
    junit_inventory = inventory_junit_tests(args.upstream_dir)

    # Save to compat/
    args.compat_dir.mkdir(parents=True, exist_ok=True)
    compat_examples_file = args.compat_dir / "extracted_grammar_examples.json"
    with open(compat_examples_file, "w", encoding="utf-8") as f:
        json.dump(extracted_examples, f, indent=2, ensure_ascii=False)

    compat_junit_file = args.compat_dir / "upstream_test_inventory.json"
    with open(compat_junit_file, "w", encoding="utf-8") as f:
        json.dump(junit_inventory, f, indent=2, ensure_ascii=False)

    # Also save fixture copy to tests/fixtures/
    args.fixtures_dir.mkdir(parents=True, exist_ok=True)
    fixture_examples_file = args.fixtures_dir / "extracted_grammar_examples.json"
    with open(fixture_examples_file, "w", encoding="utf-8") as f:
        json.dump(extracted_examples, f, indent=2, ensure_ascii=False)

    print(f"Extracted {extracted_examples['summary']['total_examples']} grammar examples.")
    print(f"Saved examples to {compat_examples_file} and {fixture_examples_file}")
    print(f"Inventoried {junit_inventory['total_test_files']} JUnit test files.")
    print(f"Saved JUnit inventory to {compat_junit_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
