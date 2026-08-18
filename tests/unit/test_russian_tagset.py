"""tests/unit/test_russian_tagset.py

Unit tests for RussianTag model, tagset loading, and compat/russian_tagset.json inventory.
"""

import json
from pathlib import Path
import pytest

from pylat_ru.tagset import RussianTag, load_tags_file, parse_tag
from tools.russian_tagset_inventory import generate_tagset_inventory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RU_RESOURCE_DIR = (
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
TAGSET_JSON_PATH = REPO_ROOT / "compat" / "russian_tagset.json"


def test_lossless_tag_parsing():
    """Verify raw tag string and all parts (including empty colon slots) are preserved."""
    tag1 = parse_tag("NN:Inanim:Masc:Sin:Nom")
    assert tag1.raw == "NN:Inanim:Masc:Sin:Nom"
    assert tag1.parts == ("NN", "Inanim", "Masc", "Sin", "Nom")
    assert tag1.pos == "NN"
    assert tag1.animacy == "Inanim"
    assert tag1.gender == "Masc"
    assert tag1.number == "Sin"
    assert tag1.case == "Nom"
    assert str(tag1) == "NN:Inanim:Masc:Sin:Nom"

    # Trailing empty slot
    tag_trailing = parse_tag("VB:INF:")
    assert tag_trailing.raw == "VB:INF:"
    assert tag_trailing.parts == ("VB", "INF", "")
    assert tag_trailing.pos == "VB"
    assert tag_trailing.tense == "INF"

    # Middle empty slot
    tag_middle = parse_tag("NN::Masc:PL:D")
    assert tag_middle.raw == "NN::Masc:PL:D"
    assert tag_middle.parts == ("NN", "", "Masc", "PL", "D")
    assert tag_middle.gender == "Masc"
    assert tag_middle.number == "PL"
    assert tag_middle.case == "D"
    assert tag_middle.animacy is None


def test_structured_views():
    """Verify non-destructive view properties for verbs, adjectives, and participles."""
    tag_vb = parse_tag("VB:Past:INTR:PFV:Neut")
    assert tag_vb.pos == "VB"
    assert tag_vb.tense == "Past"
    assert tag_vb.transitivity == "INTR"
    assert tag_vb.aspect == "PFV"
    assert tag_vb.gender == "Neut"

    tag_adj = parse_tag("ADJ:Posit:Fem:Nom")
    assert tag_adj.pos == "ADJ"
    assert tag_adj.gender == "Fem"
    assert tag_adj.case == "Nom"
    assert tag_adj.is_short is False
    assert tag_adj.is_comparative is False
    assert tag_adj.is_superlative is False

    tag_short = parse_tag("ADJ:Short:PL")
    assert tag_short.is_short is True

    tag_pt_short = parse_tag("PT_Short:Past::STR:Masc")
    assert tag_pt_short.is_short is True
    assert tag_pt_short.voice == "STR"


def test_tagset_file_loading():
    """Verify loading pinned tags_russian.txt."""
    tags_file = RU_RESOURCE_DIR / "tags_russian.txt"
    tags = load_tags_file(tags_file)
    assert len(tags) == 1201
    unique_raw = set(t.raw for t in tags)
    assert len(unique_raw) == 1200  # 1 duplicate in raw file


def test_tagset_inventory_json_exact_regeneration():
    """Verify compat/russian_tagset.json matches dynamic complete regeneration structurally and deterministically."""
    assert TAGSET_JSON_PATH.is_file(), f"Missing {TAGSET_JSON_PATH}"
    with open(TAGSET_JSON_PATH, "r", encoding="utf-8") as f:
        committed = json.load(f)

    generated = generate_tagset_inventory(write_to_disk=False)
    assert generated == committed, "Regenerated tagset inventory differs from committed compat/russian_tagset.json"


def test_dictionary_tagset_cross_validation():
    """Verify 100% tag coverage parity between binary russian.dict and tags_russian.txt."""
    with open(TAGSET_JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cross_val = data.get("dictionary_cross_validation", {})
    assert cross_val.get("is_full_tag_coverage") is True
    assert cross_val.get("missing_in_dict_count") == 0
    assert cross_val.get("missing_in_dict") == []
    assert cross_val.get("dict_distinct_normalized_tags_count") == 1200
    assert cross_val.get("dict_distinct_raw_tags_count") == 1201
    assert "NN:Inanim:Masc:PL:P  " in cross_val.get("extra_in_dict_raw", [])
