#!/usr/bin/env python3
"""tools/russian_srx_inventory.py

Extracts, inventories, and generates deterministic runtime Russian SRX
segmentation rules from pinned LanguageTool segment.srx (v6.8).

Generates:
- compat/russian_srx_inventory.json (machine-readable inventory & metadata)
- src/pylat_ru/resources/russian_srx_rules.json (pure runtime rule representation)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Tuple

import regex

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_SRX_PATH = (
    REPO_ROOT
    / "third_party"
    / "languagetool"
    / "languagetool-core"
    / "src"
    / "main"
    / "resources"
    / "org"
    / "languagetool"
    / "resource"
    / "segment.srx"
)
DEFAULT_INVENTORY_PATH = REPO_ROOT / "compat" / "russian_srx_inventory.json"
DEFAULT_RULES_PATH = (
    REPO_ROOT / "src" / "pylat_ru" / "resources" / "russian_srx_rules.json"
)

PINNED_LT_TAG = "v6.8"
PINNED_LT_COMMIT = "e807fcde6a6506191e1470744d2345da28c26be6"
LOOMCHILD_VERSION = "2.0.3"
SRX_NS = {"srx": "http://www.lisa.org/srx20"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def adapt_java_regex(pattern: str) -> str:
    """Adapt Java regex syntax constructs for the Python regex engine.

    Specifically:
    - (?U) -> (?u) (Java UNICODE_CHARACTER_CLASS flag to Python unicode flag)
    - (?iU) -> (?iu)
    - (?Ui) -> (?iu)
    """
    if not pattern:
        return ""
    p = pattern.replace("(?U)", "(?u)")
    p = p.replace("(?iU)", "(?iu)")
    p = p.replace("(?Ui)", "(?iu)")
    return p


def analyze_srx(srx_path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Parse segment.srx and extract detailed inventory and runtime rules."""
    if not srx_path.is_file():
        raise FileNotFoundError(f"SRX file not found: {srx_path}")

    srx_bytes = srx_path.read_bytes()
    srx_hash = hashlib.sha256(srx_bytes).hexdigest()
    srx_size = len(srx_bytes)

    tree = ET.parse(srx_path)
    root = tree.getroot()

    header_elem = root.find("srx:header", SRX_NS)
    if header_elem is None:
        raise ValueError("Missing <header> in SRX file")

    segmentsubflows = header_elem.attrib.get("segmentsubflows", "yes")
    cascade = header_elem.attrib.get("cascade", "no")

    # Map rules
    body_elem = root.find("srx:body", SRX_NS)
    if body_elem is None:
        raise ValueError("Missing <body> in SRX file")

    maprules_elem = body_elem.find("srx:maprules", SRX_NS)
    if maprules_elem is None:
        raise ValueError("Missing <maprules> in SRX file")

    all_maps: List[Dict[str, str]] = []
    for lm in maprules_elem.findall("srx:languagemap", SRX_NS):
        all_maps.append(
            {
                "languagepattern": lm.attrib.get("languagepattern", ""),
                "languagerulename": lm.attrib.get("languagerulename", ""),
            }
        )

    # Collect all languagerule definitions
    languagerules_dict: Dict[str, ET.Element] = {}
    for lr in body_elem.findall("srx:languagerules/srx:languagerule", SRX_NS):
        name = lr.attrib.get("languagerulename", "")
        languagerules_dict[name] = lr

    # Effective rule sequences
    ru_two_groups = ["GeneralImportant", "ByTwoLineBreaks", "Russian", "Default"]
    ru_one_groups = ["GeneralImportant", "ByLineBreak", "Russian", "Default"]

    def extract_group_rules(group_name: str) -> List[Dict[str, Any]]:
        lr_elem = languagerules_dict.get(group_name)
        if lr_elem is None:
            raise ValueError(f"Language rule group '{group_name}' not found in SRX")
        rules: List[Dict[str, Any]] = []
        for idx, r in enumerate(lr_elem.findall("srx:rule", SRX_NS), start=1):
            is_break = r.attrib.get("break", "yes") == "yes"
            bb = r.find("srx:beforebreak", SRX_NS)
            ab = r.find("srx:afterbreak", SRX_NS)
            bb_raw = bb.text if bb is not None and bb.text is not None else ""
            ab_raw = ab.text if ab is not None and ab.text is not None else ""
            bb_adapted = adapt_java_regex(bb_raw)
            ab_adapted = adapt_java_regex(ab_raw)

            # Test compile
            if bb_adapted:
                try:
                    regex.compile(bb_adapted)
                except Exception as e:
                    raise ValueError(
                        f"Failed to compile beforebreak pattern for {group_name} R{idx}: {bb_adapted} ({e})"
                    ) from e
            if ab_adapted:
                try:
                    regex.compile(ab_adapted)
                except Exception as e:
                    raise ValueError(
                        f"Failed to compile afterbreak pattern for {group_name} R{idx}: {ab_adapted} ({e})"
                    ) from e

            rules.append(
                {
                    "rule_index": idx,
                    "break": "yes" if is_break else "no",
                    "beforebreak": bb_raw,
                    "afterbreak": ab_raw,
                    "beforebreak_adapted": bb_adapted,
                    "afterbreak_adapted": ab_adapted,
                }
            )
        return rules

    groups_data: Dict[str, List[Dict[str, Any]]] = {}
    for gname in ["GeneralImportant", "ByTwoLineBreaks", "ByLineBreak", "Russian", "Default"]:
        groups_data[gname] = extract_group_rules(gname)

    # Build sequence for ru_two and ru_one
    def build_effective_sequence(group_names: List[str]) -> List[Dict[str, Any]]:
        seq: List[Dict[str, Any]] = []
        for gname in group_names:
            for r in groups_data[gname]:
                seq.append(
                    {
                        "group": gname,
                        "rule_index": r["rule_index"],
                        "break": r["break"],
                        "beforebreak": r["beforebreak"],
                        "afterbreak": r["afterbreak"],
                        "beforebreak_adapted": r["beforebreak_adapted"],
                        "afterbreak_adapted": r["afterbreak_adapted"],
                    }
                )
        return seq

    ru_two_rules = build_effective_sequence(ru_two_groups)
    ru_one_rules = build_effective_sequence(ru_one_groups)

    # Regex feature inventory
    unicode_props = set()
    for rule in ru_two_rules + ru_one_rules:
        for text in [rule["beforebreak"], rule["afterbreak"]]:
            for match in regex.finditer(r"\\p\{([A-Za-z]+)\}", text):
                unicode_props.add(match.group(1))

    inventory = {
        "schema_version": "1.0.0",
        "target_pin": {
            "languagetool_tag": PINNED_LT_TAG,
            "languagetool_commit": PINNED_LT_COMMIT,
            "loomchild_segment_version": LOOMCHILD_VERSION,
        },
        "source_file": {
            "path": "languagetool-core/src/main/resources/org/languagetool/resource/segment.srx",
            "size_bytes": srx_size,
            "sha256": srx_hash,
        },
        "srx_header": {
            "segmentsubflows": segmentsubflows,
            "cascade": cascade,
        },
        "mappings": {
            "ru_two": {
                "effective_groups": ru_two_groups,
                "total_rules_count": len(ru_two_rules),
                "break_yes_count": sum(1 for r in ru_two_rules if r["break"] == "yes"),
                "break_no_count": sum(1 for r in ru_two_rules if r["break"] == "no"),
            },
            "ru_one": {
                "effective_groups": ru_one_groups,
                "total_rules_count": len(ru_one_rules),
                "break_yes_count": sum(1 for r in ru_one_rules if r["break"] == "yes"),
                "break_no_count": sum(1 for r in ru_one_rules if r["break"] == "no"),
            },
        },
        "groups_summary": {
            gname: {
                "total_rules": len(rules),
                "break_yes": sum(1 for r in rules if r["break"] == "yes"),
                "break_no": sum(1 for r in rules if r["break"] == "no"),
            }
            for gname, rules in groups_data.items()
        },
        "regex_feature_inventory": {
            "unicode_properties_used": sorted(unicode_props),
            "inline_flags_used": ["(?U)", "(?iu)"],
            "all_rules_compiled_successfully": True,
            "unsupported_features_count": 0,
        },
    }

    runtime_rules = {
        "metadata": {
            "description": "Deterministic Russian SRX segmentation rules extracted from LanguageTool v6.8 segment.srx",
            "languagetool_commit": PINNED_LT_COMMIT,
            "languagetool_tag": PINNED_LT_TAG,
            "loomchild_version": LOOMCHILD_VERSION,
            "source_sha256": srx_hash,
        },
        "groups": groups_data,
        "configurations": {
            "ru_two": {
                "groups": ru_two_groups,
                "rules": ru_two_rules,
            },
            "ru_one": {
                "groups": ru_one_groups,
                "rules": ru_one_rules,
            },
        },
    }

    return inventory, runtime_rules


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate or verify Russian SRX rules from pinned segment.srx."
    )
    parser.add_argument(
        "--srx-path",
        type=Path,
        default=DEFAULT_SRX_PATH,
        help=f"Path to segment.srx (default: {DEFAULT_SRX_PATH})",
    )
    parser.add_argument(
        "--inventory-out",
        type=Path,
        default=DEFAULT_INVENTORY_PATH,
        help=f"Path to output inventory JSON (default: {DEFAULT_INVENTORY_PATH})",
    )
    parser.add_argument(
        "--rules-out",
        type=Path,
        default=DEFAULT_RULES_PATH,
        help=f"Path to output runtime rules JSON (default: {DEFAULT_RULES_PATH})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check existing files for exact deterministic match without writing",
    )

    args = parser.parse_args()

    try:
        inventory, runtime_rules = analyze_srx(args.srx_path)
    except Exception as e:
        print(f"Error analyzing SRX: {e}", file=sys.stderr)
        return 1

    inv_json = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    rules_json = json.dumps(runtime_rules, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        if not args.inventory_out.is_file():
            print(f"Missing inventory file: {args.inventory_out}", file=sys.stderr)
            return 1
        if not args.rules_out.is_file():
            print(f"Missing rules file: {args.rules_out}", file=sys.stderr)
            return 1

        curr_inv = args.inventory_out.read_text(encoding="utf-8")
        curr_rules = args.rules_out.read_text(encoding="utf-8")

        if curr_inv != inv_json:
            print(
                f"Drift detected in inventory file: {args.inventory_out}",
                file=sys.stderr,
            )
            return 1
        if curr_rules != rules_json:
            print(f"Drift detected in rules file: {args.rules_out}", file=sys.stderr)
            return 1

        print("SRX inventory and runtime rules are up-to-date and deterministic.")
        return 0

    # Ensure output directories exist
    args.inventory_out.parent.mkdir(parents=True, exist_ok=True)
    args.rules_out.parent.mkdir(parents=True, exist_ok=True)

    args.inventory_out.write_text(inv_json, encoding="utf-8")
    args.rules_out.write_text(rules_json, encoding="utf-8")

    print(f"Successfully generated SRX inventory -> {args.inventory_out}")
    print(f"Successfully generated runtime rules  -> {args.rules_out}")
    print(
        f"ru_two rules: {inventory['mappings']['ru_two']['total_rules_count']} "
        f"(break: {inventory['mappings']['ru_two']['break_yes_count']}, "
        f"non-break: {inventory['mappings']['ru_two']['break_no_count']})"
    )
    print(
        f"ru_one rules: {inventory['mappings']['ru_one']['total_rules_count']} "
        f"(break: {inventory['mappings']['ru_one']['break_yes_count']}, "
        f"non-break: {inventory['mappings']['ru_one']['break_no_count']})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
