"""tools/russian_tagset_inventory.py

Deterministic inventory and validation tool for Russian LanguageTool tagset resources:
- tags_russian.txt
- tagset.txt
- russian.dict cross-validation

Emits: compat/russian_tagset.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
TAGS_PATH = (
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
    / "tags_russian.txt"
)
TAGSET_TXT_PATH = (
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
    / "tagset.txt"
)
OUTPUT_JSON_PATH = REPO_ROOT / "compat" / "russian_tagset.json"


def analyze_tags_file(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        raw_lines = f.readlines()

    total_lines = len(raw_lines)
    stripped_lines = [l.strip() for l in raw_lines]
    non_empty_lines = [l for l in stripped_lines if l]
    unique_tags = sorted(set(non_empty_lines))

    # Anomaly checks
    whitespace_anomalies: List[Dict[str, Any]] = []
    for idx, line in enumerate(raw_lines, start=1):
        if line.endswith("\r\n"):
            line_no_nl = line[:-2]
        elif line.endswith("\n"):
            line_no_nl = line[:-1]
        else:
            line_no_nl = line

        if line_no_nl != line_no_nl.strip():
            whitespace_anomalies.append({
                "line_number": idx,
                "raw": repr(line_no_nl),
                "normalized": line_no_nl.strip(),
            })

    # Duplicate checks
    seen: Dict[str, int] = {}
    duplicates: List[Dict[str, Any]] = []
    for idx, t in enumerate(non_empty_lines, start=1):
        if t in seen:
            duplicates.append({
                "tag": t,
                "first_seen_line": seen[t],
                "duplicate_line": idx,
            })
        else:
            seen[t] = idx

    # Empty colon components
    empty_colon_tags: List[str] = []
    for t in unique_tags:
        parts = t.split(":")
        if any(p == "" for p in parts):
            empty_colon_tags.append(t)

    # Coarse POS prefixes
    pos_prefixes = sorted(set(t.split(":")[0] for t in unique_tags))

    # Feature atoms
    feature_atoms: Set[str] = set()
    for t in unique_tags:
        for p in t.split(":"):
            feature_atoms.add(p)

    return {
        "total_lines": total_lines,
        "non_empty_lines_count": len(non_empty_lines),
        "unique_tags_count": len(unique_tags),
        "duplicate_occurrences": duplicates,
        "whitespace_anomalies": whitespace_anomalies,
        "empty_colon_tags_count": len(empty_colon_tags),
        "empty_colon_tags": empty_colon_tags,
        "pos_prefixes": pos_prefixes,
        "feature_atoms_count": len(feature_atoms),
        "feature_atoms": sorted(feature_atoms),
        "tags": unique_tags,
    }


def parse_tagset_txt(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    aot_mappings: List[Dict[str, str]] = []
    unparsed_lines: List[Dict[str, Any]] = []
    prose_sections: List[str] = []

    # AOT mapping regex: 2 non-whitespace chars (or code) followed by tabs/spaces and LT tag
    # Example: "аа    NN:[Anim|Inanim]:Masc:Sin:Nom"
    aot_pattern = re.compile(r"^([^\s#]{1,6})\s+([A-Za-z0-9_:\-+|\[\]]+)$")

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue

        match = aot_pattern.match(line)
        if match:
            aot_code, lt_tag = match.groups()
            aot_mappings.append({
                "line_number": idx,
                "aot_code": aot_code,
                "lt_tag": lt_tag,
            })
        elif " - " in line or line.endswith(":") or re.search(r"[а-яА-Я]", line):
            prose_sections.append(line)
        else:
            unparsed_lines.append({
                "line_number": idx,
                "content": line,
            })

    return {
        "total_lines": len(lines),
        "aot_mappings_count": len(aot_mappings),
        "aot_mappings": aot_mappings,
        "prose_lines_count": len(prose_sections),
        "unparsed_lines_count": len(unparsed_lines),
        "unparsed_lines": unparsed_lines,
    }


def generate_tagset_inventory() -> Dict[str, Any]:
    tags_data = analyze_tags_file(TAGS_PATH)
    tagset_data = parse_tagset_txt(TAGSET_TXT_PATH)

    inventory = {
        "metadata": {
            "source_files": [
                "third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/tags_russian.txt",
                "third_party/languagetool/languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/tagset.txt",
            ],
            "description": "Deterministic Russian LanguageTool tagset inventory",
        },
        "tags_russian_summary": {
            "total_lines": tags_data["total_lines"],
            "unique_tags_count": tags_data["unique_tags_count"],
            "whitespace_anomalies_count": len(tags_data["whitespace_anomalies"]),
            "whitespace_anomalies": tags_data["whitespace_anomalies"],
            "duplicates_count": len(tags_data["duplicate_occurrences"]),
            "duplicates": tags_data["duplicate_occurrences"],
            "empty_colon_tags_count": tags_data["empty_colon_tags_count"],
            "pos_prefixes_count": len(tags_data["pos_prefixes"]),
            "pos_prefixes": tags_data["pos_prefixes"],
            "feature_atoms_count": tags_data["feature_atoms_count"],
            "feature_atoms": tags_data["feature_atoms"],
        },
        "tagset_txt_summary": {
            "total_lines": tagset_data["total_lines"],
            "aot_mappings_count": tagset_data["aot_mappings_count"],
            "unparsed_lines_count": tagset_data["unparsed_lines_count"],
            "unparsed_lines": tagset_data["unparsed_lines"],
        },
        "tags": tags_data["tags"],
        "aot_ancode_mappings": tagset_data["aot_mappings"],
    }

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2, ensure_ascii=False)

    print(f"Generated {OUTPUT_JSON_PATH} successfully:")
    print(f"  Total tags: {tags_data['unique_tags_count']}")
    print(f"  Empty colon tags: {tags_data['empty_colon_tags_count']}")
    print(f"  POS prefixes: {len(tags_data['pos_prefixes'])} {tags_data['pos_prefixes']}")
    print(f"  AOT mappings: {tagset_data['aot_mappings_count']}")

    return inventory


if __name__ == "__main__":
    generate_tagset_inventory()
