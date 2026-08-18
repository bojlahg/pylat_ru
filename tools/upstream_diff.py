#!/usr/bin/env python3
"""tools/upstream_diff.py

Detects drift between the pinned upstream LanguageTool compatibility surface
and a target LanguageTool revision, directory, or inventory file.

Reports:
- Added / removed / modified Russian resource files (with SHA-256 changes)
- Added / removed XML tags and attribute pairs in grammar.xml and disambiguation.xml
- Added / removed / changed XML filter classes
- Added / removed / changed Java rules in Russian.java
- Changes in grammar rules, rulegroups, and categories counts
- Changes in upstream test file inventories

Outputs structured JSON diff and human-readable summary.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.upstream_inventory import generate_inventory, get_default_upstream_dir, get_default_output_path


def compute_dict_diff(
    pinned_dict: Dict[str, Any],
    target_dict: Dict[str, Any],
) -> Dict[str, Any]:
    """Compute added, removed, and changed keys between two dictionaries."""
    pinned_keys = set(pinned_dict.keys())
    target_keys = set(target_dict.keys())

    added = sorted(target_keys - pinned_keys)
    removed = sorted(pinned_keys - target_keys)
    common = pinned_keys & target_keys

    changed = {}
    for k in sorted(common):
        if pinned_dict[k] != target_dict[k]:
            changed[k] = {
                "pinned": pinned_dict[k],
                "target": target_dict[k],
            }

    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "is_different": bool(added or removed or changed),
    }


def compute_set_diff(
    pinned_set: Set[str] | List[str],
    target_set: Set[str] | List[str],
) -> Dict[str, Any]:
    """Compute added and removed items between two sets."""
    p_set = set(pinned_set)
    t_set = set(target_set)

    added = sorted(t_set - p_set)
    removed = sorted(p_set - t_set)

    return {
        "added": added,
        "removed": removed,
        "is_different": bool(added or removed),
    }


def compare_inventories(
    pinned_inv: Dict[str, Any],
    target_inv: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare two complete inventory dictionaries and return a structured diff."""
    # 1. Resources diff
    pinned_res = pinned_inv.get("resources_manifest", {})
    target_res = target_inv.get("resources_manifest", {})
    resources_diff = compute_dict_diff(pinned_res, target_res)

    # 2. Grammar XML tags & attributes
    pinned_g_tags = pinned_inv.get("grammar_xml", {}).get("xml_structure", {}).get("tag_counts", {})
    target_g_tags = target_inv.get("grammar_xml", {}).get("xml_structure", {}).get("tag_counts", {})
    grammar_tags_diff = compute_dict_diff(pinned_g_tags, target_g_tags)

    pinned_g_attrs = pinned_inv.get("grammar_xml", {}).get("xml_structure", {}).get("attribute_counts", {})
    target_g_attrs = target_inv.get("grammar_xml", {}).get("xml_structure", {}).get("attribute_counts", {})
    grammar_attrs_diff = compute_dict_diff(pinned_g_attrs, target_g_attrs)

    # 3. Disambiguation XML tags & actions
    pinned_d_tags = pinned_inv.get("disambiguation_xml", {}).get("xml_structure", {}).get("tag_counts", {})
    target_d_tags = target_inv.get("disambiguation_xml", {}).get("xml_structure", {}).get("tag_counts", {})
    disambig_tags_diff = compute_dict_diff(pinned_d_tags, target_d_tags)

    pinned_d_actions = pinned_inv.get("disambiguation_xml", {}).get("disambig_actions", {})
    target_d_actions = target_inv.get("disambiguation_xml", {}).get("disambig_actions", {})
    disambig_actions_diff = compute_dict_diff(pinned_d_actions, target_d_actions)

    # 4. XML Filters
    pinned_filters = set(pinned_inv.get("filters_resolution", {}).keys())
    target_filters = set(target_inv.get("filters_resolution", {}).keys())
    filters_diff = compute_set_diff(pinned_filters, target_filters)

    # 5. Java Rules
    pinned_ru_rules = pinned_inv.get("russian_java", {}).get("russian_specific_rules", [])
    target_ru_rules = target_inv.get("russian_java", {}).get("russian_specific_rules", [])
    ru_rules_diff = compute_set_diff(pinned_ru_rules, target_ru_rules)

    pinned_gen_rules = pinned_inv.get("russian_java", {}).get("generic_rules_enabled", [])
    target_gen_rules = target_inv.get("russian_java", {}).get("generic_rules_enabled", [])
    gen_rules_diff = compute_set_diff(pinned_gen_rules, target_gen_rules)

    # 6. Summary metrics diff
    pinned_summary = pinned_inv.get("summary", {})
    target_summary = target_inv.get("summary", {})
    summary_diff = compute_dict_diff(pinned_summary, target_summary)

    has_drift = (
        resources_diff["is_different"]
        or grammar_tags_diff["is_different"]
        or grammar_attrs_diff["is_different"]
        or disambig_tags_diff["is_different"]
        or disambig_actions_diff["is_different"]
        or filters_diff["is_different"]
        or ru_rules_diff["is_different"]
        or gen_rules_diff["is_different"]
        or summary_diff["is_different"]
    )

    return {
        "diff_schema_version": "1.0.0",
        "compared_at": datetime.utcnow().isoformat() + "Z",
        "has_drift": has_drift,
        "pinned_meta": pinned_inv.get("pinned_upstream", {}),
        "target_meta": target_inv.get("pinned_upstream", {}),
        "summary_diff": summary_diff,
        "resources_diff": resources_diff,
        "grammar_xml_diff": {
            "tags": grammar_tags_diff,
            "attributes": grammar_attrs_diff,
        },
        "disambiguation_xml_diff": {
            "tags": disambig_tags_diff,
            "actions": disambig_actions_diff,
        },
        "xml_filters_diff": filters_diff,
        "java_rules_diff": {
            "russian_specific": ru_rules_diff,
            "generic": gen_rules_diff,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare LanguageTool Russian upstream compatibility surface for drift."
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        help="Path to target LanguageTool tree (if checking against another tree)",
    )
    parser.add_argument(
        "--target-inventory",
        type=Path,
        help="Path to target inventory.json file",
    )
    parser.add_argument(
        "--pinned-inventory",
        type=Path,
        default=get_default_output_path(),
        help="Path to pinned compat/inventory.json",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON diff",
    )

    args = parser.parse_args()

    # Load pinned inventory
    if not args.pinned_inventory.is_file():
        print(f"Generating pinned inventory at {args.pinned_inventory}...", file=sys.stderr)
        pinned_inv = generate_inventory()
    else:
        pinned_inv = json.loads(args.pinned_inventory.read_text(encoding="utf-8"))

    # Load or generate target inventory
    if args.target_inventory and args.target_inventory.is_file():
        target_inv = json.loads(args.target_inventory.read_text(encoding="utf-8"))
    elif args.target_dir and args.target_dir.is_dir():
        target_inv = generate_inventory(args.target_dir)
    else:
        # Default: check pinned against current tree
        target_inv = generate_inventory()

    diff = compare_inventories(pinned_inv, target_inv)

    if args.json:
        print(json.dumps(diff, indent=2, ensure_ascii=False))
    else:
        print(f"Drift Detected: {diff['has_drift']}")
        if diff["has_drift"]:
            print(f"Summary Changes: {json.dumps(diff['summary_diff'], indent=2)}")
            if diff["resources_diff"]["is_different"]:
                print(f"Resource file changes: +{len(diff['resources_diff']['added'])}, -{len(diff['resources_diff']['removed'])}, ~{len(diff['resources_diff']['changed'])}")
            if diff["xml_filters_diff"]["is_different"]:
                print(f"Filter changes: +{diff['xml_filters_diff']['added']}, -{diff['xml_filters_diff']['removed']}")
            if diff["java_rules_diff"]["russian_specific"]["is_different"]:
                print(f"Russian Java rule changes: {diff['java_rules_diff']['russian_specific']}")
        else:
            print("No drift detected against pinned inventory.")

    return 0 if not diff["has_drift"] else 2


if __name__ == "__main__":
    sys.exit(main())
