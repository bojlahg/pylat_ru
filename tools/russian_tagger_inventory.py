"""tools/russian_tagger_inventory.py

Deterministic generator for compat/russian_tagger_inventory.json.
Extracts metadata, hashes, line counts, distinct fullforms, readings count,
normalization tables, MayMissingYO conditions, and case fallback rules
from pinned upstream LanguageTool Russian tagger resources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from pylat_ru.tagging.russian import ACUTE_VOWELS, NORMALIZATION_REPLACEMENTS
from pylat_ru.tagging.word_tagger import ManualTagger

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
INVENTORY_OUTPUT_PATH = REPO_ROOT / "compat" / "russian_tagger_inventory.json"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def analyze_manual_file(path: Path) -> Dict[str, Any]:
    """Parse and calculate exact statistics for a manual dictionary file."""
    tagger = ManualTagger(path)
    data = path.read_text(encoding="utf-8")
    data_lines_count = 0
    for line in data.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        clean = s.split("#", 1)[0].strip()
        if clean:
            data_lines_count += 1

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "parsed_data_lines_count": data_lines_count,
        "distinct_fullforms_count": tagger.entry_count,
        "total_readings_count": tagger.total_readings_count,
    }


def generate_russian_tagger_inventory() -> Dict[str, Any]:
    """Generate deterministic compatibility inventory for RussianTagger."""
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
    ru_src = (
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
        / "tagging"
        / "ru"
        / "RussianTagger.java"
    )

    dict_path = ru_res_dir / "russian.dict"
    info_path = ru_res_dir / "russian.info"
    added_path = ru_res_dir / "added.txt"
    added_custom_path = ru_res_dir / "added_custom.txt"
    removed_path = ru_res_dir / "removed.txt"
    removed_custom_path = ru_res_dir / "removed_custom.txt"

    replacements_list = []
    for src, dst in NORMALIZATION_REPLACEMENTS:
        src_cps = [f"U+{ord(c):04X}" for c in src]
        dst_cps = [f"U+{ord(c):04X}" for c in dst]
        replacements_list.append(
            {
                "source": src,
                "target": dst,
                "source_codepoints": src_cps,
                "target_codepoints": dst_cps,
            }
        )

    acute_vowels_list = []
    for av in ACUTE_VOWELS:
        cps = [f"U+{ord(c):04X}" for c in av]
        acute_vowels_list.append(
            {
                "sequence": av,
                "codepoints": cps,
            }
        )

    inventory = {
        "schema_version": "1.0.0",
        "pinned_version": upstream["pinned_tag"],
        "pinned_commit": upstream["pinned_commit"],
        "morfologik_version": "2.1.9",
        "russian_tagger_source": {
            "path": str(ru_src.relative_to(REPO_ROOT)).replace("\\", "/"),
            "size": ru_src.stat().st_size,
            "sha256": sha256_file(ru_src),
        },
        "resources": {
            "russian_dict": {
                "path": str(dict_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "size": dict_path.stat().st_size,
                "sha256": sha256_file(dict_path),
            },
            "russian_info": {
                "path": str(info_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "size": info_path.stat().st_size,
                "sha256": sha256_file(info_path),
            },
            "added_txt": analyze_manual_file(added_path),
            "added_custom_txt": analyze_manual_file(added_custom_path),
            "removed_txt": analyze_manual_file(removed_path),
            "removed_custom_txt": analyze_manual_file(removed_custom_path),
        },
        "manual_parser_semantics": {
            "encoding": "utf-8",
            "default_separator": "\t",
            "supports_separator_regexp": True,
            "rejects_nbsp": True,
            "strips_inline_comments": True,
            "trims_pos_tags": True,
            "field_count": 3,
            "fields": ["fullform", "baseform", "postag"],
        },
        "manual_merge_order": "manual_additions_first_then_morfologik_then_removals",
        "case_fallback_policy": [
            "exact_normalized_word_lookup",
            "append_lowercase_lookup_if_not_lowercase_and_not_mixed_case",
            "append_uppercase_first_char_lookup_if_lowercase_and_all_prior_empty",
            "fallback_to_single_null_reading_if_still_empty",
        ],
        "normalization_replacements": replacements_list,
        "may_missing_yo_conditions": {
            "min_token_length": 2,
            "forbidden_characters": ["ё", "Ё"],
            "required_characters_any": ["е", "Е"],
            "forbidden_acute_vowels": acute_vowels_list,
            "lookup_transformation": "lowercase_all_e_to_yo",
            "emitted_chunk_tag": "MayMissingYO",
        },
        "unknown_token_behavior": {
            "token": "normalized_word",
            "lemma": None,
            "pos_tag": None,
        },
        "runtime_resource_strategy": "packaged_under_pylat_ru_resources_ru",
        "unsupported_or_known_differences": [],
    }

    return inventory


def main() -> int:
    inventory = generate_russian_tagger_inventory()
    content = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    INVENTORY_OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Generated Russian tagger compatibility inventory -> {INVENTORY_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    main()
