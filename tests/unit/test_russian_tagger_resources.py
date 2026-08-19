"""Unit tests for RussianTagger package resources, hash verification, and inventory regeneration."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

from pylat_ru.tagging.errors import TaggerResourceError
from pylat_ru.tagging.russian import RussianTagger
from tools.russian_tagger_inventory import generate_russian_tagger_inventory


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
PACKAGE_RES_DIR = REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru"
INVENTORY_PATH = REPO_ROOT / "compat" / "russian_tagger_inventory.json"


def test_packaged_runtime_resources_hash_parity():
    """Verify all packaged runtime resources in src/pylat_ru/resources/ru match UPSTREAM.json hashes."""
    assert PACKAGE_RES_DIR.is_dir(), f"Missing package resource directory: {PACKAGE_RES_DIR}"
    upstream_data = json.loads(UPSTREAM_JSON_PATH.read_text(encoding="utf-8"))["files"]

    files_to_check = [
        "russian.dict",
        "russian.info",
        "added.txt",
        "added_custom.txt",
        "removed.txt",
        "removed_custom.txt",
    ]

    for fname in files_to_check:
        pkg_file = PACKAGE_RES_DIR / fname
        assert pkg_file.is_file(), f"Missing packaged resource: {pkg_file}"

        pkg_sha = hashlib.sha256(pkg_file.read_bytes()).hexdigest()
        rel_key = f"languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/{fname}"
        expected_sha = upstream_data[rel_key]["sha256"]
        expected_size = upstream_data[rel_key]["size"]

        assert pkg_sha == expected_sha, f"SHA-256 mismatch for packaged {fname}: {pkg_sha} != {expected_sha}"
        assert pkg_file.stat().st_size == expected_size, f"Size mismatch for packaged {fname}"


def test_russian_tagger_inventory_byte_exact_regeneration():
    """Verify compat/russian_tagger_inventory.json matches deterministic regeneration byte-for-byte."""
    assert INVENTORY_PATH.is_file(), f"Missing {INVENTORY_PATH}"
    committed_content = INVENTORY_PATH.read_text(encoding="utf-8")

    fresh_inventory = generate_russian_tagger_inventory()
    fresh_content = json.dumps(fresh_inventory, indent=2, ensure_ascii=False) + "\n"

    assert fresh_content == committed_content, "Generated russian_tagger_inventory.json does not match committed file byte-for-byte!"


def test_missing_dictionary_raises_resource_error(tmp_path: Path):
    """Verify missing dictionary or info file raises explicit TaggerResourceError."""
    fake_dict = tmp_path / "missing.dict"
    fake_info = tmp_path / "missing.info"

    with pytest.raises(TaggerResourceError):
        RussianTagger(dict_path=fake_dict, info_path=fake_info)


def test_isolated_package_tagging_without_third_party(tmp_path: Path):
    """Verify RussianTagger can instantiate and tag text in an isolated subprocess with no third_party access."""
    # Run a subprocess with PYTHONPATH pointing only to src
    code = """
import sys
from pylat_ru import RussianTagger
tagger = RussianTagger()
atrs = tagger.tag(['Все', 'смешалось', 'в', 'доме', 'Облонских'])
assert len(atrs) == 5
assert atrs[0].token == 'Все'
assert atrs[0].has_lemma('все')
assert 'MayMissingYO' in atrs[0].chunk_tags
assert atrs[4].token == 'Облонских'
assert atrs[4].is_pos_tag_unknown is True
print('ISOLATED_TAGGER_SUCCESS')
"""
    src_dir = str(REPO_ROOT / "src")
    env = os.environ.copy()
    env["PYTHONPATH"] = src_dir

    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "ISOLATED_TAGGER_SUCCESS" in proc.stdout
