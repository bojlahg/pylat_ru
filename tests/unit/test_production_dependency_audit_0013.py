"""Task 0013 section 36 - production must stay free of dev/test dependencies.

The upstream-test parity infrastructure added by Task 0013 lives entirely in
``tools/`` and ``tests/``.  This module proves that none of it leaked into the
importable library or into the built distribution.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "pylat_ru"

FORBIDDEN_TOP_LEVEL_IMPORTS = {
    "pytest",
    "tools",
    "unittest",
    "jpype",
    "py4j",
    "jnius",
    "requests",
    "urllib",
    "urllib2",
    "http",
    "socket",
    "subprocess",
    "shutil",
}

# Task 0013 section 36 forbids production reaching the vendored Java *test*
# tree, the Java oracle and the development tooling.  The vendored upstream
# *main* resource directory remains a documented last-resort development
# fallback in two resource loaders; the wheel isolation tests prove the
# installed distribution never needs it.
FORBIDDEN_SOURCE_PATTERNS = (
    re.compile(r"third_party/languagetool[^\"']*src/test"),
    re.compile(r"\blanguagetool-commandline\b"),
    re.compile(r"\boracle_manifest\b"),
    re.compile(r"\.oracle_cache\b"),
    re.compile(r"\bjava\s+-cp\b"),
    re.compile(r"\bJavaRulesOracle\w*\b"),
    re.compile(r"upstream_test_inventory"),
    re.compile(r"\bfrom tools\b|\bimport tools\b"),
)


def _python_modules() -> list[Path]:
    return sorted(p for p in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def test_production_modules_have_no_dev_or_java_imports() -> None:
    offenders: list[str] = []
    for path in _python_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                top = name.split(".")[0]
                if top in FORBIDDEN_TOP_LEVEL_IMPORTS:
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {name}")
    assert offenders == [], "forbidden production imports:\n  " + "\n  ".join(offenders)


def test_production_sources_do_not_reference_dev_assets() -> None:
    offenders: list[str] = []
    for path in _python_modules():
        source = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_SOURCE_PATTERNS:
            if pattern.search(source):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}: {pattern.pattern}"
                )
    assert offenders == [], "forbidden dev-asset references:\n  " + "\n  ".join(offenders)


def test_upstream_test_infrastructure_stays_outside_the_package() -> None:
    """The Task-0013 tooling and fixtures live only under tools/ and tests/."""
    for relative in (
        "tools/java_test_parser.py",
        "tools/inventory_upstream_tests_0013.py",
        "tools/generate_upstream_tests_fixtures_0013.py",
        "tools/audit_tagger_dictionary_0013.py",
        "tests/fixtures/oracle_upstream_tests_0013.json",
        "compat/upstream_test_inventory_0013.json",
    ):
        assert (REPO_ROOT / relative).is_file(), relative
        assert not (PACKAGE_ROOT / Path(relative).name).exists(), relative


def test_wheel_contains_no_upstream_test_or_oracle_material() -> None:
    """The built distribution ships runtime resources only."""
    with tempfile.TemporaryDirectory() as tmpdir:
        dist_dir = Path(tmpdir)
        build = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(REPO_ROOT)],
            capture_output=True, text=True,
        )
        assert build.returncode == 0, f"pip wheel failed: {build.stderr}"
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1
        with zipfile.ZipFile(wheels[0], "r") as archive:
            entries = archive.namelist()

    forbidden = [
        entry for entry in entries
        if "/src/test/" in entry
        or entry.endswith(".java")
        or entry.endswith(".jar")
        or (
            "third_party/" in entry
            and ".dist-info/licenses/third_party/" not in entry
        )
        or "/tools/" in entry
        or entry.startswith("tools/")
        or "oracle_" in entry
        or "upstream_test_inventory" in entry
    ]
    assert forbidden == [], "dev-only material shipped in the wheel:\n  " + "\n  ".join(forbidden)
    assert any(e.endswith("pylat_ru/resources/rules/ru/grammar.xml") for e in entries)
    assert any(e.endswith("licenses/third_party/languagetool/COPYING.txt") for e in entries)
    assert any(e.endswith("licenses/third_party/languagetool/LICENSES.md") for e in entries)
