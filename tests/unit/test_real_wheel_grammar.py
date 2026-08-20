"""tests/unit/test_real_wheel_grammar.py

Automated real-wheel distribution test for LanguageTool Russian grammar engine.
Builds the wheel package, inspects packaged grammar.xml resource, installs into an isolated directory,
and executes the complete end-to-end pipeline (raw -> tag -> disambiguate -> chunk -> grammar check)
in a clean isolated Python subprocess without the repository root in sys.path.
Asserts exact metadata, offsets (codepoint and UTF-16), pattern spans, message, suggestions,
and proves production execution operates without Java, network, or server subprocess calls.
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
            assert any(e.endswith("pylat_ru/resources/ru/compounds.txt") for e in wheel_entries)
            assert any(e.endswith("pylat_ru/resources/ru/specific_case.txt") for e in wheel_entries)

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
import socket
import subprocess
import urllib.request
from pathlib import Path

# Guard against network or external process invocation in production execution
def _block_network(*args, **kwargs):
    raise RuntimeError("Forbidden network socket access during production execution")

def _block_subprocess(*args, **kwargs):
    raise RuntimeError("Forbidden subprocess execution during production execution")

socket.socket = _block_network
subprocess.Popen = _block_subprocess
subprocess.run = _block_subprocess

# Remove any repo source paths from sys.path
sys.path = [p for p in sys.path if "src" not in p]

import pylat_ru
from pylat_ru import LanguageToolRU
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
assert m.category_id == "LOGIC"
assert m.from_pos == 13
assert m.to_pos == 24
assert m.from_pos_utf16 == 13
assert m.to_pos_utf16 == 24
assert m.pattern_from_pos == 13
assert m.pattern_to_pos == 24
assert m.pattern_from_pos_utf16 == 13
assert m.pattern_to_pos_utf16 == 24
assert m.suggestions == ["предложить тест"]
assert text[m.from_pos:m.to_pos] == "задать тест"
assert "<suggestion>предложить тест</suggestion>" in m.message

# 4. Check whole sentence with all runnable rules
all_matches = engine.check_sentence(sentence)
assert any(x.rule_id == "zadat_test" for x in all_matches)

# 5. Check advanced 0008 rule (vopreki_NN) with synthesis and multiple suggestions
adv_text = "Вопреки утверждения ФАС дефицит топлива возможен."
adv_sentence = disambiguator.disambiguate_text(adv_text)
adv_sentence.text = adv_text
chunker.chunk(adv_sentence)
adv_matches = engine.check_rule(adv_sentence, "vopreki_NN")
assert len(adv_matches) == 1, f"Expected 1 match for vopreki_NN, got {{len(adv_matches)}}"
adv_m = adv_matches[0]
assert adv_m.rule_id == "vopreki_NN"
assert adv_m.full_rule_id == "vopreki_NN[1]"
assert adv_m.from_pos == 0
assert adv_m.to_pos == 19
assert adv_m.from_pos_utf16 == 0
assert adv_m.to_pos_utf16 == 19
assert adv_m.suggestions == ["Вопреки утверждению", "Вопреки утвержденью"]

# 6. Check unification 0009 rule (Unify_Mult_Adj) with feature unification agreement
uni_text = "Крыловский государственной научный центр"
uni_sentence = disambiguator.disambiguate_text(uni_text)
uni_sentence.text = uni_text
chunker.chunk(uni_sentence)
uni_matches = engine.check_rule(uni_sentence, "Unify_Mult_Adj")
assert len(uni_matches) == 1, f"Expected 1 match for Unify_Mult_Adj, got {{len(uni_matches)}}"
uni_m = uni_matches[0]
assert uni_m.rule_id == "Unify_Mult_Adj"
assert uni_m.full_rule_id == "Unify_Mult_Adj[1]"
assert uni_m.category_id == "GRAMMAR"
assert uni_m.from_pos == 0
assert uni_m.to_pos == 40
assert uni_m.from_pos_utf16 == 0
assert uni_m.to_pos_utf16 == 40
assert uni_m.pattern_from_pos == 0
assert uni_m.pattern_to_pos == 40
assert uni_m.pattern_from_pos_utf16 == 0
assert uni_m.pattern_to_pos_utf16 == 40
assert uni_m.message == "Прилагательное не согласуется с существительным по роду."
assert uni_m.short_message == "Грамматическая ошибка в согласовании рода"
assert uni_m.suggestions == []

# 7. Check a real AdvancedSynthesizerFilter rule and its exact replacement
filter_synth_text = "моему отношение"
filter_synth_sentence = disambiguator.disambiguate_text(filter_synth_text)
filter_synth_sentence.text = filter_synth_text
chunker.chunk(filter_synth_sentence)
filter_synth_matches = engine.check_rule(filter_synth_sentence, "Unify_PADJ_NN_case[1]")
assert len(filter_synth_matches) == 1
filter_synth_match = filter_synth_matches[0]
assert filter_synth_match.rule_id == "Unify_PADJ_NN_case"
assert filter_synth_match.full_rule_id == "Unify_PADJ_NN_case[1]"
assert filter_synth_match.from_pos == 0
assert filter_synth_match.to_pos == 15
assert filter_synth_match.from_pos_utf16 == 0
assert filter_synth_match.to_pos_utf16 == 15
assert filter_synth_match.pattern_from_pos == 0
assert filter_synth_match.pattern_to_pos == 15
assert filter_synth_match.pattern_from_pos_utf16 == 0
assert filter_synth_match.pattern_to_pos_utf16 == 15
assert filter_synth_match.message == "Притяжательное прилагательное (местоимение) не согласуется с существительным по падежу."
assert filter_synth_match.short_message == "Не согласуются по падежу"
assert filter_synth_match.suggestions == ["моё отношение"]

# 8. Check a real RussianPartialPosTagFilter rule
partial_pos_text = "Работа выполнена далеко неплохо."
partial_pos_sentence = disambiguator.disambiguate_text(partial_pos_text)
partial_pos_sentence.text = partial_pos_text
chunker.chunk(partial_pos_sentence)
partial_pos_matches = engine.check_rule(partial_pos_sentence, "Ne_narech[3]")
assert len(partial_pos_matches) == 1
partial_pos_match = partial_pos_matches[0]
assert partial_pos_match.full_rule_id == "Ne_narech[3]"
assert partial_pos_match.from_pos == 17
assert partial_pos_match.to_pos == 31
assert partial_pos_match.from_pos_utf16 == 17
assert partial_pos_match.to_pos_utf16 == 31
assert partial_pos_match.message == "Пишется раздельно с «не»: <suggestion>далеко не плохо</suggestion>."
assert partial_pos_match.short_message == "Раздельно с «не»"
assert partial_pos_match.suggestions == ["далеко не плохо"]

# 9. Check a deterministic INNNumberFilter rule
inn_text = "ИНН: 1234567890"
inn_sentence = disambiguator.disambiguate_text(inn_text)
inn_sentence.text = inn_text
chunker.chunk(inn_sentence)
inn_matches = engine.check_rule(inn_sentence, "WRONG_INN[1]")
assert len(inn_matches) == 1
inn_match = inn_matches[0]
assert inn_match.full_rule_id == "WRONG_INN[1]"
assert inn_match.from_pos == 0
assert inn_match.to_pos == 15
assert inn_match.from_pos_utf16 == 0
assert inn_match.to_pos_utf16 == 15
assert inn_match.message == "Некорректный ИНН: 1234567890"
assert inn_match.short_message == "Некорректный ИНН"
assert inn_match.suggestions == []

# 10. Task-0011 native Java-rule equivalents execute from the wheel only.
native_tool = LanguageToolRU(enabled_rules=["WHITESPACE_PARAGRAPH_BEGIN"])
native_text = " Текст. Я идёт. Ростов — на — Дону. Это  тест."
native_matches = native_tool.check(native_text)
native_ids = {{m.rule_id for m in native_matches}}
assert "WHITESPACE_RULE" in native_ids                 # generic whitespace
assert "WHITESPACE_PARAGRAPH_BEGIN" in native_ids      # paragraph/default enablement
assert "RU_DASH_RULE" in native_ids                    # pinned packaged compounds.txt
assert "RU_VERB_CONJUGATION" in native_ids             # accepted native morphology
assert all(m.source in {{"xml_grammar", "java_rule_0011"}} for m in native_matches)

print("REAL_WHEEL_GRAMMAR_SUCCESS")
"""
        run_env = dict(os.environ)
        run_env["PYTHONPATH"] = str(install_target)
        run_env.pop("JAVA_HOME", None)

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
