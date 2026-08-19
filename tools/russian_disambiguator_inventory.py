"""tools/russian_disambiguator_inventory.py

Deterministic generator for compat/russian_disambiguator_inventory.json.
Extracts metadata, hashes, rule counts, action distributions, filter specifications,
multiword statistics, and test examples directly from pinned upstream LanguageTool
Russian disambiguation resources.
"""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List

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
    tags = set()
    length_distribution: Dict[str, int] = {}

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
            phrase, tag = parts
            tags.add(tag)
            n_words = len(phrase.split(" "))
            key = f"{n_words}_words"
            length_distribution[key] = length_distribution.get(key, 0) + 1

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "total_lines_count": len(lines),
        "data_lines_count": len(data_lines),
        "unique_tags_count": len(tags),
        "unique_tags": sorted(list(tags)),
        "phrase_length_distribution": dict(sorted(length_distribution.items())),
    }


def analyze_disambiguation_xml(path: Path) -> Dict[str, Any]:
    """Parse and calculate exact statistics for disambiguation.xml."""
    tree = ET.parse(str(path))
    root = tree.getroot()

    all_rules = root.findall(".//rule")
    rulegroups = root.findall("rulegroup")
    top_rules = [c for c in root if c.tag == "rule"]

    actions_count: Dict[str, int] = {}
    filters_list: List[Dict[str, str]] = []
    rule_ids: List[str] = []
    examples: List[Dict[str, Any]] = []

    for rule in all_rules:
        rid = rule.attrib.get("id") or rule.attrib.get("name") or "UNKNOWN"
        rule_ids.append(rid)

        disambig = rule.find("disambig")
        if disambig is not None:
            act = disambig.attrib.get("action", "filter_or_replace")
            actions_count[act] = actions_count.get(act, 0) + 1

        filt = rule.find("filter")
        if filt is not None:
            filters_list.append({
                "rule_id": rid,
                "class": filt.attrib.get("class", ""),
                "args": filt.attrib.get("args", ""),
            })

        for ex in rule.findall("example"):
            examples.append({
                "rule_id": rid,
                "type": ex.attrib.get("type", "ambiguous"),
                "inputform": ex.attrib.get("inputform"),
                "outputform": ex.attrib.get("outputform"),
                "text": "".join(ex.itertext()).strip(),
            })

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "total_rules_count": len(all_rules),
        "top_level_rules_count": len(top_rules),
        "rulegroups_count": len(rulegroups),
        "actions_distribution": dict(sorted(actions_count.items())),
        "filters_count": len(filters_list),
        "filters": filters_list,
        "examples_count": len(examples),
        "examples": examples,
        "rule_ids": rule_ids,
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

    return {
        "schema_version": "1.0.0",
        "pinned_upstream": {
            "commit": upstream["pinned_commit"],
            "tag": upstream["pinned_tag"],
            "commit_date": upstream["commit_date"],
        },
        "multiwords": multiwords_analysis,
        "disambiguation_xml": disambig_analysis,
        "packaged_runtime_resources": packaged_resources,
        "pipeline_status": {
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
    print(f"  Multiwords data lines: {inventory['multiwords']['data_lines_count']}")
    print(f"  Disambiguation XML rules: {inventory['disambiguation_xml']['total_rules_count']}")
    print(f"  Disambiguation XML filters: {inventory['disambiguation_xml']['filters_count']}")
    print(f"  Disambiguation XML examples: {inventory['disambiguation_xml']['examples_count']}")
    return 0


if __name__ == "__main__":
    main()
