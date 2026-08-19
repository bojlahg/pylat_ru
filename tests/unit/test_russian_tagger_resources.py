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


def test_real_installed_distribution_package_tagging(tmp_path: Path):
    """Verify building a real wheel distribution, verify all 6 Russian resources in wheel, and test isolated install."""
    import zipfile

    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    isolated_site = tmp_path / "site-packages"
    isolated_site.mkdir()

    # 1. Build a wheel distribution from repo root
    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(REPO_ROOT)],
        check=True,
        capture_output=True,
    )

    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"Expected 1 built wheel, found {len(wheels)}"
    whl_path = wheels[0]

    # 2. Inspect wheel zip contents and explicitly verify all 6 Russian runtime assets are packaged
    with zipfile.ZipFile(whl_path) as zf:
        wheel_entries = set(zf.namelist())

    required_packaged_resources = [
        "pylat_ru/resources/ru/russian.dict",
        "pylat_ru/resources/ru/russian.info",
        "pylat_ru/resources/ru/added.txt",
        "pylat_ru/resources/ru/added_custom.txt",
        "pylat_ru/resources/ru/removed.txt",
        "pylat_ru/resources/ru/removed_custom.txt",
    ]

    for req_res in required_packaged_resources:
        assert req_res in wheel_entries, (
            f"Required resource '{req_res}' is missing from built wheel distribution {whl_path.name}!"
        )

    # 3. Install wheel into isolated target directory
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(isolated_site),
            str(whl_path),
        ],
        check=True,
        capture_output=True,
    )

    # 4. Execute real morphology lookups in a subprocess isolated from repo src/ and third_party/
    smoke_script = tmp_path / "smoke_test.py"
    smoke_script.write_text(
        f"""
import sys
from pathlib import Path

# Strip any globally registered editable repo paths from sys.path
sys.path = [p for p in sys.path if not p.replace('\\\\', '/').lower().endswith('/src') and 'third_party' not in p.replace('\\\\', '/').lower()]

import pylat_ru
from pylat_ru import RussianTagger

# Confirm that pylat_ru is imported strictly from the isolated site-packages
assert str(Path({repr(str(isolated_site))})).lower() in pylat_ru.__file__.lower(), (
    f"pylat_ru imported from wrong path: {{pylat_ru.__file__}}"
)

tagger = RussianTagger()
atrs = tagger.tag(['Все', 'смешалось', 'в', 'доме', 'Облонских', 'блукать', 'Абдуллаевы'])
assert len(atrs) == 7

# Verify normal word and MayMissingYO
assert atrs[0].token == 'Все'
assert atrs[0].has_lemma('все')
assert 'MayMissingYO' in atrs[0].chunk_tags

# Verify unknown word
assert atrs[4].token == 'Облонских'
assert atrs[4].is_pos_tag_unknown is True

# Verify dictionary word with trailing colon
assert atrs[5].token == 'блукать'
assert atrs[5].has_pos_tag('VB:INF:')

# Verify manual overlay addition
assert atrs[6].token == 'Абдуллаевы'
assert atrs[6].has_lemma('абдуллаев')

print('REAL_INSTALLED_DISTRIBUTION_SUCCESS')
""",
        encoding="utf-8",
    )

    env = {
        "PYTHONPATH": str(isolated_site),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "PATH": os.environ.get("PATH", ""),
    }

    proc = subprocess.run(
        [sys.executable, str(smoke_script)],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "REAL_INSTALLED_DISTRIBUTION_SUCCESS" in proc.stdout
