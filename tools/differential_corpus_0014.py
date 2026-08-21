"""Task-0014 differential corpus: build, run, summarize, minimize, verify.

Development/test only.  Nothing in ``src/pylat_ru`` imports this module, and the
installed wheel contains neither this file, the Java helper, nor any corpus data.

The module owns four things:

* a deterministic, strongly typed corpus of Russian whole-text cases across five
  strata (accepted upstream evidence, deterministic mutations, spelling stress,
  natural prose, targeted Unicode/offset cases);
* a campaign runner that drives one long-lived pinned Java oracle and one
  long-lived Python pipeline per profile and compares every case strictly;
* a summary generator whose every rate is derived from integer counts;
* a deterministic mismatch minimizer.

Commands::

    python -m tools.differential_corpus_0014 validate-oracle
    python -m tools.differential_corpus_0014 build
    python -m tools.differential_corpus_0014 run [--stratum A] [--profile default] [--shard 1/4] [--resume]
    python -m tools.differential_corpus_0014 summarize
    python -m tools.differential_corpus_0014 minimize [--limit N]
    python -m tools.differential_corpus_0014 verify-regressions
    python -m tools.differential_corpus_0014 state-isolation [--sample N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
#: Development escape hatch: point the campaign at another checkout's ``src`` so the
#: same corpus and comparator can measure an earlier implementation.  Task 0014 uses it
#: to reproduce the initial mismatch count against the Task-0013 baseline.
sys.path.insert(0, os.environ.get("PYLAT_RU_SRC_OVERRIDE") or str(REPO_ROOT / "src"))

from tools.differential_batch_oracle_0014 import (  # noqa: E402
    BatchJavaOracle,
    LANGUAGE_MODEL_RULE_ID,
    OracleProtocolError,
    Profile,
    pylat_findings,
)
from tools.differential_lt import (  # noqa: E402
    PINNED_LT_COMMIT,
    PINNED_LT_VERSION,
    Finding,
    JavaLanguageToolOracle,
    compare_findings,
    sha256_file,
    validate_oracle_manifest,
)

# --------------------------------------------------------------------------
# Identity and paths
# --------------------------------------------------------------------------

TASK = "0014"
SCHEMA_VERSION = "2.0.0"

#: Committed fixed seed for every generated Task-0014 stratum.
FIXED_SEED = 140014

#: Bumped whenever generated corpus content changes semantically.
GENERATOR_VERSION = "0014.3-second-review-fix"

CORPORA_DIR = REPO_ROOT / "corpora"
RESULTS_DIR = CORPORA_DIR / "results_0014"
CORPUS_PATH = CORPORA_DIR / "differential_corpus_0014.jsonl"
NATURAL_METADATA_PATH = CORPORA_DIR / "natural_ru_0014_metadata.json"

MANIFEST_PATH = REPO_ROOT / "compat" / "differential_corpus_0014_manifest.json"
SUMMARY_PATH = REPO_ROOT / "compat" / "differential_summary_0014.json"
REGRESSION_FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "differential_regressions_0014.json"
UTF16_CALIBRATION_PATH = REPO_ROOT / "tests" / "fixtures" / "oracle_utf16_calibration_0014.json"
ALLOWLIST_PATH = REPO_ROOT / "compat" / "differential_allowlist_0014.json"
UPSTREAM_DEFECTS_PATH = REPO_ROOT / "compat" / "differential_upstream_defects_0014.json"
STATE_ISOLATION_PATH = REPO_ROOT / "compat" / "differential_state_isolation_0014.json"

GRAMMAR_EXAMPLES_PATH = REPO_ROOT / "compat" / "extracted_grammar_examples.json"
JAVA_RULES_INVENTORY_PATH = REPO_ROOT / "compat" / "russian_java_rules_inventory.json"

#: Committed fixtures whose whole-text inputs feed Stratum A.
STRATUM_A_FIXTURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("tests/fixtures/oracle_upstream_tests_0013.json", ("single_rule",)),
    ("tests/fixtures/oracle_java_rules_0011_russian.json", ("single_rule",)),
    ("tests/fixtures/oracle_java_rules_0011_combined.json", ("combined_pipeline",)),
    ("tests/fixtures/oracle_java_rules_0012_rules.json", ("single_rule",)),
    ("tests/fixtures/oracle_java_rules_0012_spelling.json", ("single_rule",)),
    ("tests/fixtures/oracle_java_rules_0012_combined.json", ("combined_pipeline",)),
)

STRATA = ("A", "B", "C", "D", "E")
STRATUM_NAMES = {
    "A": "accepted_upstream_evidence",
    "B": "deterministic_mutations",
    "C": "spelling_stress",
    "D": "natural_russian_prose",
    "E": "unicode_offset_targeted",
}


# --------------------------------------------------------------------------
# Case schema
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusCase:
    """One deterministic whole-text differential case."""

    case_id: str
    source_stratum: str
    text: str
    profile: str
    provenance: Mapping[str, Any] = field(default_factory=dict)
    mutation_parent_id: Optional[str] = None
    mutation_kind: Optional[str] = None
    seed: Optional[int] = None
    external_source_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


def semantic_identity(text: str, profile: Profile) -> str:
    """Stable identity of a case: its text plus its exact profile state.

    Deliberately independent of anything Java returns, so accidental duplication and
    generator drift stay visible instead of being masked by matching oracle output.
    """
    payload = json.dumps(
        {"text": text, "profile": profile.to_dict()},
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def make_case_id(stratum: str, index: int, identity: str) -> str:
    return f"{stratum}{index:06d}_{identity[:12]}"


# --------------------------------------------------------------------------
# Profiles
# --------------------------------------------------------------------------


def java_rule_default_off_ids() -> List[str]:
    """Default-off ordinary Java rule ids, read from the pinned Java-rule inventory."""
    inventory = json.loads(JAVA_RULES_INVENTORY_PATH.read_text(encoding="utf-8"))
    return sorted(
        rule["rule_id"]
        for rule in inventory["rules"]
        if rule["default_off"] and rule["rule_id"] != LANGUAGE_MODEL_RULE_ID
    )


def xml_rule_default_off_ids() -> List[str]:
    """Default-off XML rule ids, read from the pinned Russian ``grammar.xml``."""
    from pylat_ru.grammar import RussianGrammarEngine

    engine = RussianGrammarEngine.get_instance()
    return sorted({rule.id for rule in engine.get_all_rules() if rule.default_off})


def default_off_rule_ids() -> List[str]:
    """Every ordinary non-LM Russian rule that is registered but default-off."""
    return sorted(set(java_rule_default_off_ids()) | set(xml_rule_default_off_ids()))


def build_profiles() -> Dict[str, Profile]:
    """The whole-pipeline profiles the campaign runs, applied identically to both sides."""
    all_off = tuple(default_off_rule_ids())
    profiles = [
        Profile(profile_id="default"),
        Profile(
            profile_id="all_ordinary_enabled",
            enabled_rules=all_off,
            enable_all_default_off=True,
        ),
        Profile(
            profile_id="cfg_long_sentence_15",
            rule_config={"TOO_LONG_SENTENCE": {"maxWords": 15}},
            level="PICKY",
        ),
        Profile(
            profile_id="cfg_long_paragraph_30",
            enabled_rules=("TOO_LONG_PARAGRAPH",),
            rule_config={"TOO_LONG_PARAGRAPH": {"maxWords": 30}},
            level="PICKY",
        ),
        Profile(
            profile_id="cfg_filler_words_2",
            enabled_rules=("FILLER_WORDS_RU",),
            rule_config={
                "FILLER_WORDS_RU": {"minPercent": 2, "excludeDirectSpeech": False}
            },
        ),
        Profile(
            profile_id="cfg_speller_conf_ru_0",
            rule_config={"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": 0}},
        ),
        Profile(
            profile_id="cfg_speller_conf_ru_1",
            rule_config={"MORFOLOGIK_RULE_RU_RU": {"conf_ru_Value": 1}},
        ),
        Profile(
            profile_id="ref_picky",
            level="PICKY",
        ),
        Profile(
            profile_id="ref_long_paragraph_default",
            enabled_rules=("TOO_LONG_PARAGRAPH",),
            level="PICKY",
        ),
        Profile(
            profile_id="ref_filler_words_default",
            enabled_rules=("FILLER_WORDS_RU",),
        ),
        Profile(
            profile_id="cfg_speller_yo",
            enabled_rules=("MORFOLOGIK_RULE_RU_RU_YO",),
            disabled_rules=("MORFOLOGIK_RULE_RU_RU",),
        ),
    ]
    return {profile.profile_id: profile for profile in profiles}


def python_tool(profile: Profile):
    """Build the Python pipeline for ``profile`` with the identical configuration."""
    from pylat_ru import LanguageToolRU

    enabled = list(profile.enabled_rules)
    if profile.enable_all_default_off:
        enabled = sorted(set(enabled) | set(default_off_rule_ids()))
    return LanguageToolRU(
        enabled_rules=enabled,
        disabled_rules=list(profile.disabled_rules),
        rule_config={k: dict(v) for k, v in profile.rule_config.items()} or None,
    )


# --------------------------------------------------------------------------
# Stratum A - accepted pinned/upstream text evidence
# --------------------------------------------------------------------------


def _grammar_example_texts() -> List[Tuple[str, Dict[str, Any]]]:
    payload = json.loads(GRAMMAR_EXAMPLES_PATH.read_text(encoding="utf-8"))
    texts: List[Tuple[str, Dict[str, Any]]] = []
    for example in payload["examples"]:
        text = example["text"]
        if not text.strip():
            continue
        texts.append(
            (
                text,
                {
                    "source": "compat/extracted_grammar_examples.json",
                    "example_id": example["example_id"],
                    "rule_id": example["rule_id"],
                    "example_type": example["type"],
                },
            )
        )
    return texts


def _fixture_texts() -> List[Tuple[str, Dict[str, Any]]]:
    """Whole-text inputs from accepted Task-0011/0012/0013 oracle fixtures.

    ``direct_speller`` cases are intentionally excluded: they probe the speller API
    with bare words, not whole-text grammar-check inputs.
    """
    texts: List[Tuple[str, Dict[str, Any]]] = []
    for relative_path, accepted_modes in STRATUM_A_FIXTURES:
        path = REPO_ROOT / relative_path
        payload = json.loads(path.read_text(encoding="utf-8"))
        for case in payload["cases"]:
            if case.get("execution_mode") not in accepted_modes:
                continue
            text = case.get("text", "")
            if not text.strip():
                continue
            texts.append(
                (
                    text,
                    {
                        "source": relative_path,
                        "fixture_case_id": case["id"],
                        "rule_id": case.get("rule_id", ""),
                        "execution_mode": case["execution_mode"],
                    },
                )
            )
    return texts


def build_stratum_a() -> List[Tuple[str, Dict[str, Any]]]:
    return _grammar_example_texts() + _fixture_texts()


# --------------------------------------------------------------------------
# Stratum B - deterministic mutation corpus
# --------------------------------------------------------------------------

RUSSIAN_LETTERS = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
NBSP = " "
SOFT_HYPHEN = "­"
COMBINING_ACUTE = "́"
COMBINING_GRAVE = "̀"
EMOJI = ("\U0001F600", "\U0001F680", "\U0001F914", "\U0001F4DA")

MutationFn = Callable[[str, random.Random], Optional[str]]


def _word_spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"[^\W\d_]+", text, re.UNICODE)]


def _pick_word(text: str, rng: random.Random) -> Optional[Tuple[int, int]]:
    spans = [s for s in _word_spans(text) if s[1] - s[0] >= 4]
    return rng.choice(spans) if spans else None


def _sentence_spans(text: str) -> List[Tuple[int, int]]:
    spans: List[Tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[.!?…]+[\s]+", text):
        spans.append((start, match.end()))
        start = match.end()
    if start < len(text):
        spans.append((start, len(text)))
    return spans


# -- whitespace / boundaries ------------------------------------------------


def _m_space_before_punct(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start() for m in re.finditer(r"(?<=\S)[,.;:!?]", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[:index] + " " + text[index:]


def _m_remove_space_after_punct(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start(1) for m in re.finditer(r"[,.;:!?](\s)\S", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[:index] + text[index + 1 :]


def _m_double_space(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start() for m in re.finditer(r" ", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[:index] + "  " + text[index + 1 :]


def _m_tab_instead_space(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start() for m in re.finditer(r" ", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[:index] + "\t" + text[index + 1 :]


def _m_nbsp_instead_space(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start() for m in re.finditer(r" ", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[:index] + NBSP + text[index + 1 :]


def _m_linebreak_instead_space(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start() for m in re.finditer(r" ", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[:index] + "\n" + text[index + 1 :]


def _m_paragraph_break(text: str, rng: random.Random) -> Optional[str]:
    spans = _sentence_spans(text)
    if len(spans) < 2:
        return text + "\n\n" + text
    index = rng.randrange(1, len(spans))
    cut = spans[index][0]
    return text[:cut].rstrip() + "\n\n" + text[cut:]


def _m_leading_trailing_whitespace(text: str, rng: random.Random) -> Optional[str]:
    prefix = rng.choice(["  ", "\t", "\n", " \t "])
    suffix = rng.choice(["  ", "\t", "\n", " \n "])
    return prefix + text + suffix


# -- case -------------------------------------------------------------------


def _m_lowercase_sentence_start(text: str, rng: random.Random) -> Optional[str]:
    spans = [s for s in _sentence_spans(text) if s[0] < len(text) and text[s[0]].isupper()]
    if not spans:
        return None
    index = rng.choice(spans)[0]
    return text[:index] + text[index].lower() + text[index + 1 :]


def _m_title_case(text: str, rng: random.Random) -> Optional[str]:
    return " ".join(
        word[:1].upper() + word[1:] if word else word for word in text.split(" ")
    )


def _m_all_caps(text: str, rng: random.Random) -> Optional[str]:
    upper = text.upper()
    return upper if upper != text else None


def _m_mixed_case(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    word = text[start:end]
    flipped = "".join(
        c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(word)
    )
    if flipped == word:
        return None
    return text[:start] + flipped + text[end:]


# -- punctuation / typography ----------------------------------------------


def _replace_random(text: str, pattern: str, replacement: str, rng: random.Random) -> Optional[str]:
    positions = [(m.start(), m.end()) for m in re.finditer(pattern, text)]
    if not positions:
        return None
    start, end = rng.choice(positions)
    return text[:start] + replacement + text[end:]


def _m_hyphen_to_endash(text: str, rng: random.Random) -> Optional[str]:
    return _replace_random(text, r"-", "–", rng)


def _m_hyphen_to_emdash(text: str, rng: random.Random) -> Optional[str]:
    return _replace_random(text, r"-", "—", rng)


def _m_straight_quotes(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    return text[:start] + '"' + text[start:end] + '"' + text[end:]


def _m_russian_quotes(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    return text[:start] + "«" + text[start:end] + "»" + text[end:]


def _m_nested_quotes(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    inner = "«„" + text[start:end] + "“»"
    return text[:start] + inner + text[end:]


def _m_brackets(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    opening, closing = rng.choice([("(", ")"), ("[", "]"), ("{", "}"), ("(", "")])
    return text[:start] + opening + text[start:end] + closing + text[end:]


def _m_ellipsis(text: str, rng: random.Random) -> Optional[str]:
    variant = rng.choice(["...", "…", ".. .", "....."])
    replaced = _replace_random(text, r"[.!?]$", variant, rng)
    return replaced if replaced is not None else text + variant


def _m_punct_variant(text: str, rng: random.Random) -> Optional[str]:
    variant = rng.choice(["?", "!", "?!", "!!", ".", ";", ",", "!?"])
    return _replace_random(text, r"[.!?;,]", variant, rng)


# -- Russian spelling / orthography ----------------------------------------


def _m_yo_to_e(text: str, rng: random.Random) -> Optional[str]:
    return _replace_random(text, r"[ёЁ]", "е", rng)


def _m_e_to_yo(text: str, rng: random.Random) -> Optional[str]:
    return _replace_random(text, r"е", "ё", rng)


def _m_delete_char(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    index = rng.randrange(start, end)
    return text[:index] + text[index + 1 :]


def _m_insert_char(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    index = rng.randrange(start, end)
    return text[:index] + rng.choice(RUSSIAN_LETTERS) + text[index:]


def _m_transpose_adjacent(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    index = rng.randrange(start, end - 1)
    if text[index] == text[index + 1]:
        return None
    return text[:index] + text[index + 1] + text[index] + text[index + 2 :]


def _m_substitute_cyrillic(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    index = rng.randrange(start, end)
    replacement = rng.choice(RUSSIAN_LETTERS)
    if replacement == text[index].lower():
        return None
    return text[:index] + replacement + text[index + 1 :]


def _m_hyphenation_perturb(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    if end - start < 5:
        return None
    index = rng.randrange(start + 2, end - 1)
    return text[:index] + "-" + text[index:]


# -- repetitions ------------------------------------------------------------


def _m_duplicate_word(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    return text[:end] + " " + text[start:end] + text[end:]


def _m_repeat_root_short_range(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    word = text[start:end]
    if len(word) < 6:
        return None
    root = word[: len(word) - 2]
    return text[:end] + " и " + root + "ами" + text[end:]


def _m_paragraph_begin_repeat(text: str, rng: random.Random) -> Optional[str]:
    spans = _sentence_spans(text)
    first = text[spans[0][0] : spans[0][1]].strip()
    if not first:
        return None
    return first + "\n\n" + first + " " + text


# -- Unicode / offsets ------------------------------------------------------


def _m_combining_acute(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start() for m in re.finditer(r"[аеёиоуыэюяАЕЁИОУЫЭЮЯ]", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[: index + 1] + COMBINING_ACUTE + text[index + 1 :]


def _m_combining_grave(text: str, rng: random.Random) -> Optional[str]:
    positions = [m.start() for m in re.finditer(r"[аеёиоуыэюяАЕЁИОУЫЭЮЯ]", text)]
    if not positions:
        return None
    index = rng.choice(positions)
    return text[: index + 1] + COMBINING_GRAVE + text[index + 1 :]


def _m_soft_hyphen(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, end = span
    index = rng.randrange(start + 1, end)
    return text[:index] + SOFT_HYPHEN + text[index:]


def _m_nonbmp_prefix(text: str, rng: random.Random) -> Optional[str]:
    return rng.choice(EMOJI) + " " + text


def _m_nonbmp_infix(text: str, rng: random.Random) -> Optional[str]:
    span = _pick_word(text, rng)
    if span is None:
        return None
    start, _ = span
    return text[:start] + rng.choice(EMOJI) + " " + text[start:]


def _m_multi_emoji(text: str, rng: random.Random) -> Optional[str]:
    prefix = "".join(rng.choice(EMOJI) for _ in range(3))
    return prefix + " " + text + " " + rng.choice(EMOJI) + rng.choice(EMOJI)


# -- sentence / paragraph composition --------------------------------------


def _m_insert_quote_bracket(text: str, rng: random.Random) -> Optional[str]:
    spans = _sentence_spans(text)
    index = rng.randrange(len(spans))
    start, end = spans[index]
    sentence = text[start:end].strip()
    if not sentence:
        return None
    quoted = "«" + sentence + "» (" + sentence + ")"
    return text[:start] + quoted + " " + text[end:]


def _m_split_at_boundary(text: str, rng: random.Random) -> Optional[str]:
    if len(text) < 20:
        return None
    index = rng.randrange(len(text) // 4, 3 * len(text) // 4)
    return text[:index].rstrip() + "\n" + text[index:].lstrip()


def _m_repeat_sentence_paragraphs(text: str, rng: random.Random) -> Optional[str]:
    spans = _sentence_spans(text)
    sentence = text[spans[0][0] : spans[0][1]].strip()
    if not sentence:
        return None
    return "\n\n".join([sentence, sentence, sentence])


MUTATION_FAMILIES: tuple[tuple[str, str, MutationFn], ...] = (
    ("whitespace", "space_before_punct", _m_space_before_punct),
    ("whitespace", "remove_space_after_punct", _m_remove_space_after_punct),
    ("whitespace", "double_space", _m_double_space),
    ("whitespace", "tab_instead_space", _m_tab_instead_space),
    ("whitespace", "nbsp_instead_space", _m_nbsp_instead_space),
    ("whitespace", "linebreak_instead_space", _m_linebreak_instead_space),
    ("whitespace", "paragraph_break", _m_paragraph_break),
    ("whitespace", "leading_trailing_whitespace", _m_leading_trailing_whitespace),
    ("case", "lowercase_sentence_start", _m_lowercase_sentence_start),
    ("case", "title_case", _m_title_case),
    ("case", "all_caps", _m_all_caps),
    ("case", "mixed_case", _m_mixed_case),
    ("punctuation", "hyphen_to_endash", _m_hyphen_to_endash),
    ("punctuation", "hyphen_to_emdash", _m_hyphen_to_emdash),
    ("punctuation", "straight_quotes", _m_straight_quotes),
    ("punctuation", "russian_quotes", _m_russian_quotes),
    ("punctuation", "nested_quotes", _m_nested_quotes),
    ("punctuation", "brackets", _m_brackets),
    ("punctuation", "ellipsis", _m_ellipsis),
    ("punctuation", "punct_variant", _m_punct_variant),
    ("spelling", "yo_to_e", _m_yo_to_e),
    ("spelling", "e_to_yo", _m_e_to_yo),
    ("spelling", "delete_char", _m_delete_char),
    ("spelling", "insert_char", _m_insert_char),
    ("spelling", "transpose_adjacent", _m_transpose_adjacent),
    ("spelling", "substitute_cyrillic", _m_substitute_cyrillic),
    ("spelling", "hyphenation_perturb", _m_hyphenation_perturb),
    ("repetition", "duplicate_word", _m_duplicate_word),
    ("repetition", "repeat_root_short_range", _m_repeat_root_short_range),
    ("repetition", "paragraph_begin_repeat", _m_paragraph_begin_repeat),
    ("unicode", "combining_acute", _m_combining_acute),
    ("unicode", "combining_grave", _m_combining_grave),
    ("unicode", "soft_hyphen", _m_soft_hyphen),
    ("unicode", "nonbmp_prefix", _m_nonbmp_prefix),
    ("unicode", "nonbmp_infix", _m_nonbmp_infix),
    ("unicode", "multi_emoji", _m_multi_emoji),
    ("composition", "insert_quote_bracket", _m_insert_quote_bracket),
    ("composition", "split_at_boundary", _m_split_at_boundary),
    ("composition", "repeat_sentence_paragraphs", _m_repeat_sentence_paragraphs),
)

MUTATION_FAMILY_NAMES = tuple(sorted({family for family, _, _ in MUTATION_FAMILIES}))
MUTATION_KINDS = tuple(kind for _, kind, _ in MUTATION_FAMILIES)


def build_stratum_b(
    seeds: Sequence[Tuple[str, Dict[str, Any]]], seed: int = FIXED_SEED
) -> List[Tuple[str, Dict[str, Any]]]:
    """Deterministically mutate accepted Russian seed texts.

    Seeds are drawn with a string-seeded :class:`random.Random`, never with Python's
    process-randomised ``hash()``, so selection is identical on 3.10 and 3.12.
    """
    usable = [pair for pair in seeds if len(pair[0]) >= 25]
    usable.sort(key=lambda pair: pair[0])
    if not usable:
        return []

    results: List[Tuple[str, Dict[str, Any]]] = []
    per_kind = max(1, 2500 // len(MUTATION_FAMILIES))
    for kind_index, (family, kind, mutate) in enumerate(MUTATION_FAMILIES):
        picker = random.Random(f"{seed}:pick:{kind}")
        indices = sorted(
            picker.sample(range(len(usable)), min(per_kind * 3, len(usable)))
        )
        produced = 0
        for seed_index in indices:
            if produced >= per_kind:
                break
            source_text, source_provenance = usable[seed_index]
            rng = random.Random(f"{seed}:{kind}:{seed_index}")
            mutated = mutate(source_text, rng)
            if not mutated or mutated == source_text or not mutated.strip():
                continue
            produced += 1
            results.append(
                (
                    mutated,
                    {
                        "source": "mutation",
                        "mutation_family": family,
                        "mutation_kind": kind,
                        "mutation_order": kind_index,
                        "seed_text_sha256": hashlib.sha256(
                            source_text.encode("utf-8")
                        ).hexdigest(),
                        "seed_provenance": source_provenance,
                    },
                )
            )
    return results


# --------------------------------------------------------------------------
# Stratum C - spelling / suggestion stress
# --------------------------------------------------------------------------

#: Sentence frames so every stress word is checked as a whole-text input.
SPELLING_FRAMES = (
    "Слово {word} встречается в тексте.",
    "Мы обсудили {word} вчера вечером.",
    "Это {word}, и ничего больше.",
    "{word} — важная часть предложения.",
    "Он написал {word} на доске.",
)


def _spelling_base_words(limit: int, seed: int) -> List[str]:
    """Deterministic ordinary-frequency Russian words from pinned accepted resources."""
    counts: Dict[str, int] = {}
    for text, _ in _grammar_example_texts():
        for match in re.finditer(r"[а-яёА-ЯЁ]{5,14}", text):
            word = match.group(0).lower()
            counts[word] = counts.get(word, 0) + 1

    spelling_txt = (
        REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru" / "hunspell" / "spelling.txt"
    )
    if spelling_txt.is_file():
        for line in spelling_txt.read_text(encoding="utf-8").splitlines():
            entry = line.split("#", 1)[0].strip()
            if re.fullmatch(r"[а-яёА-ЯЁ]{5,14}", entry):
                counts.setdefault(entry.lower(), 1)

    # Frequency first, then alphabetical: fully deterministic, prefers ordinary words.
    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ordered[:limit]]


def _misspell(word: str, kind: str, rng: random.Random) -> Optional[str]:
    if kind == "deletion" and len(word) > 4:
        index = rng.randrange(1, len(word))
        return word[:index] + word[index + 1 :]
    if kind == "insertion":
        index = rng.randrange(1, len(word))
        return word[:index] + rng.choice(RUSSIAN_LETTERS) + word[index:]
    if kind == "substitution":
        index = rng.randrange(1, len(word))
        replacement = rng.choice(RUSSIAN_LETTERS)
        if replacement == word[index]:
            return None
        return word[:index] + replacement + word[index + 1 :]
    if kind == "transposition" and len(word) > 4:
        index = rng.randrange(1, len(word) - 1)
        if word[index] == word[index + 1]:
            return None
        return word[:index] + word[index + 1] + word[index] + word[index + 2 :]
    if kind == "case_upper":
        return word.upper()
    if kind == "case_title":
        return word[:1].upper() + word[1:]
    if kind == "case_mixed":
        return "".join(c.upper() if i % 3 == 0 else c for i, c in enumerate(word))
    if kind == "yo_variant":
        if "е" in word:
            index = word.index("е")
            return word[:index] + "ё" + word[index + 1 :]
        if "ё" in word:
            return word.replace("ё", "е", 1)
        return None
    if kind == "hyphen_variant" and len(word) > 5:
        index = rng.randrange(2, len(word) - 1)
        return word[:index] + "-" + word[index:]
    return None


SPELLING_MISSPELL_KINDS = (
    "deletion",
    "insertion",
    "substitution",
    "transposition",
    "case_upper",
    "case_title",
    "case_mixed",
    "yo_variant",
    "hyphen_variant",
)


def build_stratum_c(
    target: int = 2200, seed: int = FIXED_SEED
) -> List[Tuple[str, Dict[str, Any]]]:
    """Controlled misspellings framed as whole-text inputs, at least ``target`` unique."""
    base_words = _spelling_base_words(limit=600, seed=seed)
    results: List[Tuple[str, Dict[str, Any]]] = []
    seen: set[str] = set()

    for round_index in range(len(SPELLING_MISSPELL_KINDS)):
        for word_index, word in enumerate(base_words):
            if len(results) >= target:
                return results
            kind = SPELLING_MISSPELL_KINDS[
                (word_index + round_index) % len(SPELLING_MISSPELL_KINDS)
            ]
            rng = random.Random(f"{seed}:spell:{word}:{kind}")
            wrong = _misspell(word, kind, rng)
            if not wrong or wrong == word:
                continue
            frame = SPELLING_FRAMES[
                (word_index + round_index) % len(SPELLING_FRAMES)
            ]
            text = frame.format(word=wrong)
            if text in seen:
                continue
            seen.add(text)
            results.append(
                (
                    text,
                    {
                        "source": "spelling_stress",
                        "base_word": word,
                        "misspelling_kind": kind,
                        "surface": wrong,
                        "frame_index": (word_index + round_index) % len(SPELLING_FRAMES),
                    },
                )
            )
    return results


# --------------------------------------------------------------------------
# Stratum D - natural Russian development corpus
# --------------------------------------------------------------------------


def build_stratum_d() -> List[Tuple[str, Dict[str, Any]]]:
    """Load the local, git-ignored natural Russian corpus."""
    from tools.fetch_natural_corpus_0014 import load_natural_corpus

    blocks = load_natural_corpus()
    results: List[Tuple[str, Dict[str, Any]]] = []
    for block in blocks:
        text = block["text"]
        if not text.strip():
            continue
        results.append(
            (
                text,
                {
                    "source": "natural_corpus",
                    "source_id": block["source_id"],
                    "page_id": block["page_id"],
                    "block_index": block["block_index"],
                },
            )
        )
    return results


def natural_corpus_metadata() -> Dict[str, Any]:
    if not NATURAL_METADATA_PATH.is_file():
        return {}
    return json.loads(NATURAL_METADATA_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Stratum E - targeted Unicode / offset calibration
# --------------------------------------------------------------------------

UNICODE_BASE_SENTENCES = (
    "Это тестовый текст с ашибкой.",
    "Мама  мыла раму , и папа тоже.",
    "Он сказал , что придёт завтра.",
    "Ошибочный текст текст здесь.",
    "Всё хорошо, что харашо кончается.",
    "Она читала книгу и книгу читала.",
    "Ето неправильное слово.",
    "Привет, как дила у тебя?",
)

UNICODE_DECORATIONS: tuple[tuple[str, Callable[[str], str]], ...] = (
    ("nonbmp_prefix_single", lambda t: EMOJI[0] + " " + t),
    ("nonbmp_prefix_double", lambda t: EMOJI[0] + EMOJI[1] + " " + t),
    ("nonbmp_prefix_quad", lambda t: "".join(EMOJI) + " " + t),
    ("nonbmp_suffix", lambda t: t + " " + EMOJI[2]),
    ("nonbmp_surround", lambda t: EMOJI[3] + " " + t + " " + EMOJI[3]),
    ("nonbmp_infix_word", lambda t: t.replace(" ", " " + EMOJI[1] + " ", 1)),
    ("nonbmp_repeated_infix", lambda t: t.replace(" ", " " + EMOJI[0] + EMOJI[2] + " ")),
    ("bmp_and_nonbmp_mixture", lambda t: "❤ " + EMOJI[0] + " «" + t + "»"),
    ("combining_acute", lambda t: t.replace("а", "а" + COMBINING_ACUTE, 1)),
    ("combining_grave", lambda t: t.replace("о", "о" + COMBINING_GRAVE, 1)),
    ("combining_multiple", lambda t: t.replace("е", "е" + COMBINING_ACUTE).replace("и", "и" + COMBINING_GRAVE)),
    ("soft_hyphen_infix", lambda t: t.replace("а", "а" + SOFT_HYPHEN, 1)),
    ("soft_hyphen_many", lambda t: t.replace("о", "о" + SOFT_HYPHEN)),
    ("nbsp_boundaries", lambda t: t.replace(" ", NBSP, 2)),
    ("zero_width_joiner", lambda t: "\U0001F468‍\U0001F4BB " + t),
    ("nonbmp_math_symbols", lambda t: "\U0001D400\U0001D401 " + t),
    ("supplementary_letter_prefix", lambda t: "\U00010400 " + t),
    ("nonbmp_and_combining", lambda t: EMOJI[1] + " " + t.replace("у", "у" + COMBINING_ACUTE, 1)),
    ("nonbmp_between_sentences", lambda t: t + " " + EMOJI[3] + " " + t),
    ("nonbmp_inside_quotes", lambda t: "«" + EMOJI[0] + t + EMOJI[1] + "»"),
    ("nonbmp_paragraphs", lambda t: EMOJI[2] + "\n\n" + t + "\n\n" + EMOJI[3]),
)


def build_stratum_e() -> List[Tuple[str, Dict[str, Any]]]:
    """Targeted non-BMP, combining-mark and soft-hyphen offset calibration cases."""
    results: List[Tuple[str, Dict[str, Any]]] = []
    for sentence_index, sentence in enumerate(UNICODE_BASE_SENTENCES):
        for kind, decorate in UNICODE_DECORATIONS:
            text = decorate(sentence)
            if not text.strip() or text == sentence:
                continue
            results.append(
                (
                    text,
                    {
                        "source": "unicode_targeted",
                        "unicode_kind": kind,
                        "base_sentence_index": sentence_index,
                        "has_non_bmp": any(ord(c) > 0xFFFF for c in text),
                        "has_combining": any(
                            unicodedata.combining(c) for c in text
                        ),
                        "has_soft_hyphen": SOFT_HYPHEN in text,
                        "has_supplementary_letter": any(
                            ord(c) > 0xFFFF
                            and unicodedata.category(c).startswith("L")
                            for c in text
                        ),
                    },
                )
            )
    return results


# --------------------------------------------------------------------------
# Corpus assembly
# --------------------------------------------------------------------------

#: Which profiles each stratum runs under.  Every stratum runs ``default``; the
#: broader profiles are applied where they add whole-pipeline signal without
#: multiplying the entire corpus.
STRATUM_PROFILES: Dict[str, tuple[str, ...]] = {
    "A": ("default", "all_ordinary_enabled"),
    "B": ("default", "all_ordinary_enabled"),
    "C": ("default", "cfg_speller_yo"),
    "D": ("default",),
    "E": ("default", "all_ordinary_enabled"),
}

#: Bounded targeted non-default configuration evidence over the whole pipeline.
TARGETED_CONFIG_PROFILES: tuple[str, ...] = (
    "cfg_long_sentence_15",
    "cfg_long_paragraph_30",
    "cfg_filler_words_2",
    "cfg_speller_conf_ru_1",
)

CONFIG_CONTROL_WORDS = tuple(
    "Город улица дом окно книга автор читатель школа учитель ученик работа время место "
    "страна человек вопрос ответ пример задача решение история наука музыка театр музей "
    "парк река озеро море гора поле лес дорога поезд самолёт корабль солнце ветер дождь "
    "снег облако птица дерево трава цветок сад берег остров деревня площадь".split()
)

SUPPLEMENTARY_LETTER = "\U00010400"
SUPPLEMENTARY_LONG_SENTENCE_TEXT = (
    SUPPLEMENTARY_LETTER + " " + " ".join(CONFIG_CONTROL_WORDS[:15]) + "."
)

CONFIG_SENSITIVITY_SPECS: Dict[str, Dict[str, Any]] = {
    "cfg_long_sentence_15": {
        "reference_profile": "ref_picky",
        "intended_rule_config_delta": {
            "rule_id": "TOO_LONG_SENTENCE",
            "options": ("maxWords",),
        },
        "texts": (
            *(" ".join(CONFIG_CONTROL_WORDS[:count]) + "." for count in (14, 15, 16, 20)),
            SUPPLEMENTARY_LONG_SENTENCE_TEXT,
        ),
    },
    "cfg_long_paragraph_30": {
        "reference_profile": "ref_long_paragraph_default",
        "intended_rule_config_delta": {
            "rule_id": "TOO_LONG_PARAGRAPH",
            "options": ("maxWords",),
        },
        "texts": tuple(" ".join(CONFIG_CONTROL_WORDS[:count]) + "." for count in (29, 30, 31, 36)),
    },
    "cfg_filler_words_2": {
        "reference_profile": "ref_filler_words_default",
        "intended_rule_config_delta": {
            "rule_id": "FILLER_WORDS_RU",
            "options": ("excludeDirectSpeech", "minPercent"),
        },
        "texts": (
            "ах " + " ".join(["слово"] * 20) + ".",
            "ну " + " ".join(["слово"] * 20) + ".",
            "в общем " + " ".join(["слово"] * 30) + ".",
        ),
    },
    "cfg_speller_conf_ru_1": {
        "reference_profile": "cfg_speller_conf_ru_0",
        "intended_rule_config_delta": {
            "rule_id": "MORFOLOGIK_RULE_RU_RU",
            "options": ("conf_ru_Value",),
        },
        "texts": (
            "The quick brown fox.",
            "wordd написано здесь.",
            "teхt написан смешанными буквами.",
        ),
    },
}

PINNED_ORACLE_REGRESSION_CASES: tuple[Dict[str, Any], ...] = (
    {
        "case_id": "second_review_long_sentence_supplementary_letter",
        "discovered_in_stratum": "A",
        "original_mismatch_kinds": ["UTF16_FIRST_CODE_UNIT_SEMANTICS"],
        "minimized_text": SUPPLEMENTARY_LONG_SENTENCE_TEXT,
        "profile": "cfg_long_sentence_15",
        "upstream_proof": (
            "pinned LongSentenceRule.isWordCount uses substring(0,1), so U+10400 "
            "contributes an unpaired surrogate rather than a Unicode letter"
        ),
    },
)


def validate_config_sensitivity_profiles(
    profiles: Mapping[str, Profile] | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Fail closed unless every pair differs only in its declared rule option."""
    declared_profiles = dict(build_profiles() if profiles is None else profiles)
    proof: Dict[str, Dict[str, Any]] = {}
    missing = object()
    for target_id, spec in sorted(CONFIG_SENSITIVITY_SPECS.items()):
        reference_id = spec["reference_profile"]
        if target_id not in declared_profiles or reference_id not in declared_profiles:
            raise ValueError(
                f"Unknown config-sensitivity profile pair: {target_id}/{reference_id}"
            )
        delta = spec.get("intended_rule_config_delta")
        if (
            not isinstance(delta, Mapping)
            or not delta.get("rule_id")
            or not delta.get("options")
        ):
            raise ValueError(f"Missing intended rule_config delta for {target_id}")

        target = declared_profiles[target_id]
        reference = declared_profiles[reference_id]
        dimensions = (
            "enabled_rules",
            "disabled_rules",
            "level",
            "enable_all_default_off",
        )
        changed_dimensions = [
            name
            for name in dimensions
            if getattr(target, name) != getattr(reference, name)
        ]
        if changed_dimensions:
            raise ValueError(
                f"Unrelated profile dimensions differ for {target_id}: "
                f"{changed_dimensions}"
            )

        rule_id = str(delta["rule_id"])
        options = tuple(str(option) for option in delta["options"])
        if not options or len(options) != len(set(options)):
            raise ValueError(f"Invalid intended options for {target_id}: {options}")
        target_config = {
            key: dict(value) for key, value in target.rule_config.items()
        }
        reference_config = {
            key: dict(value) for key, value in reference.rule_config.items()
        }
        all_rules = set(target_config) | set(reference_config)
        unrelated_rules = sorted(
            key
            for key in all_rules
            if key != rule_id
            and target_config.get(key, {}) != reference_config.get(key, {})
        )
        if unrelated_rules:
            raise ValueError(
                f"Unrelated rule_config differs for {target_id}: {unrelated_rules}"
            )

        target_rule = target_config.get(rule_id, {})
        reference_rule = reference_config.get(rule_id, {})
        changed_options = {
            option
            for option in set(target_rule) | set(reference_rule)
            if target_rule.get(option, missing) != reference_rule.get(option, missing)
        }
        if changed_options != set(options):
            raise ValueError(
                f"Declared/actual option delta differs for {target_id}: "
                f"declared={sorted(options)}, actual={sorted(changed_options)}"
            )
        proof[target_id] = {
            "reference_profile": reference_id,
            "rule_id": rule_id,
            "options": list(options),
            "unrelated_profile_dimensions_equal": True,
            "only_intended_rule_config_differs": True,
        }
    return proof


def build_corpus(seed: int = FIXED_SEED) -> Tuple[List[CorpusCase], Dict[str, Any]]:
    """Build the complete deterministic corpus and its accounting."""
    profiles = build_profiles()
    validate_config_sensitivity_profiles(profiles)

    stratum_texts: Dict[str, List[Tuple[str, Dict[str, Any]]]] = {}
    stratum_texts["A"] = build_stratum_a()
    stratum_texts["B"] = build_stratum_b(stratum_texts["A"], seed=seed)
    stratum_texts["C"] = build_stratum_c(seed=seed)
    stratum_texts["D"] = build_stratum_d()
    stratum_texts["E"] = build_stratum_e()

    cases: List[CorpusCase] = []
    seen_identity: set[str] = set()
    duplicates = 0
    index_by_stratum: Dict[str, int] = {stratum: 0 for stratum in STRATA}

    def emit(
        stratum: str,
        text: str,
        provenance: Mapping[str, Any],
        profile: Profile,
    ) -> None:
        nonlocal duplicates
        identity = semantic_identity(text, profile)
        if identity in seen_identity:
            duplicates += 1
            return
        seen_identity.add(identity)
        case_index = index_by_stratum[stratum]
        index_by_stratum[stratum] += 1
        cases.append(
            CorpusCase(
                case_id=make_case_id(stratum, case_index, identity),
                source_stratum=stratum,
                text=text,
                profile=profile.profile_id,
                provenance=dict(provenance),
                mutation_kind=provenance.get("mutation_kind"),
                mutation_parent_id=provenance.get("seed_text_sha256"),
                seed=seed if stratum in ("B", "C") else None,
            )
        )

    for stratum in STRATA:
        for profile_id in STRATUM_PROFILES[stratum]:
            profile = profiles[profile_id]
            for text, provenance in stratum_texts[stratum]:
                emit(stratum, text, provenance, profile)

    # Controlled boundary/effect cases are executed under a target and a reference
    # profile that differs only in the option being proved.  This makes a zero-effect
    # configuration a validation failure instead of vacuous parity evidence.
    for profile_id in TARGETED_CONFIG_PROFILES:
        spec = CONFIG_SENSITIVITY_SPECS[profile_id]
        for text in spec["texts"]:
            provenance = {
                "source": "config_sensitivity",
                "target_profile": profile_id,
                "reference_profile": spec["reference_profile"],
            }
            emit("A", text, provenance, profiles[spec["reference_profile"]])
            emit("A", text, provenance, profiles[profile_id])

    unique_texts = {case.text for case in cases}
    accounting = {
        "cases_total": len(cases),
        "unique_texts_total": len(unique_texts),
        "semantic_duplicates_skipped": duplicates,
        "cases_by_stratum": {
            stratum: sum(1 for case in cases if case.source_stratum == stratum)
            for stratum in STRATA
        },
        "unique_texts_by_stratum": {
            stratum: len(
                {case.text for case in cases if case.source_stratum == stratum}
            )
            for stratum in STRATA
        },
        "cases_by_profile": {
            profile_id: sum(1 for case in cases if case.profile == profile_id)
            for profile_id in sorted(profiles)
        },
        "source_texts_by_stratum": {
            stratum: len(stratum_texts[stratum]) for stratum in STRATA
        },
        "non_bmp_executions": sum(
            1 for case in cases if any(ord(c) > 0xFFFF for c in case.text)
        ),
        "supplementary_letter_executions": sum(
            1
            for case in cases
            if any(
                ord(c) > 0xFFFF and unicodedata.category(c).startswith("L")
                for c in case.text
            )
        ),
        "combining_mark_executions": sum(
            1
            for case in cases
            if any(unicodedata.combining(c) for c in case.text)
        ),
        "soft_hyphen_executions": sum(
            1 for case in cases if SOFT_HYPHEN in case.text
        ),
    }
    return cases, accounting


def _stratum_index(
    stratum_texts: Mapping[str, List[Tuple[str, Dict[str, Any]]]]
) -> Dict[str, str]:
    """Map each source text to the first stratum that produced it."""
    index: Dict[str, str] = {}
    for stratum in STRATA:
        for text, _ in stratum_texts[stratum]:
            index.setdefault(text, stratum)
    return index


def corpus_signature(cases: Sequence[CorpusCase]) -> str:
    """Semantic signature of the corpus: identity, order, text hash and profile."""
    digest = hashlib.sha256()
    for case in cases:
        digest.update(case.case_id.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(case.source_stratum.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(case.profile.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(hashlib.sha256(case.text.encode("utf-8")).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def stratum_signature(cases: Sequence[CorpusCase], stratum: str) -> str:
    return corpus_signature([case for case in cases if case.source_stratum == stratum])


def internal_stratum_signature(cases: Sequence[CorpusCase], stratum: str) -> str:
    """Signature of one stratum's own cases, excluding the targeted-config additions.

    The targeted-config sample is drawn from a pool that contains the external natural
    corpus, so it cannot be regenerated without that corpus.  Excluding it leaves a
    signature that any checkout can reproduce from committed inputs alone, which is what
    the Java-free regeneration test compares.
    """
    return corpus_signature(
        [
            case
            for case in cases
            if case.source_stratum == stratum
            and case.provenance.get("source") != "config_sensitivity"
        ]
    )


def write_corpus(cases: Sequence[CorpusCase]) -> Path:
    CORPORA_DIR.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w", encoding="utf-8", newline="\n") as handle:
        for case in cases:
            handle.write(json.dumps(case.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
    return CORPUS_PATH


def read_corpus() -> List[CorpusCase]:
    if not CORPUS_PATH.is_file():
        raise FileNotFoundError(
            f"{CORPUS_PATH} not found. Run: python -m tools.differential_corpus_0014 build"
        )
    cases: List[CorpusCase] = []
    for line in CORPUS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        cases.append(
            CorpusCase(
                case_id=payload["case_id"],
                source_stratum=payload["source_stratum"],
                text=payload["text"],
                profile=payload["profile"],
                provenance=payload.get("provenance", {}),
                mutation_parent_id=payload.get("mutation_parent_id"),
                mutation_kind=payload.get("mutation_kind"),
                seed=payload.get("seed"),
                external_source_hash=payload.get("external_source_hash"),
            )
        )
    return cases


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


def _source_hashes() -> Dict[str, str]:
    paths = [GRAMMAR_EXAMPLES_PATH, JAVA_RULES_INVENTORY_PATH] + [
        REPO_ROOT / relative for relative, _ in STRATUM_A_FIXTURES
    ]
    return {
        str(path.relative_to(REPO_ROOT)).replace("\\", "/"): sha256_file(path)
        for path in sorted(paths)
    }


def build_manifest(cases: Sequence[CorpusCase], accounting: Mapping[str, Any]) -> Dict[str, Any]:
    manifest_data = validate_oracle_manifest(
        REPO_ROOT / "compat" / "oracle_manifest.json"
    )
    profiles = build_profiles()
    config_structure = validate_config_sensitivity_profiles(profiles)
    natural = natural_corpus_metadata()

    return {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "pinned_lt_version": PINNED_LT_VERSION,
        "pinned_lt_commit": PINNED_LT_COMMIT,
        "oracle_build_id": manifest_data["default_build_id"],
        "oracle_jar_sha256": manifest_data["oracle_sha256"],
        "generator_version": GENERATOR_VERSION,
        "fixed_seed": FIXED_SEED,
        "source_inventory": _source_hashes(),
        "mutation_families": list(MUTATION_FAMILY_NAMES),
        "mutation_kinds": list(MUTATION_KINDS),
        "spelling_misspell_kinds": list(SPELLING_MISSPELL_KINDS),
        "unicode_kinds": [kind for kind, _ in UNICODE_DECORATIONS],
        "default_off_rule_ids": default_off_rule_ids(),
        "language_model_rule": {
            "rule_id": LANGUAGE_MODEL_RULE_ID,
            "rule_class": "RussianConfusionProbabilityRule",
            "status": "LANGUAGE_MODEL_DEFERRED",
            "excluded_from_java_surface": True,
        },
        "profiles": {
            profile_id: profiles[profile_id].to_dict() for profile_id in sorted(profiles)
        },
        "profile_signatures": {
            profile_id: profiles[profile_id].signature() for profile_id in sorted(profiles)
        },
        "stratum_names": dict(STRATUM_NAMES),
        "stratum_profiles": {k: list(v) for k, v in sorted(STRATUM_PROFILES.items())},
        "targeted_config_profiles": list(TARGETED_CONFIG_PROFILES),
        "config_sensitivity_specs": {
            profile_id: {
                "reference_profile": spec["reference_profile"],
                "intended_rule_config_delta": {
                    "rule_id": spec["intended_rule_config_delta"]["rule_id"],
                    "options": list(
                        spec["intended_rule_config_delta"]["options"]
                    ),
                },
                "text_sha256": [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in spec["texts"]],
            }
            for profile_id, spec in sorted(CONFIG_SENSITIVITY_SPECS.items())
        },
        "config_sensitivity_structure": config_structure,
        "counts": dict(accounting),
        "corpus_signature": corpus_signature(cases),
        "stratum_signatures": {
            stratum: stratum_signature(cases, stratum) for stratum in STRATA
        },
        "internal_stratum_signatures": {
            stratum: internal_stratum_signature(cases, stratum)
            for stratum in ("A", "B", "C", "E")
        },
        "internal_strata": ["A", "B", "C", "E"],
        "external_strata": ["D"],
        "external_corpus": natural,
        "corpus_file": {
            "path": str(CORPUS_PATH.relative_to(REPO_ROOT)).replace("\\", "/"),
            "committed": False,
            "reason": "contains external natural-corpus text; never committed",
        },
    }


def write_manifest(manifest: Mapping[str, Any]) -> Path:
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return MANIFEST_PATH


# --------------------------------------------------------------------------
# Campaign runner
# --------------------------------------------------------------------------


@dataclass
class CaseResult:
    """Outcome of one differential execution."""

    case_id: str
    source_stratum: str
    profile: str
    text_sha256: str
    is_exact: bool
    java_finding_count: int
    pylat_finding_count: int
    java_rule_ids: List[str]
    pylat_rule_ids: List[str]
    mismatch_kinds: List[str]
    mismatches: List[Dict[str, Any]]
    java_findings_with_suggestions: int = 0
    java_error: Optional[str] = None
    python_error: Optional[str] = None
    utf16_self_consistent: bool = True
    java_comparable: List[List[Any]] = field(default_factory=list)
    pylat_comparable: List[List[Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _check_utf16_consistency(text: str, matches: Sequence[Any]) -> bool:
    """Prove Python's own code-point and UTF-16 spans agree for every match."""
    prefix_utf16: List[int] = [0]
    total = 0
    for character in text:
        total += 2 if ord(character) > 0xFFFF else 1
        prefix_utf16.append(total)
    for match in matches:
        start = match.offset
        end = match.offset + match.length
        if start < 0 or end > len(text):
            return False
        if match.utf16_offset != prefix_utf16[start]:
            return False
        if match.utf16_length != prefix_utf16[end] - prefix_utf16[start]:
            return False
    return True


def run_campaign(
    cases: Sequence[CorpusCase],
    output_path: Path,
    resume: bool = False,
    progress_every: int = 250,
) -> List[CaseResult]:
    """Run every case against one long-lived Java oracle and one Python tool per profile."""
    profiles = build_profiles()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    done: set[str] = set()
    if resume and output_path.is_file():
        for line in output_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["case_id"])

    pending = [case for case in cases if case.case_id not in done]
    results: List[CaseResult] = []

    needed_profiles = sorted({case.profile for case in pending})
    python_tools = {profile_id: python_tool(profiles[profile_id]) for profile_id in needed_profiles}

    mode = "a" if (resume and output_path.is_file()) else "w"
    with BatchJavaOracle() as oracle, output_path.open(
        mode, encoding="utf-8", newline="\n"
    ) as handle:
        for profile_id in needed_profiles:
            oracle.define_profile(profiles[profile_id])

        for index, case in enumerate(pending, 1):
            result = _run_single(
                oracle, python_tools[case.profile], profiles[case.profile], case
            )
            results.append(result)
            handle.write(json.dumps(result.to_dict(), ensure_ascii=False) + "\n")
            if progress_every and index % progress_every == 0:
                exact = sum(1 for r in results if r.is_exact)
                print(
                    f"  {index}/{len(pending)} cases, {exact} exact",
                    file=sys.stderr,
                    flush=True,
                )
    return results


def _run_single(
    oracle: BatchJavaOracle, tool: Any, profile: Profile, case: CorpusCase
) -> CaseResult:
    text_sha = hashlib.sha256(case.text.encode("utf-8")).hexdigest()
    java_error: Optional[str] = None
    python_error: Optional[str] = None
    java: List[Finding] = []
    pylat: List[Finding] = []
    utf16_ok = True

    try:
        java = oracle.check(case.case_id, case.profile, case.text)
    except Exception as error:  # noqa: BLE001 - recorded, never swallowed
        java_error = f"{type(error).__name__}: {error}"

    try:
        matches = tool.check(case.text, level=profile.level)
        utf16_ok = _check_utf16_consistency(case.text, matches)
        pylat = pylat_findings(matches)
    except Exception as error:  # noqa: BLE001 - recorded, never swallowed
        python_error = f"{type(error).__name__}: {error}"

    if java_error or python_error:
        kinds = []
        if java_error:
            kinds.append("JAVA_ORACLE_ERROR")
        if python_error:
            kinds.append("PYTHON_ERROR")
        return CaseResult(
            case_id=case.case_id,
            source_stratum=case.source_stratum,
            profile=case.profile,
            text_sha256=text_sha,
            is_exact=False,
            java_finding_count=len(java),
            pylat_finding_count=len(pylat),
            java_rule_ids=[f.rule_id for f in java],
            pylat_rule_ids=[f.rule_id for f in pylat],
            mismatch_kinds=kinds,
            mismatches=[],
            java_findings_with_suggestions=sum(1 for f in java if f.suggestions),
            java_error=java_error,
            python_error=python_error,
            utf16_self_consistent=utf16_ok,
            java_comparable=[f.comparable_json() for f in java],
            pylat_comparable=[f.comparable_json() for f in pylat],
        )

    comparison = compare_findings(case.text, java, pylat)
    return CaseResult(
        case_id=case.case_id,
        source_stratum=case.source_stratum,
        profile=case.profile,
        text_sha256=text_sha,
        is_exact=comparison.is_exact_match and utf16_ok,
        java_finding_count=len(java),
        pylat_finding_count=len(pylat),
        java_rule_ids=[f.rule_id for f in java],
        pylat_rule_ids=[f.rule_id for f in pylat],
        mismatch_kinds=comparison.mismatch_kinds
        + ([] if utf16_ok else ["PYTHON_ERROR"]),
        mismatches=[m.to_dict() for m in comparison.mismatches],
        java_findings_with_suggestions=sum(1 for f in java if f.suggestions),
        utf16_self_consistent=utf16_ok,
        java_comparable=[f.comparable_json() for f in java],
        pylat_comparable=[f.comparable_json() for f in pylat],
    )


def read_results(path: Path) -> List[CaseResult]:
    results: List[CaseResult] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        results.append(CaseResult(**payload))
    return results


def results_path() -> Path:
    return RESULTS_DIR / "campaign.jsonl"


# --------------------------------------------------------------------------
# Mismatch fingerprints and allowlist
# --------------------------------------------------------------------------


def mismatch_fingerprint(result: CaseResult) -> str:
    """Stable fingerprint grouping mismatches that share a root cause."""
    rule_ids = sorted(
        {m.get("rule_id", "") for m in result.mismatches if m.get("rule_id")}
    )
    payload = json.dumps(
        {
            "kinds": sorted(set(result.mismatch_kinds)),
            "rule_ids": rule_ids,
            "profile": result.profile,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def load_upstream_defects() -> List[Dict[str, Any]]:
    """Committed record of pinned-upstream defects the campaign ran into.

    These are inputs on which the pinned Java pipeline raises instead of returning a
    result, so no parity comparison is possible for them at all.  Each entry names the
    exception signature, the pinned source that produces it, and how ``pylat_ru``
    behaves instead.
    """
    if not UPSTREAM_DEFECTS_PATH.is_file():
        return []
    payload = json.loads(UPSTREAM_DEFECTS_PATH.read_text(encoding="utf-8"))
    return payload.get("defects", [])


def classify_java_error(message: str, defects: Sequence[Mapping[str, Any]]) -> Optional[str]:
    """Return the id of the recorded upstream defect explaining ``message``."""
    for defect in defects:
        if defect["exception_signature"] in message:
            return defect["defect_id"]
    return None


def load_allowlist() -> List[Dict[str, Any]]:
    """Narrow, machine-readable ordinary-difference classifications (normally empty)."""
    if not ALLOWLIST_PATH.is_file():
        return []
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    return payload.get("entries", [])


def is_allowlisted(result: CaseResult, entries: Sequence[Mapping[str, Any]]) -> bool:
    for entry in entries:
        if entry.get("case_id") and entry["case_id"] != result.case_id:
            continue
        if entry.get("fingerprint") and entry["fingerprint"] != mismatch_fingerprint(result):
            continue
        if entry.get("fields"):
            if not set(result.mismatch_kinds).issubset(set(entry["fields"])):
                continue
        return True
    return False


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------


def _rate(numerator: int, denominator: int) -> Dict[str, Any]:
    """Integer-derived rate that never pretends an empty denominator is perfect."""
    if denominator == 0:
        return {
            "numerator": numerator,
            "denominator": 0,
            "rate": None,
            "state": "NO_OBSERVATIONS",
        }
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": numerator / denominator,
        "state": "MEASURED",
    }


def build_summary(
    cases: Sequence[CorpusCase],
    results: Sequence[CaseResult],
    manifest: Mapping[str, Any],
    git_sha: str,
) -> Dict[str, Any]:
    """Derive every campaign metric from integer counts."""
    from collections import Counter

    allowlist = load_allowlist()
    upstream_defects = load_upstream_defects()
    config_structure = validate_config_sensitivity_profiles(build_profiles())
    by_case = {case.case_id: case for case in cases}

    exact = sum(1 for r in results if r.is_exact)
    non_exact = [r for r in results if not r.is_exact]
    java_error_results = [r for r in results if r.java_error]
    python_errors = sum(1 for r in results if r.python_error)

    explained_java_errors = [
        r
        for r in java_error_results
        if classify_java_error(r.java_error or "", upstream_defects)
    ]
    unexplained_java_errors = [
        r for r in java_error_results if r not in explained_java_errors
    ]
    java_error_ids = {r.case_id for r in java_error_results}

    # A case the pinned oracle could not answer at all is not a compatibility
    # discrepancy: there is no Java result to be compatible with.  It is counted and
    # named separately instead, and must be covered by a committed upstream-defect
    # record to be considered explained.
    unexplained = [
        r
        for r in non_exact
        if r.case_id not in java_error_ids and not is_allowlisted(r, allowlist)
    ]
    accepted = len(non_exact) - len(unexplained) - len(java_error_results)
    java_errors = len(java_error_results)

    java_findings_total = sum(r.java_finding_count for r in results)
    pylat_findings_total = sum(r.pylat_finding_count for r in results)

    kind_counter: Counter[str] = Counter()
    rule_mismatch_counter: Counter[str] = Counter()
    for result in non_exact:
        for kind in result.mismatch_kinds:
            kind_counter[kind] += 1
        for mismatch in result.mismatches:
            if mismatch.get("rule_id"):
                rule_mismatch_counter[mismatch["rule_id"]] += 1

    # Field-level parity is measured per case: a case counts towards a field's
    # parity when that field never differed anywhere in the case.
    comparable = [r for r in results if r.case_id not in java_error_ids]

    def field_parity(kinds: Sequence[str]) -> Dict[str, Any]:
        """Parity over the cases the pinned oracle actually answered."""
        offending = sum(
            1 for r in comparable if any(kind in r.mismatch_kinds for kind in kinds)
        )
        return _rate(len(comparable) - offending, len(comparable))

    java_rule_counter: Counter[str] = Counter()
    pylat_rule_counter: Counter[str] = Counter()
    exact_rule_counter: Counter[str] = Counter()
    for result in results:
        java_rule_counter.update(result.java_rule_ids)
        pylat_rule_counter.update(result.pylat_rule_ids)
        if result.is_exact:
            exact_rule_counter.update(result.java_rule_ids)

    by_rule = {
        rule_id: {
            "java_occurrences": java_rule_counter[rule_id],
            "pylat_occurrences": pylat_rule_counter[rule_id],
            "exact_case_occurrences": exact_rule_counter[rule_id],
            "mismatch_count": rule_mismatch_counter.get(rule_id, 0),
        }
        for rule_id in sorted(set(java_rule_counter) | set(pylat_rule_counter))
    }

    def stratum_block(stratum: str) -> Dict[str, Any]:
        subset = [r for r in results if r.source_stratum == stratum]
        subset_non_exact = [r for r in subset if not r.is_exact]
        stratum_kinds: Counter[str] = Counter()
        for result in subset_non_exact:
            stratum_kinds.update(result.mismatch_kinds)
        return {
            "cases": len(subset),
            "unique_texts": len(
                {by_case[r.case_id].text for r in subset if r.case_id in by_case}
            ),
            "exact": sum(1 for r in subset if r.is_exact),
            "non_exact": len(subset_non_exact),
            "java_findings": sum(r.java_finding_count for r in subset),
            "pylat_findings": sum(r.pylat_finding_count for r in subset),
            "mismatch_counts_by_kind": dict(sorted(stratum_kinds.items())),
        }

    def profile_block(profile_id: str) -> Dict[str, Any]:
        subset = [r for r in results if r.profile == profile_id]
        subset_non_exact = [r for r in subset if not r.is_exact]
        profile_kinds: Counter[str] = Counter()
        for result in subset_non_exact:
            profile_kinds.update(result.mismatch_kinds)
        return {
            "cases": len(subset),
            "exact": sum(1 for r in subset if r.is_exact),
            "non_exact": len(subset_non_exact),
            "java_findings": sum(r.java_finding_count for r in subset),
            "pylat_findings": sum(r.pylat_finding_count for r in subset),
            "mismatch_counts_by_kind": dict(sorted(profile_kinds.items())),
        }

    non_bmp = [r for r in results if any(ord(c) > 0xFFFF for c in by_case[r.case_id].text)]
    supplementary_letter = [
        r
        for r in results
        if any(
            ord(c) > 0xFFFF and unicodedata.category(c).startswith("L")
            for c in by_case[r.case_id].text
        )
    ]
    supplementary_letter_comparable = [
        r for r in supplementary_letter if not r.java_error
    ]
    combining = [
        r
        for r in results
        if any(unicodedata.combining(c) for c in by_case[r.case_id].text)
    ]
    soft_hyphen = [r for r in results if SOFT_HYPHEN in by_case[r.case_id].text]

    suggestion_stats = _suggestion_statistics(
        results, {r.case_id: r.java_findings_with_suggestions for r in results}
    )

    unique_texts = {case.text for case in cases}
    input_manifest_payload = json.dumps(manifest, ensure_ascii=False, sort_keys=True)

    result_by_profile_text = {
        (result.profile, result.text_sha256): result for result in results
    }
    config_sensitivity: Dict[str, Dict[str, Any]] = {}
    for profile_id, spec in sorted(CONFIG_SENSITIVITY_SPECS.items()):
        reference_profile = spec["reference_profile"]
        pairs: List[Tuple[CaseResult, CaseResult]] = []
        for text in spec["texts"]:
            text_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
            target = result_by_profile_text.get((profile_id, text_sha))
            reference = result_by_profile_text.get((reference_profile, text_sha))
            if target is not None and reference is not None:
                pairs.append((target, reference))
        java_deltas = [pair for pair in pairs if pair[0].java_comparable != pair[1].java_comparable]
        python_deltas = [pair for pair in pairs if pair[0].pylat_comparable != pair[1].pylat_comparable]
        delta_rule_ids = sorted(
            {
                finding[0]
                for target, reference in java_deltas
                for sequence in (target.java_comparable, reference.java_comparable)
                for finding in sequence
                if finding
            }
        )
        block = {
            "profile_id": profile_id,
            "reference_profile": reference_profile,
            "targeted_cases": len(pairs),
            "java_cases_with_observable_delta": len(java_deltas),
            "python_cases_with_same_observable_delta": len(python_deltas),
            "java_python_exact_cases": sum(1 for target, _ in pairs if target.is_exact),
            "delta_rule_ids": delta_rule_ids,
            "structural_proof": config_structure[profile_id],
        }
        config_sensitivity[profile_id] = block
        if (
            block["targeted_cases"] == 0
            or block["java_cases_with_observable_delta"] == 0
            or block["python_cases_with_same_observable_delta"] == 0
            or block["java_python_exact_cases"] != block["targeted_cases"]
        ):
            raise RuntimeError(
                f"Config sensitivity validation failed closed for {profile_id}: {block}"
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "campaign_identity": {
            "generator_version": GENERATOR_VERSION,
            "fixed_seed": FIXED_SEED,
            "corpus_signature": manifest["corpus_signature"],
            "stratum_signatures": manifest["stratum_signatures"],
        },
        "input_manifest_sha256": hashlib.sha256(
            input_manifest_payload.encode("utf-8")
        ).hexdigest(),
        "oracle": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "build_id": manifest["oracle_build_id"],
            "jar_sha256": manifest["oracle_jar_sha256"],
        },
        "repository_sha": git_sha,
        "totals": {
            "cases_total": len(results),
            "comparable_cases": len(comparable),
            "unique_texts_total": len(unique_texts),
            "profile_executions_total": len(results),
            "exact_cases": exact,
            "non_exact_cases": len(non_exact),
            "java_errors": java_errors,
            "python_errors": python_errors,
            "java_findings_total": java_findings_total,
            "pylat_findings_total": pylat_findings_total,
            # Restricted to the cases the pinned oracle answered.  The unrestricted
            # totals differ by the findings pylat_ru returned for inputs on which
            # pinned LanguageTool raised and produced nothing at all.
            "java_findings_comparable": sum(
                r.java_finding_count for r in comparable
            ),
            "pylat_findings_comparable": sum(
                r.pylat_finding_count for r in comparable
            ),
        },
        "parity": {
            "finding_sequence_exact": _rate(exact, len(comparable)),
            "rule_id": field_parity(
                ["RULE_ID_MISMATCH", "MISSING_FINDING", "EXTRA_FINDING"]
            ),
            "full_rule_id": field_parity(["FULL_RULE_ID_MISMATCH"]),
            "category": field_parity(["CATEGORY_MISMATCH"]),
            "category_name": field_parity(["CATEGORY_NAME_MISMATCH"]),
            "span": field_parity(["SPAN_MISMATCH"]),
            "message": field_parity(["MESSAGE_MISMATCH"]),
            "short_message": field_parity(["SHORT_MESSAGE_MISMATCH"]),
            "suggestion_content": field_parity(["SUGGESTION_CONTENT_MISMATCH"]),
            "suggestion_order": field_parity(["SUGGESTION_ORDER_MISMATCH"]),
            "finding_order": field_parity(["FINDING_ORDER_MISMATCH"]),
            "url": field_parity(["URL_MISMATCH"]),
            "full_observable_field": _rate(exact, len(comparable)),
        },
        "config_sensitivity": config_sensitivity,
        "counts_by_stratum": {stratum: stratum_block(stratum) for stratum in STRATA},
        "counts_by_profile": {
            profile_id: profile_block(profile_id)
            for profile_id in sorted(manifest["profiles"])
        },
        "mismatch_counts_by_kind": dict(sorted(kind_counter.items())),
        "mismatch_counts_by_rule_id": dict(sorted(rule_mismatch_counter.items())),
        "by_rule_id": by_rule,
        "unicode_coverage": {
            "non_bmp_cases": len(non_bmp),
            "non_bmp_exact": sum(1 for r in non_bmp if r.is_exact),
            "supplementary_letter_cases": len(supplementary_letter),
            "supplementary_letter_comparable_cases": len(
                supplementary_letter_comparable
            ),
            "supplementary_letter_exact": sum(
                1 for r in supplementary_letter_comparable if r.is_exact
            ),
            "combining_mark_cases": len(combining),
            "combining_mark_exact": sum(1 for r in combining if r.is_exact),
            "soft_hyphen_cases": len(soft_hyphen),
            "soft_hyphen_exact": sum(1 for r in soft_hyphen if r.is_exact),
            "utf16_parity_failures": sum(
                1 for r in results if not r.utf16_self_consistent
            ),
        },
        "suggestions": suggestion_stats,
        "known_accepted_discrepancies": accepted,
        "upstream_defects": {
            "java_error_cases": java_errors,
            "explained": len(explained_java_errors),
            "unexplained": len(unexplained_java_errors),
            "record": str(UPSTREAM_DEFECTS_PATH.relative_to(REPO_ROOT)).replace(
                "\\", "/"
            ),
            "by_defect_id": {
                defect_id: sum(
                    1
                    for r in java_error_results
                    if classify_java_error(r.java_error or "", upstream_defects)
                    == defect_id
                )
                for defect_id in sorted(
                    {d["defect_id"] for d in upstream_defects}
                )
            },
            "unexplained_case_ids": sorted(r.case_id for r in unexplained_java_errors)[:50],
        },
        "unexplained_discrepancies": len(unexplained),
        "ordinary_allowlist_entries": len(allowlist),
        "unexplained_case_ids": sorted(r.case_id for r in unexplained)[:200],
        "language_model_rule": manifest["language_model_rule"],
        "external_corpus": manifest.get("external_corpus", {}),
    }


def _suggestion_statistics(
    results: Sequence[CaseResult], suggestion_counts: Mapping[str, int]
) -> Dict[str, Any]:
    """Suggestion-specific accounting.

    ``suggestion_counts`` carries the per-case number of Java findings that offered at
    least one replacement, recorded during the run.  Everything else is derived from
    the mismatch records, where an exactly matching case contributes zero by
    construction: its ordered suggestion lists were equal element for element.
    """
    content = 0
    order = 0
    duplicate = 0
    for result in results:
        for mismatch in result.mismatches:
            kind = mismatch.get("kind")
            if kind == "SUGGESTION_ORDER_MISMATCH":
                order += 1
            elif kind == "SUGGESTION_CONTENT_MISMATCH":
                content += 1
                java_value = mismatch.get("java_value") or []
                pylat_value = mismatch.get("pylat_value") or []
                # Same distinct members, different multiplicity: a duplicate-preservation
                # defect rather than a genuinely different suggestion list.
                if sorted(set(java_value)) == sorted(set(pylat_value)):
                    duplicate += 1

    findings_with_suggestions = sum(
        suggestion_counts.get(result.case_id, 0) for result in results
    )
    mismatched = content + order
    return {
        "java_findings_with_suggestions": findings_with_suggestions,
        "exact_ordered_suggestion_matches": findings_with_suggestions - mismatched,
        "suggestion_content_mismatches": content,
        "suggestion_order_only_mismatches": order,
        "duplicate_preservation_mismatches": duplicate,
    }


def write_summary(summary: Mapping[str, Any]) -> Path:
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return SUMMARY_PATH


# --------------------------------------------------------------------------
# UTF-16 offset calibration fixture
# --------------------------------------------------------------------------


def utf16_prefix_table(text: str) -> List[int]:
    """Cumulative UTF-16 code-unit length before each code-point index."""
    table = [0]
    total = 0
    for character in text:
        total += 2 if ord(character) > 0xFFFF else 1
        table.append(total)
    return table


def generate_utf16_calibration() -> Dict[str, Any]:
    """Record exactly how the pinned Java oracle serialises positions for non-BMP text.

    The committed fixture makes the offset-domain proof reproducible without a JVM:
    ordinary pytest asserts Python's UTF-16 spans equal the recorded Java spans and
    that Python's own code-point span converts to the same UTF-16 span.
    """
    manifest_data = validate_oracle_manifest(REPO_ROOT / "compat" / "oracle_manifest.json")
    profiles = build_profiles()
    profile = profiles["default"]
    tool = python_tool(profile)

    cases: List[Dict[str, Any]] = []
    with BatchJavaOracle() as oracle:
        oracle.define_profile(profile)
        for index, (text, provenance) in enumerate(build_stratum_e()):
            java = oracle.check(f"utf16_{index:04d}", profile.profile_id, text)
            matches = tool.check(text, level=profile.level)
            prefix = utf16_prefix_table(text)
            cases.append(
                {
                    "case_id": f"utf16_{index:04d}",
                    "unicode_kind": provenance["unicode_kind"],
                    "text": text,
                    "text_code_point_length": len(text),
                    "text_utf16_length": prefix[-1],
                    "has_non_bmp": provenance["has_non_bmp"],
                    "has_combining": provenance["has_combining"],
                    "has_soft_hyphen": provenance["has_soft_hyphen"],
                    "has_supplementary_letter": provenance[
                        "has_supplementary_letter"
                    ],
                    "java_findings": [f.comparable_json() for f in java],
                    "python_code_point_spans": [
                        [m.offset, m.length] for m in matches
                    ],
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": manifest_data["default_build_id"],
            "oracle_jar_sha256": manifest_data["oracle_sha256"],
            "profile": profile.to_dict(),
            "position_domain": "UTF-16 code units, as produced by java.lang.String indexing",
            "finding_field_order": [
                "rule_id",
                "full_rule_id",
                "category_id",
                "category_name",
                "message",
                "short_message",
                "utf16_offset",
                "utf16_length",
                "suggestions",
                "url",
            ],
        },
        "cases": cases,
    }


# --------------------------------------------------------------------------
# Minimizer
# --------------------------------------------------------------------------


def _fingerprint_of(text: str, profile: Profile, oracle: BatchJavaOracle, tool: Any) -> Optional[str]:
    """Fingerprint of the discrepancy a candidate text produces, or None if it is exact."""
    try:
        java = oracle.check("minimize", profile.profile_id, text)
    except Exception:  # noqa: BLE001
        return "JAVA_ORACLE_ERROR"
    try:
        matches = tool.check(text, level=profile.level)
        pylat = pylat_findings(matches)
    except Exception:  # noqa: BLE001
        return "PYTHON_ERROR"
    comparison = compare_findings(text, java, pylat)
    if comparison.is_exact_match:
        return None
    rule_ids = sorted({m.rule_id for m in comparison.mismatches if m.rule_id})
    payload = json.dumps(
        {
            "kinds": comparison.mismatch_kinds,
            "rule_ids": rule_ids,
            "profile": profile.profile_id,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


#: Candidate evaluations one minimisation may spend.  Delta debugging over a long
#: natural-prose block is quadratic in the number of words, so the budget keeps a single
#: pathological case from starving the rest.  Exhausting it stops the search and keeps
#: the smallest text found so far, which is still a valid reproducer.
MINIMIZE_EVALUATION_BUDGET = 400


def minimize_text(
    text: str,
    profile: Profile,
    oracle: BatchJavaOracle,
    tool: Any,
    target_fingerprint: str,
    budget: int = MINIMIZE_EVALUATION_BUDGET,
) -> str:
    """Deterministically shrink ``text`` while preserving its discrepancy fingerprint.

    The trusted Java result is never edited; every candidate is re-checked against the
    live oracle.
    """
    remaining = budget

    def keeps(candidate: str) -> bool:
        nonlocal remaining
        if not candidate.strip():
            return False
        if remaining <= 0:
            return False
        remaining -= 1
        return _fingerprint_of(candidate, profile, oracle, tool) == target_fingerprint

    # Each level splits the text into parts plus the exact separator that rejoins
    # them, so a rejected candidate is always a real substring structure of the
    # original rather than a re-punctuated approximation.
    levels: tuple[tuple[Callable[[str], List[str]], str], ...] = (
        (lambda s: s.split("\n\n"), "\n\n"),
        (lambda s: s.split("\n"), "\n"),
        (lambda s: [p for p in re.split(r"(?<=[.!?…])(?=\s)", s) if p], ""),
        (lambda s: s.split(" "), " "),
    )

    current = text
    for split, joiner in levels:
        changed = True
        while changed:
            changed = False
            parts = split(current)
            if len(parts) <= 1:
                break
            for index in range(len(parts) - 1, -1, -1):
                candidate = joiner.join(parts[:index] + parts[index + 1 :])
                if candidate != current and keeps(candidate):
                    current = candidate
                    changed = True
                    break

    # Final character-level trim of leading/trailing fragments.
    changed = True
    while changed and len(current) > 1:
        changed = False
        for candidate in (current[1:], current[:-1], current.strip()):
            if candidate != current and keeps(candidate):
                current = candidate
                changed = True
                break
    return current


# --------------------------------------------------------------------------
# State isolation proof
# --------------------------------------------------------------------------


def state_isolation_check(
    cases: Sequence[CorpusCase], sample: int = 300, heap: str = "6g"
) -> Dict[str, Any]:
    """Prove results do not depend on instance reuse or on case order.

    Cases on which the pinned oracle raises are dropped from the sample and counted:
    there is no Java result to compare across configurations for them.  See
    ``compat/differential_upstream_defects_0014.json``.
    """
    profiles = build_profiles()
    picker = random.Random(f"{FIXED_SEED}:state-isolation")
    # Always exercise every declared profile, then fill the remaining bounded sample
    # deterministically.  A purely random sample could omit the small config-sensitive
    # profiles and leave their state isolation unproved.
    first_by_profile: Dict[str, CorpusCase] = {}
    for case in cases:
        first_by_profile.setdefault(case.profile, case)
    mandatory_ids = {case.case_id for case in first_by_profile.values()}
    remaining = [case for case in cases if case.case_id not in mandatory_ids]
    random_count = min(max(sample - len(first_by_profile), 0), len(remaining))
    random_indexes = sorted(picker.sample(range(len(remaining)), random_count))
    case_order = {case.case_id: index for index, case in enumerate(cases)}
    chosen = sorted(
        list(first_by_profile.values()) + [remaining[i] for i in random_indexes],
        key=lambda case: case_order[case.case_id],
    )

    def signature(results: Mapping[str, List[Finding]]) -> Dict[str, str]:
        return {
            case_id: hashlib.sha256(
                json.dumps(
                    [f.comparable_json() for f in findings], ensure_ascii=False
                ).encode("utf-8")
            ).hexdigest()
            for case_id, findings in results.items()
        }

    shared_java: Dict[str, List[Finding]] = {}
    fresh_java: Dict[str, List[Finding]] = {}
    reverse_java: Dict[str, List[Finding]] = {}
    shared_python: Dict[str, List[Finding]] = {}
    fresh_python: Dict[str, List[Finding]] = {}
    reverse_python: Dict[str, List[Finding]] = {}
    oracle_error_case_ids: List[str] = []

    needed = sorted({case.profile for case in chosen})

    def java_check(oracle: BatchJavaOracle, case: CorpusCase, profile_id: str):
        """Return the oracle's findings, or None when the pinned pipeline raises."""
        try:
            return oracle.check(case.case_id, profile_id, case.text)
        except OracleProtocolError:
            if case.case_id not in oracle_error_case_ids:
                oracle_error_case_ids.append(case.case_id)
            return None

    # Twice as many JLanguageTool instances live at once here as in a campaign run,
    # because every profile is also built a second time from scratch.
    with BatchJavaOracle(heap=heap) as oracle:
        for profile_id in needed:
            oracle.define_profile(profiles[profile_id])
        shared_tools = {pid: python_tool(profiles[pid]) for pid in needed}

        for case in chosen:
            found = java_check(oracle, case, case.profile)
            if found is None:
                continue
            shared_java[case.case_id] = found
            shared_python[case.case_id] = pylat_findings(
                shared_tools[case.profile].check(
                    case.text, level=profiles[case.profile].level
                )
            )

        for case in reversed(chosen):
            found = java_check(oracle, case, case.profile)
            if found is None:
                continue
            reverse_java[case.case_id] = found
            reverse_python[case.case_id] = pylat_findings(
                shared_tools[case.profile].check(
                    case.text, level=profiles[case.profile].level
                )
            )

        # Fresh Java profiles and fresh Python instances for the same inputs.
        for profile_id in needed:
            oracle.define_profile(
                Profile(
                    profile_id=f"fresh_{profile_id}",
                    enabled_rules=profiles[profile_id].enabled_rules,
                    disabled_rules=profiles[profile_id].disabled_rules,
                    rule_config=profiles[profile_id].rule_config,
                    enable_all_default_off=profiles[profile_id].enable_all_default_off,
                    level=profiles[profile_id].level,
                )
            )
        for case in chosen:
            found = java_check(oracle, case, f"fresh_{case.profile}")
            if found is None:
                continue
            fresh_java[case.case_id] = found
            fresh_python[case.case_id] = pylat_findings(
                python_tool(profiles[case.profile]).check(
                    case.text, level=profiles[case.profile].level
                )
            )

    comparable = sorted(
        set(shared_java) & set(fresh_java) & set(reverse_java)
    )

    def restrict(results: Mapping[str, List[Finding]]) -> Dict[str, str]:
        return signature({key: results[key] for key in comparable})

    shared_java_sig = restrict(shared_java)
    fresh_java_sig = restrict(fresh_java)
    reverse_java_sig = restrict(reverse_java)
    shared_python_sig = restrict(shared_python)
    fresh_python_sig = restrict(fresh_python)
    reverse_python_sig = restrict(reverse_python)

    divergent = sorted(
        case_id
        for case_id in comparable
        if shared_java_sig[case_id] != fresh_java_sig[case_id]
        or shared_java_sig[case_id] != reverse_java_sig[case_id]
        or shared_python_sig[case_id] != fresh_python_sig[case_id]
        or shared_python_sig[case_id] != reverse_python_sig[case_id]
    )
    return {
        "sample_size": len(comparable),
        "requested_sample": len(chosen),
        "oracle_error_cases": len(oracle_error_case_ids),
        "oracle_error_case_ids": sorted(oracle_error_case_ids),
        "profiles": needed,
        "java_fresh_matches_shared": shared_java_sig == fresh_java_sig,
        "java_reverse_matches_forward": shared_java_sig == reverse_java_sig,
        "python_fresh_matches_shared": shared_python_sig == fresh_python_sig,
        "python_reverse_matches_forward": shared_python_sig == reverse_python_sig,
        "divergent_case_ids": divergent,
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _git_sha() -> str:
    import subprocess

    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - development helper only
        return "unknown"


def _filter_cases(
    cases: Sequence[CorpusCase],
    stratum: Optional[str],
    profile: Optional[str],
    shard: Optional[str],
) -> List[CorpusCase]:
    selected = list(cases)
    if stratum:
        selected = [c for c in selected if c.source_stratum == stratum]
    if profile:
        selected = [c for c in selected if c.profile == profile]
    if shard:
        index, total = (int(part) for part in shard.split("/"))
        selected = [c for i, c in enumerate(selected) if i % total == index - 1]
    return selected


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate-oracle", help="validate the trusted pinned Java oracle")
    sub.add_parser("build", help="regenerate the corpus and its manifest")

    run_parser = sub.add_parser("run", help="run the differential campaign")
    run_parser.add_argument("--stratum", choices=STRATA)
    run_parser.add_argument("--profile")
    run_parser.add_argument("--shard", help="run shard i of n, e.g. 1/4")
    run_parser.add_argument("--resume", action="store_true")
    run_parser.add_argument("--output", type=Path)

    sub.add_parser("summarize", help="regenerate compat/differential_summary_0014.json")

    minimize_parser = sub.add_parser("minimize", help="minimize recorded mismatches")
    minimize_parser.add_argument("--limit", type=int, default=50)
    minimize_parser.add_argument("--offset", type=int, default=0)
    minimize_parser.add_argument(
        "--budget", type=int, default=MINIMIZE_EVALUATION_BUDGET
    )
    minimize_parser.add_argument("--input", type=Path, help="campaign results to read")
    minimize_parser.add_argument("--output", type=Path)

    sub.add_parser("calibrate-utf16", help="regenerate the UTF-16 offset calibration fixture")
    sub.add_parser(
        "bind-fixtures",
        help="record the Task-0014 fixtures in compat/oracle_manifest.json",
    )
    sub.add_parser("verify-regressions", help="re-check the committed regression fixture")

    regression_parser = sub.add_parser(
        "build-regressions", help="build the committed minimized regression fixture"
    )
    regression_parser.add_argument("--from-minimized", type=Path)

    isolation_parser = sub.add_parser(
        "state-isolation", help="prove long-lived state and order invariance"
    )
    isolation_parser.add_argument("--sample", type=int, default=300)
    isolation_parser.add_argument("--output", type=Path)

    args = parser.parse_args(argv)

    if args.command == "validate-oracle":
        oracle = JavaLanguageToolOracle()
        info = oracle.validate_oracle()
        print(json.dumps(info, indent=2, sort_keys=True, default=str))
        return 0

    if args.command == "build":
        cases, accounting = build_corpus()
        write_corpus(cases)
        manifest = build_manifest(cases, accounting)
        write_manifest(manifest)
        print(json.dumps(accounting, indent=2, sort_keys=True))
        print(f"corpus -> {CORPUS_PATH}")
        print(f"manifest -> {MANIFEST_PATH}")
        return 0

    if args.command == "run":
        cases = read_corpus()
        selected = _filter_cases(cases, args.stratum, args.profile, args.shard)
        output = args.output or results_path()
        print(f"Running {len(selected)} cases -> {output}", file=sys.stderr)
        results = run_campaign(selected, output, resume=args.resume)
        exact = sum(1 for r in results if r.is_exact)
        print(f"{exact}/{len(results)} exact in this run", file=sys.stderr)
        return 0

    if args.command == "summarize":
        cases = read_corpus()
        results = read_results(results_path())
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        summary = build_summary(cases, results, manifest, _git_sha())
        write_summary(summary)
        print(json.dumps(summary["totals"], indent=2, sort_keys=True))
        print(f"unexplained: {summary['unexplained_discrepancies']}")
        print(f"summary -> {SUMMARY_PATH}")
        return 0

    if args.command == "minimize":
        return _minimize_command(args)

    if args.command == "calibrate-utf16":
        payload = generate_utf16_calibration()
        UTF16_CALIBRATION_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"calibration -> {UTF16_CALIBRATION_PATH} ({len(payload['cases'])} cases)")
        return 0

    if args.command == "bind-fixtures":
        return _bind_fixtures_command()

    if args.command == "build-regressions":
        return _build_regressions_command(args)

    if args.command == "verify-regressions":
        return _verify_regressions_command()

    if args.command == "state-isolation":
        cases = read_corpus()
        report = state_isolation_check(cases, sample=args.sample)
        manifest_data = validate_oracle_manifest(
            REPO_ROOT / "compat" / "oracle_manifest.json"
        )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "task": TASK,
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": manifest_data["default_build_id"],
            "corpus_signature": corpus_signature(cases),
            **report,
        }
        output = args.output or STATE_ISOLATION_PATH
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"state isolation -> {output}")
        return 0 if not report["divergent_case_ids"] else 1

    return 1


def _minimize_command(args: argparse.Namespace) -> int:
    cases = {case.case_id: case for case in read_corpus()}
    results = [
        r
        for r in read_results(args.input or results_path())
        if not r.is_exact and not r.java_error
    ]
    profiles = build_profiles()

    by_fingerprint: Dict[str, CaseResult] = {}
    for result in results:
        by_fingerprint.setdefault(mismatch_fingerprint(result), result)

    selected = sorted(by_fingerprint.items())[
        args.offset : args.offset + args.limit
    ]
    output = args.output or (RESULTS_DIR / "minimized.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    minimized: List[Dict[str, Any]] = []
    with BatchJavaOracle() as oracle:
        for profile_id in sorted({r.profile for _, r in selected}):
            oracle.define_profile(profiles[profile_id])
        tools = {
            pid: python_tool(profiles[pid]) for pid in sorted({r.profile for _, r in selected})
        }
        for fingerprint, result in selected:
            case = cases[result.case_id]
            profile = profiles[case.profile]
            minimal = minimize_text(
                case.text,
                profile,
                oracle,
                tools[case.profile],
                fingerprint,
                budget=args.budget,
            )
            minimized.append(
                {
                    "fingerprint": fingerprint,
                    "case_id": case.case_id,
                    "discovered_in_stratum": case.source_stratum,
                    "profile": case.profile,
                    "original_mismatch_kinds": result.mismatch_kinds,
                    "original_length": len(case.text),
                    "minimized_length": len(minimal),
                    "minimized_text": minimal,
                }
            )
            print(
                f"  {fingerprint}: {len(case.text)} -> {len(minimal)} chars",
                file=sys.stderr,
            )

    output.write_text(
        json.dumps(minimized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"minimized -> {output}")
    return 0


def _bind_fixtures_command() -> int:
    """Bind the Task-0014 fixtures to the trusted oracle identity.

    Each binding records the fixture path, byte size, SHA-256, the oracle build that
    produced its expected findings, and its case count, so a fixture edited by hand
    fails the Java-free manifest tests.
    """
    oracle_manifest_path = REPO_ROOT / "compat" / "oracle_manifest.json"
    manifest_data = validate_oracle_manifest(oracle_manifest_path)
    payload = json.loads(oracle_manifest_path.read_text(encoding="utf-8"))

    bindings = {binding["path"]: binding for binding in payload["fixture_bindings"]}
    for path in (REGRESSION_FIXTURE_PATH, UTF16_CALIBRATION_PATH):
        relative = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        fixture = json.loads(path.read_text(encoding="utf-8"))
        bindings[relative] = {
            "path": relative,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
            "oracle_build_id": manifest_data["default_build_id"],
            "case_count": len(fixture["cases"]),
        }
        print(f"bound {relative} ({bindings[relative]['case_count']} cases)")

    payload["fixture_bindings"] = [bindings[key] for key in sorted(bindings)]
    oracle_manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    validate_oracle_manifest(oracle_manifest_path)
    return 0


def _build_regressions_command(args: argparse.Namespace) -> int:
    """Build the committed regression fixture from minimized mismatches.

    Expected findings always come from the trusted oracle, never from memory.  When
    Task 0014 found no ordinary compatibility bug the fixture is written with an
    explicit empty case list rather than invented content.
    """
    source = args.from_minimized or (RESULTS_DIR / "minimized.json")
    minimized: List[Dict[str, Any]] = (
        json.loads(source.read_text(encoding="utf-8")) if source.is_file() else []
    )
    manifest_data = validate_oracle_manifest(REPO_ROOT / "compat" / "oracle_manifest.json")
    profiles = build_profiles()

    regression_inputs = [*minimized, *PINNED_ORACLE_REGRESSION_CASES]
    cases: List[Dict[str, Any]] = []
    if regression_inputs:
        with BatchJavaOracle() as oracle:
            for profile_id in sorted(
                {entry["profile"] for entry in regression_inputs}
            ):
                oracle.define_profile(profiles[profile_id])
            for entry in sorted(regression_inputs, key=lambda e: e["case_id"]):
                java = oracle.check(
                    entry["case_id"], entry["profile"], entry["minimized_text"]
                )
                cases.append(
                    {
                        "case_id": entry["case_id"],
                        "discovered_in_stratum": entry["discovered_in_stratum"],
                        "original_mismatch_type": sorted(
                            entry["original_mismatch_kinds"]
                        ),
                        "minimized_text": entry["minimized_text"],
                        "profile": entry["profile"],
                        "expected_java_findings": [f.comparable_json() for f in java],
                        "upstream_proof": entry.get(
                            "upstream_proof",
                            "pinned LanguageTool 6.8 Russian pipeline at commit "
                            + PINNED_LT_COMMIT,
                        ),
                    }
                )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "task": TASK,
        "metadata": {
            "pinned_lt_version": PINNED_LT_VERSION,
            "pinned_lt_commit": PINNED_LT_COMMIT,
            "oracle_build_id": manifest_data["default_build_id"],
            "oracle_jar_sha256": manifest_data["oracle_sha256"],
            "finding_field_order": [
                "rule_id",
                "full_rule_id",
                "category_id",
                "category_name",
                "message",
                "short_message",
                "utf16_offset",
                "utf16_length",
                "suggestions",
                "url",
            ],
            "empty_reason": (
                ""
                if cases
                else "Task 0014 discovered no ordinary compatibility defect requiring "
                "a minimized regression case; recorded explicitly rather than invented."
            ),
        },
        "cases": cases,
    }
    REGRESSION_FIXTURE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"regressions -> {REGRESSION_FIXTURE_PATH} ({len(cases)} cases)")
    return 0


def _verify_regressions_command() -> int:
    if not REGRESSION_FIXTURE_PATH.is_file():
        print(f"missing {REGRESSION_FIXTURE_PATH}", file=sys.stderr)
        return 1
    payload = json.loads(REGRESSION_FIXTURE_PATH.read_text(encoding="utf-8"))
    profiles = build_profiles()
    failures = 0
    for case in payload["cases"]:
        tool = python_tool(profiles[case["profile"]])
        actual = [
            f.comparable_json()
            for f in pylat_findings(
                tool.check(case["minimized_text"], level=profiles[case["profile"]].level)
            )
        ]
        expected = [list(f) for f in case["expected_java_findings"]]
        if actual != expected:
            failures += 1
            print(f"MISMATCH {case['case_id']}", file=sys.stderr)
    print(f"{len(payload['cases']) - failures}/{len(payload['cases'])} regression cases match")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
