"""tools/russian_synthesizer_inventory.py

Deterministic generator for compat/russian_synthesizer_inventory.json.
Extracts comprehensive metadata, hashes, Java source properties, FSA header info,
tags_russian.txt statistics, manual overlays analysis, custom exclusions,
and representative synthesis examples directly from pinned upstream LanguageTool resources.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Set

from pylat_ru.morfologik.dictionary import MorfologikDictionary
from pylat_ru.morfologik.fsa import read_fsa
from pylat_ru.morfologik.metadata import DictionaryMetadata
from pylat_ru.synthesis.manual import ManualSynthesizer

REPO_ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
INVENTORY_OUTPUT_PATH = REPO_ROOT / "compat" / "russian_synthesizer_inventory.json"
RES_DIR = REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru"
JAVA_SRC_DIR = (
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
    / "synthesis"
    / "ru"
)
JAVA_TEST_DIR = (
    REPO_ROOT
    / "third_party"
    / "languagetool"
    / "languagetool-language-modules"
    / "ru"
    / "src"
    / "test"
    / "java"
    / "org"
    / "languagetool"
    / "synthesis"
    / "ru"
)


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def analyze_java_sources() -> Dict[str, Any]:
    """Analyze Java synthesizer source and test files."""
    synth_java = JAVA_SRC_DIR / "RussianSynthesizer.java"
    test_java = JAVA_TEST_DIR / "RussianSynthesizerTest.java"

    test_content = test_java.read_text(encoding="utf-8") if test_java.is_file() else ""
    test_methods = re.findall(r"public\s+(?:final\s+)?void\s+(test\w+)\s*\(", test_content)

    return {
        "russian_synthesizer_java": {
            "path": str(synth_java.relative_to(REPO_ROOT)).replace("\\", "/"),
            "size": synth_java.stat().st_size if synth_java.is_file() else 0,
            "sha256": sha256_file(synth_java) if synth_java.is_file() else "MISSING",
        },
        "russian_synthesizer_test_java": {
            "path": str(test_java.relative_to(REPO_ROOT)).replace("\\", "/"),
            "size": test_java.stat().st_size if test_java.is_file() else 0,
            "sha256": sha256_file(test_java) if test_java.is_file() else "MISSING",
            "junit_test_methods": test_methods,
        },
    }


def analyze_synth_fsa_and_info() -> Dict[str, Any]:
    """Analyze binary synthesis dictionary and metadata."""
    dict_p = RES_DIR / "russian_synth.dict"
    info_p = RES_DIR / "russian_synth.info"

    fsa = read_fsa(dict_p)
    meta = DictionaryMetadata.from_text(info_p.read_text(encoding="utf-8"))

    return {
        "dictionary_file": {
            "path": "src/pylat_ru/resources/ru/russian_synth.dict",
            "size": dict_p.stat().st_size,
            "sha256": sha256_file(dict_p),
            "format": "CFSA2",
            "flags": f"0x{fsa.flags:04x}",
            "supported_flags": ["FLEXIBLE", "STOPBIT", "NEXTBIT"],
            "label_mapping_size": len(fsa.label_mapping),
            "total_arcs_bytes": len(fsa.arcs),
        },
        "info_file": {
            "path": "src/pylat_ru/resources/ru/russian_synth.info",
            "size": info_p.stat().st_size,
            "sha256": sha256_file(info_p),
            "parsed_attributes": dict(sorted(meta.raw_attributes.items())),
        },
    }


def analyze_tags_file() -> Dict[str, Any]:
    """Analyze tags_russian.txt tag sequence and statistics."""
    tags_p = RES_DIR / "tags_russian.txt"
    lines = [
        line.strip()
        for line in tags_p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    unique_tags = set(lines)
    trailing_empty = [t for t in lines if t.endswith(":")]

    return {
        "path": "src/pylat_ru/resources/ru/tags_russian.txt",
        "size": tags_p.stat().st_size,
        "sha256": sha256_file(tags_p),
        "total_tags_count": len(lines),
        "unique_tags_count": len(unique_tags),
        "duplicate_tags_count": len(lines) - len(unique_tags),
        "first_5_tags": lines[:5],
        "last_5_tags": lines[-5:],
        "trailing_empty_colon_tags_count": len(trailing_empty),
        "trailing_empty_colon_tags_sample": trailing_empty[:5],
    }


def analyze_manual_synth_file(path: Path) -> Dict[str, Any]:
    """Parse and calculate exact statistics for a manual synthesizer dictionary file."""
    manual = ManualSynthesizer(path)
    data = path.read_text(encoding="utf-8")
    data_lines_count = 0
    sep_directive = None
    key_form_counts: Dict[tuple[str, str], int] = defaultdict(int)

    for line in data.splitlines():
        s = line.strip(" \t\r\n")
        if not s or s.startswith("#"):
            if s.startswith("#separatorRegExp="):
                sep_directive = s[len("#separatorRegExp=") :]
            continue
        clean = s.split("#", 1)[0].strip(" \t\r\n")
        if clean:
            data_lines_count += 1
            parts = clean.split("\t") if sep_directive is None else re.split(sep_directive, clean)
            if len(parts) == 3:
                key_form_counts[(parts[1], parts[2])] += 1

    dup_keys = {k: v for k, v in key_form_counts.items() if v > 1}

    return {
        "path": str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "size": path.stat().st_size,
        "sha256": sha256_file(path),
        "parsed_data_lines_count": data_lines_count,
        "distinct_keys_count": len(manual),
        "total_forms_count": sum(len(forms) for forms in manual._mapping.values()),
        "duplicate_forms_per_key_count": len(dup_keys),
        "possible_tags_count": len(manual.get_possible_tags()),
        "separator_directive": sep_directive,
    }


def analyze_material_removals() -> Dict[str, Any]:
    """Analyze which entries in removed.txt materially remove forms from russian_synth.dict."""
    dict_p = RES_DIR / "russian_synth.dict"
    info_p = RES_DIR / "russian_synth.info"
    synth_dict = MorfologikDictionary.open(dict_p, info_p)

    rem_path = RES_DIR / "removed.txt"
    lines = rem_path.read_text(encoding="utf-8").splitlines()
    material_cases: List[Dict[str, Any]] = []

    for line in lines:
        s = line.strip(" \t\r\n")
        if not s or s.startswith("#"):
            continue
        clean = s.split("#", 1)[0].strip(" \t\r\n")
        parts = clean.split("\t")
        if len(parts) == 3:
            form, lemma, tag = parts
            dict_res = synth_dict.synthesize(lemma, tag)
            if form in dict_res:
                material_cases.append(
                    {
                        "form": form,
                        "lemma": lemma,
                        "pos_tag": tag,
                        "original_dict_forms": list(dict_res),
                    }
                )

    return {
        "total_material_removals_count": len(material_cases),
        "material_removals_sample": material_cases[:5],
    }


def generate_russian_synthesizer_inventory() -> Dict[str, Any]:
    """Generate complete deterministic Russian synthesizer inventory."""
    java_info = analyze_java_sources()
    fsa_info = analyze_synth_fsa_and_info()
    tags_info = analyze_tags_file()
    added_info = analyze_manual_synth_file(RES_DIR / "added.txt")
    removed_info = analyze_manual_synth_file(RES_DIR / "removed.txt")
    material_removals = analyze_material_removals()

    tags_p = RES_DIR / "tags_russian.txt"
    tags_lines = [
        line.strip()
        for line in tags_p.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    base_tags_set = set(tags_lines)
    manual_added = ManualSynthesizer(RES_DIR / "added.txt")
    manual_only_tags = [t for t in manual_added.get_possible_tags() if t not in base_tags_set]

    added_custom_p = RES_DIR / "added_custom.txt"
    removed_custom_p = RES_DIR / "removed_custom.txt"
    do_not_synth_p = RES_DIR / "do-not-synthesize.txt"

    return {
        "schema_version": "1.0.0",
        "pinned_upstream": {
            "repository": "https://github.com/languagetool-org/languagetool.git",
            "tag": "v6.8",
            "commit": "e807fcde6a6506191e1470744d2345da28c26be6",
            "commit_date": "2026-05-05T15:03:23Z",
            "morfologik_version": "2.1.9",
        },
        "java_sources": java_info,
        "synthesis_dictionary": fsa_info,
        "possible_tags_file": tags_info,
        "manual_overlays": {
            "added_txt": {
                **added_info,
                "manual_only_tags_count": len(manual_only_tags),
                "manual_only_tags": manual_only_tags,
            },
            "removed_txt": {
                **removed_info,
                "material_removals": material_removals,
            },
            "do_not_synthesize_txt": {
                "path": "src/pylat_ru/resources/ru/do-not-synthesize.txt",
                "exists": do_not_synth_p.is_file(),
            },
        },
        "custom_overlay_exclusion": {
            "added_custom.txt": {
                "exists": added_custom_p.is_file(),
                "size": added_custom_p.stat().st_size if added_custom_p.is_file() else 0,
                "sha256": sha256_file(added_custom_p) if added_custom_p.is_file() else "MISSING",
                "status": "EXCLUDED",
                "rationale": "RussianSynthesizer in LT 6.8 only loads /ru/added.txt and /ru/removed.txt, not custom overlays",
            },
            "removed_custom.txt": {
                "exists": removed_custom_p.is_file(),
                "size": removed_custom_p.stat().st_size if removed_custom_p.is_file() else 0,
                "sha256": sha256_file(removed_custom_p) if removed_custom_p.is_file() else "MISSING",
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
        "representative_synthesis_corpus": [
            {"category": "noun_exact", "token": "семья", "lemma": "семья", "pos_tag": "NN:Inanim:Fem:Sin:Nom", "expected": ["семья"]},
            {"category": "verb_exact", "token": "бежать", "lemma": "бежать", "pos_tag": "VB:INF:INTR:IMPFV", "expected": ["бежать"]},
            {"category": "adj_exact", "token": "красивый", "lemma": "красивый", "pos_tag": "ADJ:Posit:Fem:Nom", "expected": ["красивая"]},
            {"category": "trailing_empty_tag", "token": "блукать", "lemma": "блукать", "pos_tag": "VB:INF:", "expected": ["блукать"]},
            {"category": "manual_added", "token": "мадам", "lemma": "мадам", "pos_tag": "NN:Name:Fem:PL", "expected": ["мадам"]},
            {"category": "manual_removed", "token": "дерево", "lemma": "дерево", "pos_tag": "NN:Inanim:Neut:PL:R", "expected": ["деревьев"]},
            {"category": "regex_noun", "token": "семья", "lemma": "семья", "pos_tag": "NN:Inanim:Fem:.*", "expected_count": 13},
            {"category": "special_roman", "token": "123", "lemma": "123", "pos_tag": "_spell_number_:Roman", "expected": ["CXXIII"]},
        ],
    }


def main() -> None:
    inventory = generate_russian_synthesizer_inventory()
    content = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    INVENTORY_OUTPUT_PATH.write_text(content, encoding="utf-8")
    print(f"Generated {INVENTORY_OUTPUT_PATH} ({len(content.encode('utf-8'))} bytes)")


if __name__ == "__main__":
    main()
