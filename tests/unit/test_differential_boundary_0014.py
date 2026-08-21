"""Task 0014 section 18 - the differential campaign may use Java; the library may not.

The Task-0013 audit in ``test_production_dependency_audit_0013.py`` already proves the
package imports nothing from ``tools/``.  This module extends that proof to the
artefacts Task 0014 introduced: the batch oracle, the Java helper, the corpus runner,
the corpus data and the external natural corpus.  It also builds a real wheel and runs
``LanguageToolRU().check()`` from a clean interpreter with no Java on the path.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = REPO_ROOT / "src" / "pylat_ru"

#: Task-0014 development artefacts that must never appear inside the package or wheel.
TASK_0014_DEV_ARTEFACTS = (
    "tools/DifferentialCorpusOracle0014.java",
    "tools/differential_batch_oracle_0014.py",
    "tools/differential_corpus_0014.py",
    "tools/fetch_natural_corpus_0014.py",
)

#: Source patterns that would indicate production reaching into the campaign.
FORBIDDEN_SOURCE_PATTERNS_0014 = (
    re.compile(r"\bdifferential_batch_oracle_0014\b"),
    re.compile(r"\bdifferential_corpus_0014\b"),
    re.compile(r"\bfetch_natural_corpus_0014\b"),
    re.compile(r"\bDifferentialCorpusOracle0014\b"),
    re.compile(r"\bcorpora\b"),
    re.compile(r"\btest_corpora\b"),
    re.compile(r"\bBatchJavaOracle\b"),
    re.compile(r"\bru\.wikipedia\.org\b"),
    re.compile(r"\bru\.wikisource\.org\b"),
)

FORBIDDEN_TOP_LEVEL_IMPORTS_0014 = {
    "tools",
    "subprocess",
    "socket",
    "socketserver",
    "http",
    "urllib",
    "requests",
    "httpx",
    "jpype",
    "py4j",
    "jnius",
}


def _package_modules() -> list[Path]:
    return sorted(
        path
        for path in PACKAGE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    )


def test_package_does_not_import_task_0014_tooling() -> None:
    offenders: list[str] = []
    for path in _package_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            for name in names:
                if name.split(".")[0] in FORBIDDEN_TOP_LEVEL_IMPORTS_0014:
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {name}")
    assert offenders == [], "forbidden production imports:\n  " + "\n  ".join(offenders)


def test_package_sources_never_mention_the_campaign_or_corpora() -> None:
    offenders: list[str] = []
    for path in _package_modules():
        source = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_SOURCE_PATTERNS_0014:
            if pattern.search(source):
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}: {pattern.pattern}"
                )
    assert offenders == [], "forbidden dev references:\n  " + "\n  ".join(offenders)


def test_task_0014_artefacts_live_outside_the_package() -> None:
    for relative in TASK_0014_DEV_ARTEFACTS:
        path = REPO_ROOT / relative
        assert path.is_file(), relative
        assert not (PACKAGE_ROOT / Path(relative).name).exists(), relative


def test_external_corpus_is_not_committed() -> None:
    """Section 19: no external corpus blob may reach version control."""
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    offenders = [
        path
        for path in tracked
        if path.startswith(("corpora/", "test_corpora/", ".oracle_cache/"))
        or path.endswith((".jsonl", ".zip", ".jar"))
    ]
    assert offenders == [], "external corpus material is committed:\n  " + "\n  ".join(
        offenders
    )


def test_gitignore_still_excludes_corpora_and_oracle_caches() -> None:
    ignore_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    for entry in ("corpora/", "test_corpora/", ".oracle_cache/"):
        assert entry in ignore_text, entry


def test_committed_task_0014_evidence_is_small_and_metadata_only() -> None:
    """Only the deterministic metadata artefacts are committed, not raw campaign logs."""
    for relative, limit_bytes in (
        ("compat/differential_corpus_0014_manifest.json", 2_000_000),
        ("compat/differential_summary_0014.json", 2_000_000),
        ("compat/differential_allowlist_0014.json", 100_000),
        ("compat/differential_upstream_defects_0014.json", 100_000),
        ("compat/differential_state_isolation_0014.json", 100_000),
        ("tests/fixtures/differential_regressions_0014.json", 2_000_000),
        ("tests/fixtures/oracle_utf16_calibration_0014.json", 2_000_000),
    ):
        path = REPO_ROOT / relative
        assert path.is_file(), relative
        assert path.stat().st_size <= limit_bytes, (relative, path.stat().st_size)


@pytest.mark.parametrize("with_java_on_path", [False])
def test_real_wheel_is_java_free_and_carries_no_campaign_material(
    with_java_on_path: bool,
) -> None:
    """Build a real wheel, install it, and check Russian text with no Java available."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        dist_dir = tmp_path / "dist"
        target_dir = tmp_path / "site"
        dist_dir.mkdir()
        target_dir.mkdir()

        build = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "-w",
                str(dist_dir),
                str(REPO_ROOT),
            ],
            capture_output=True,
            text=True,
        )
        assert build.returncode == 0, f"pip wheel failed: {build.stderr}"
        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1, [w.name for w in wheels]

        with zipfile.ZipFile(wheels[0], "r") as archive:
            entries = archive.namelist()

        forbidden = [
            entry
            for entry in entries
            if entry.endswith((".java", ".class", ".jar", ".jsonl"))
            or "/tools/" in entry
            or entry.startswith("tools/")
            or "corpora" in entry
            or "differential_" in entry
            or "wikipedia" in entry.lower()
            or "wikisource" in entry.lower()
        ]
        assert forbidden == [], "campaign material shipped in the wheel:\n  " + "\n  ".join(
            forbidden
        )

        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--target",
                str(target_dir),
                str(wheels[0]),
            ],
            capture_output=True,
            text=True,
        )
        assert install.returncode == 0, f"pip install failed: {install.stderr}"

        # A clean interpreter: no repository root on sys.path and no Java on PATH.
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() not in {"PATH", "PYTHONPATH", "JAVA_HOME"}
        }
        environment["PYTHONPATH"] = str(target_dir)
        environment["PATH"] = str(Path(sys.executable).parent)
        environment["PYTHONIOENCODING"] = "utf-8"

        script = (
            "import shutil, sys;\n"
            "assert shutil.which('java') is None, 'java must not be reachable';\n"
            "assert shutil.which('javac') is None, 'javac must not be reachable';\n"
            "from pylat_ru import LanguageToolRU;\n"
            "import pylat_ru;\n"
            "assert 'pylat_ru' in pylat_ru.__file__;\n"
            "matches = LanguageToolRU().check('Это тест.');\n"
            "assert isinstance(matches, list);\n"
            "matches = LanguageToolRU().check('Это тестовый текст с ашибкой.');\n"
            "assert [m.rule_id for m in matches] == ['MORFOLOGIK_RULE_RU_RU'], "
            "[m.rule_id for m in matches];\n"
            "assert (matches[0].utf16_offset, matches[0].utf16_length) == (21, 7);\n"
            "assert 'tools' not in sys.modules;\n"
            "print('OK')\n"
        )
        run = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env=environment,
        )
        assert run.returncode == 0, f"clean-environment run failed:\n{run.stderr}"
        assert "OK" in run.stdout
