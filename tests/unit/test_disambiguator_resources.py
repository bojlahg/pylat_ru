"""Unit tests for Russian disambiguator packaged resources and wheel distribution."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

from tools.russian_disambiguator_inventory import (
    generate_russian_disambiguator_inventory,
    sha256_file,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_packaged_runtime_resources_hash_parity() -> None:
    """Verify packaged runtime resources in src/ match pinned upstream hashes."""
    upstream_json = json.loads(
        (REPO_ROOT / "third_party" / "languagetool" / "UPSTREAM.json").read_text(encoding="utf-8")
    )
    upstream_files = upstream_json["files"]

    pkg_res_dir = REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru"

    multiwords_path = pkg_res_dir / "multiwords.txt"
    disambig_path = pkg_res_dir / "disambiguation.xml"

    assert multiwords_path.is_file()
    assert disambig_path.is_file()

    expected_multiwords_hash = upstream_files[
        "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/multiwords.txt"
    ]["sha256"]
    expected_disambig_hash = upstream_files[
        "languagetool-language-modules/ru/src/main/resources/org/languagetool/resource/ru/disambiguation.xml"
    ]["sha256"]

    assert sha256_file(multiwords_path) == expected_multiwords_hash
    assert sha256_file(disambig_path) == expected_disambig_hash


def test_russian_disambiguator_inventory_byte_exact_regeneration() -> None:
    """Verify that regenerating compat/russian_disambiguator_inventory.json produces identical JSON."""
    inventory_path = REPO_ROOT / "compat" / "russian_disambiguator_inventory.json"
    assert inventory_path.is_file()

    existing_content = inventory_path.read_text(encoding="utf-8")
    regenerated = generate_russian_disambiguator_inventory()
    regenerated_json = json.dumps(regenerated, indent=2, ensure_ascii=False) + "\n"

    assert existing_content == regenerated_json


def test_real_installed_distribution_package_disambiguation() -> None:
    """Build a real wheel, install into isolated environment, and verify disambiguation execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()

        # Build wheel
        build_proc = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )
        assert build_proc.returncode == 0, f"pip wheel failed: {build_proc.stderr}"

        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1
        whl_path = wheels[0]

        # Verify all 8 Russian assets exist in wheel archive
        with zipfile.ZipFile(whl_path, "r") as z:
            names = z.namelist()
            assert any(n.endswith("pylat_ru/resources/ru/russian.dict") for n in names)
            assert any(n.endswith("pylat_ru/resources/ru/russian.info") for n in names)
            assert any(n.endswith("pylat_ru/resources/ru/added.txt") for n in names)
            assert any(n.endswith("pylat_ru/resources/ru/added_custom.txt") for n in names)
            assert any(n.endswith("pylat_ru/resources/ru/removed.txt") for n in names)
            assert any(n.endswith("pylat_ru/resources/ru/removed_custom.txt") for n in names)
            assert any(n.endswith("pylat_ru/resources/ru/multiwords.txt") for n in names)
            assert any(n.endswith("pylat_ru/resources/ru/disambiguation.xml") for n in names)

        # Install into target directory
        install_target = tmp_path / "site-packages"
        install_target.mkdir()
        install_proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(install_target), str(whl_path)],
            capture_output=True,
            text=True,
        )
        assert install_proc.returncode == 0, f"pip install failed: {install_proc.stderr}"

        # Run isolated verification script
        test_script = """
import sys
from pylat_ru.disambiguation import RussianHybridDisambiguator

disambiguator = RussianHybridDisambiguator.get_instance()
sentence = disambiguator.disambiguate_text("В целом, 73 процента людей согласны.")
tokens = sentence.get_tokens()

v_tok = next(t for t in tokens if t.token == "В")
assert v_tok.has_pos_tag("<ADV>")

num_tok = next(t for t in tokens if t.token == "73")
assert num_tok.has_pos_tag("NumD_D")
print("WHEEL_DISAMBIGUATION_SUCCESS")
"""
        run_env = dict(subprocess.os.environ)
        run_env["PYTHONPATH"] = str(install_target)
        run_proc = subprocess.run(
            [sys.executable, "-c", test_script],
            cwd=str(tmp_path),
            env=run_env,
            capture_output=True,
            text=True,
        )
        assert run_proc.returncode == 0, f"Isolated wheel execution failed: {run_proc.stderr}"
        assert "WHEEL_DISAMBIGUATION_SUCCESS" in run_proc.stdout
