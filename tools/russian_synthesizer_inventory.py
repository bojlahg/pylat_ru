"""tools/russian_synthesizer_inventory.py

Deterministic generator for compat/russian_synthesizer_inventory.json.
Extracts metadata, hashes, line counts, distinct lemma/tag pairs, forms count,
and possible tags ordering directly from pinned upstream LanguageTool Russian synthesizer resources.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from pylat_ru.synthesis.manual import ManualSynthesizer

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
INVENTORY_OUTPUT_PATH = REPO_ROOT / "compat" / "russian_synthesizer_inventory.json"
RES_DIR = REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru"


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def analyze_manual_synth_file(path: Path) -> Dict[str, Any]:
    """Parse and calculate exact statistics for a manual synthesizer dictionary file."""
    manual = ManualSynthesizer(path)
    data = path.read_text(encoding="utf-8")
    data_lines_count = 0
    for line in data.splitlines():
        s = line.strip(" \t\r\n")
        if not s or s.startswith("#"):
            continue
        clean = s.split("#", 1)[0].strip(" \t\r\n")
        if clean:
            data_lines_count += 1

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "parsed_data_lines_count": data_lines_count,
        "distinct_keys_count": len(manual),
        "total_forms_count": sum(len(forms) for forms in manual._mapping.values()),
        "possible_tags_count": len(manual.get_possible_tags()),
    }


def generate_russian_synthesizer_inventory() -> Dict[str, Any]:
    """Generate complete deterministic Russian synthesizer inventory."""
    tags_file = RES_DIR / "tags_russian.txt"
    tags_lines = [
        line.strip()
        for line in tags_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    added_info = analyze_manual_synth_file(RES_DIR / "added.txt")
    removed_info = analyze_manual_synth_file(RES_DIR / "removed.txt")

    manual_added = ManualSynthesizer(RES_DIR / "added.txt")
    base_tags_set = set(tags_lines)
    manual_only_tags = [t for t in manual_added.get_possible_tags() if t not in base_tags_set]

    return {
        "schema_version": "1.0.0",
        "pinned_upstream": {
            "repository": "https://github.com/languagetool-org/languagetool.git",
            "tag": "v6.8",
            "commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "commit_date": "2026-05-05T15:03:23Z",
            "morfologik_version": "2.1.9",
        },
        "resources": {
            "russian_synth_dict": {
                "path": "src/pylat_ru/resources/ru/russian_synth.dict",
                "size": (RES_DIR / "russian_synth.dict").stat().st_size,
                "sha256": sha256_file(RES_DIR / "russian_synth.dict"),
            },
            "russian_synth_info": {
                "path": "src/pylat_ru/resources/ru/russian_synth.info",
                "size": (RES_DIR / "russian_synth.info").stat().st_size,
                "sha256": sha256_file(RES_DIR / "russian_synth.info"),
            },
            "tags_russian_txt": {
                "path": "src/pylat_ru/resources/ru/tags_russian.txt",
                "size": tags_file.stat().st_size,
                "sha256": sha256_file(tags_file),
                "total_tags_count": len(tags_lines),
            },
            "added_txt": added_info,
            "removed_txt": removed_info,
        },
        "custom_overlay_exclusion": {
            "added_custom.txt": {
                "status": "EXCLUDED",
                "rationale": "RussianSynthesizer in LT 6.8 only loads /ru/added.txt and /ru/removed.txt, not custom overlays",
            },
            "removed_custom.txt": {
                "status": "EXCLUDED",
                "rationale": "RussianSynthesizer in LT 6.8 only loads /ru/added.txt and /ru/removed.txt, not custom overlays",
            },
        },
        "special_tags": {
            "_spell_number_": {
                "description": "Spelled number without gender prefix",
                "handler": "get_spelled_number",
                "supports_russian_sor": False,
            },
            "_spell_number_:feminine": {
                "description": "Spelled number with feminine gender prefix",
                "handler": "get_spelled_number_feminine",
                "supports_russian_sor": False,
            },
            "_spell_number_:Roman": {
                "description": "Integer to Roman numeral conversion",
                "handler": "int_to_roman",
                "supports_russian_sor": True,
            },
        },
        "possible_tags_summary": {
            "base_tags_count": len(tags_lines),
            "manual_only_tags_count": len(manual_only_tags),
            "manual_only_tags": manual_only_tags,
            "total_possible_tags_count": len(tags_lines) + len(manual_only_tags),
        },
    }


def main() -> None:
    inventory = generate_russian_synthesizer_inventory()
    content = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    INVENTORY_OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Generated {INVENTORY_OUTPUT_PATH} ({len(content.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
