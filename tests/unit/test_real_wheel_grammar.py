"""tests/unit/test_real_wheel_grammar.py

Automated real-wheel distribution test for LanguageTool Russian grammar engine.
Builds the wheel package, inspects packaged grammar.xml resource, installs into an isolated directory,
and executes the complete end-to-end pipeline (raw -> tag -> disambiguate -> chunk -> grammar check)
in a clean isolated Python subprocess without the repository root in sys.path.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_real_wheel_build_and_grammar_execution() -> None:
    """Build wheel, inspect grammar.xml in archive, install to isolated target, and verify grammar execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        dist_dir = tmp_path / "dist"
        dist_dir.mkdir()

        # 1. Build real wheel distribution
        build_proc = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist_dir), str(REPO_ROOT)],
            capture_output=True,
            text=True,
        )
        assert build_proc.returncode == 0, f"pip wheel failed: {build_proc.stderr}"

        wheels = list(dist_dir.glob("*.whl"))
        assert len(wheels) == 1, f"Expected 1 built wheel, found {len(wheels)}"
        whl_path = wheels[0]

        # 2. Inspect wheel zip entries and verify grammar.xml is present
        with zipfile.ZipFile(whl_path, "r") as zf:
            wheel_entries = set(zf.namelist())
            grammar_entries = [e for e in wheel_entries if e.endswith("pylat_ru/resources/rules/ru/grammar.xml")]
            assert len(grammar_entries) == 1, f"grammar.xml missing from wheel entries: {wheel_entries}"

        # 3. Install wheel into isolated target directory
        install_target = tmp_path / "site-packages"
        install_target.mkdir()
        install_proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--no-deps", "--target", str(install_target), str(whl_path)],
            capture_output=True,
            text=True,
        )
        assert install_proc.returncode == 0, f"pip install failed: {install_proc.stderr}"

        # 4. Run end-to-end pipeline in isolated subprocess without repository root in sys.path
        isolated_script = f"""
import sys
from pathlib import Path

# Remove any repo source paths from sys.path
sys.path = [p for p in sys.path if "src" not in p]

import pylat_ru
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.grammar.engine import RussianGrammarEngine

# Assert pylat_ru is loaded directly from installed site-packages target
assert Path(pylat_ru.__file__).resolve().is_relative_to(Path(r"{install_target}").resolve()), (
    f"Imported from unexpected location: {{pylat_ru.__file__}}"
)

text = "Ученик решил задать тест учителю."

# 1. Tag & Disambiguate
disambiguator = RussianHybridDisambiguator.get_instance()
sentence = disambiguator.disambiguate_text(text)
sentence.text = text

# 2. Chunk
chunker = RussianChunker()
chunker.chunk(sentence)

# 3. Grammar check
engine = RussianGrammarEngine.get_instance()
matches = engine.check_rule(sentence, "zadat_test")

assert len(matches) == 1, f"Expected 1 match, got {{len(matches)}}"
m = matches[0]
assert m.rule_id == "zadat_test"
assert m.full_rule_id == "zadat_test[1]"
assert m.from_pos == 13
assert m.to_pos == 24
assert m.suggestions == ["предложить тест"]
assert text[m.from_pos:m.to_pos] == "задать тест"

# 4. Check whole sentence with all core rules
all_matches = engine.check_sentence(sentence)
assert any(x.rule_id == "zadat_test" for x in all_matches)

print("REAL_WHEEL_GRAMMAR_SUCCESS")
"""
        run_env = dict(os.environ)
        run_env["PYTHONPATH"] = str(install_target)

        # Execute in a clean empty working directory
        run_proc = subprocess.run(
            [sys.executable, "-c", isolated_script],
            cwd=str(tmp_path),
            env=run_env,
            capture_output=True,
            text=True,
        )
        assert run_proc.returncode == 0, f"Isolated wheel execution failed:\nSTDOUT: {run_proc.stdout}\nSTDERR: {run_proc.stderr}"
        assert "REAL_WHEEL_GRAMMAR_SUCCESS" in run_proc.stdout
