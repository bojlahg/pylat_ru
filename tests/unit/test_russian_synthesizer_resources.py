"""Unit tests for RussianSynthesizer package resources, hash verification, and real installed wheel distribution."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

from pylat_ru.synthesis import RussianSynthesizer
from tools.russian_synthesizer_inventory import generate_russian_synthesizer_inventory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
UPSTREAM_JSON_PATH = REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json"
PACKAGE_RES_DIR = REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru"
INVENTORY_PATH = REPO_ROOT / "compat" / "russian_synthesizer_inventory.json"


def test_packaged_synthesis_resources_hash_parity():
    """Verify all packaged runtime synthesis resources in src/pylat_ru/resources/ru match UPSTREAM.json hashes."""
    assert PACKAGE_RES_DIR.is_dir(), f"Missing package resource directory: {PACKAGE_RES_DIR}"
    upstream_data = json.loads(UPSTREAM_JSON_PATH.read_text(encoding="utf-8"))["files"]

    files_to_check = [
        "russian_synth.dict",
        "russian_synth.info",
        "tags_russian.txt",
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


def test_russian_synthesizer_inventory_byte_exact_regeneration():
    """Verify compat/russian_synthesizer_inventory.json matches deterministic regeneration byte-for-byte."""
    assert INVENTORY_PATH.is_file(), f"Missing {INVENTORY_PATH}"
    committed_content = INVENTORY_PATH.read_text(encoding="utf-8")

    fresh_inventory = generate_russian_synthesizer_inventory()
    fresh_content = json.dumps(fresh_inventory, indent=2, ensure_ascii=False) + "\n"

    assert fresh_content == committed_content, "Generated russian_synthesizer_inventory.json does not match committed file byte-for-byte!"


def test_missing_synth_dictionary_raises_error(tmp_path: Path):
    """Verify missing synthesis dictionary raises explicit FileNotFoundError."""
    fake_dict = tmp_path / "missing_synth.dict"
    fake_tags = tmp_path / "missing_tags.txt"

    with pytest.raises(FileNotFoundError):
        RussianSynthesizer(resource_path=fake_dict, tag_file_path=fake_tags)


def test_real_installed_distribution_package_synthesis(tmp_path: Path):
    """Verify building a real wheel distribution, verify all Russian synthesis resources in wheel, and test isolated install."""
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

    # 2. Inspect wheel zip contents and explicitly verify Russian synthesis assets are packaged
    with zipfile.ZipFile(whl_path) as zf:
        wheel_entries = set(zf.namelist())

    required_packaged_resources = [
        "pylat_ru/resources/ru/russian_synth.dict",
        "pylat_ru/resources/ru/russian_synth.info",
        "pylat_ru/resources/ru/tags_russian.txt",
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

    # 4. Execute real synthesis lookups in a subprocess isolated from repo src/ and third_party/
    smoke_script = tmp_path / "smoke_test_synth.py"
    smoke_script.write_text(
        f"""
import sys
from pathlib import Path

# Strip any globally registered editable repo paths from sys.path
sys.path = [p for p in sys.path if not p.replace('\\\\', '/').lower().endswith('/src') and 'third_party' not in p.replace('\\\\', '/').lower()]

import pylat_ru
from pylat_ru import RussianSynthesizer

# Confirm that pylat_ru is imported strictly from the isolated site-packages
assert str(Path({repr(str(isolated_site))})).lower() in pylat_ru.__file__.lower(), (
    f"pylat_ru imported from wrong path: {{pylat_ru.__file__}}"
)

synth = RussianSynthesizer()
res_nom = synth.synthesize('семья', 'NN:Inanim:Fem:Sin:Nom')
assert res_nom == ['семья']

res_r = synth.synthesize('семья', 'NN:Inanim:Fem:Sin:R')
assert res_r == ['семьи']

res_madam = synth.synthesize('мадам', 'NN:Name:Fem:PL')
assert res_madam == ['мадам']

res_roman = synth.synthesize('123', '_spell_number_:Roman')
assert res_roman == ['CXXIII']

print('REAL_INSTALLED_SYNTHESIS_DISTRIBUTION_SUCCESS')
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
    assert "REAL_INSTALLED_SYNTHESIS_DISTRIBUTION_SUCCESS" in proc.stdout
