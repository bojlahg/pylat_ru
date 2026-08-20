"""Task 0013 - direct translations of pinned upstream Russian JUnit test methods.

Every test function in this module reproduces the observable contract of one
``@Test`` method (or one inherited helper contract) of the pinned LanguageTool
6.8 Russian test module at commit
``e807fcde6a6506191e1470744d2345da28c26be6``.

The exact source/method/scenario mapping is recorded in
``compat/upstream_test_inventory_0013.json`` and validated by
``tests/unit/test_upstream_test_inventory_0013.py``.

Methods already translated assertion-for-assertion by earlier tasks are mapped
to those existing tests instead of being duplicated here (Task 0013 section 26):

* ``MorfologikRussianSpellerRuleTest``      -> ``test_java_rules_0012_upstream_tests.py``
* ``MorfologikRussianYOSpellerRuleTest``    -> ``test_java_rules_0012_upstream_tests.py``
* ``RussianCompoundRuleTest``               -> ``test_java_rules_0012_upstream_tests.py``
* ``RussianSimpleReplaceRuleTest``          -> ``test_java_rules_0012_upstream_tests.py``
* ``RussianWordCoherencyRuleTest``          -> ``test_java_rules_0012_upstream_tests.py``
* ``RussianWordRepeatRuleTest``             -> ``test_java_rules_0012_upstream_tests.py``
* ``RussianSynthesizerTest``                -> ``test_russian_synthesizer.py``
* ``RussianSRXSentenceTokenizerTest``       -> ``test_russian_sentence_tokenizer_parity.py``
"""

from __future__ import annotations

import concurrent.futures
import threading
from pathlib import Path
from typing import List

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.filters.date_check import DateCheckFilter
from pylat_ru.morfologik import MorfologikDictionary
from pylat_ru.native_rules import RussianJavaRulesEngine
from pylat_ru.synthesis import RussianSynthesizer
from pylat_ru.tagging.russian import RussianTagger
from pylat_ru.tokenization.word import RussianWordTokenizer


RESOURCE_DIR = Path(__file__).resolve().parents[2] / "src" / "pylat_ru" / "resources"


@pytest.fixture(scope="module")
def engine() -> RussianJavaRulesEngine:
    return RussianJavaRulesEngine()


# ---------------------------------------------------------------------------
# DateCheckFilterTest.java
# ---------------------------------------------------------------------------

def test_date_check_filter_get_day_of_week() -> None:
    """DateCheckFilterTest#testGetDayOfWeek - 4 executable assertions.

    The pinned source comments out the ``вс``/``понедельник``/``Понедельник``/
    ``Пн``/``пятница`` assertions; commented code is not a scenario unit.
    """
    filter_ = DateCheckFilter()
    assert filter_.get_day_of_week("пн") == 2
    assert filter_.get_day_of_week("пн.") == 2
    assert filter_.get_day_of_week("вт") == 3
    assert filter_.get_day_of_week("пт") == 6


def test_date_check_filter_get_month() -> None:
    """DateCheckFilterTest#testMonth - 5 assertions."""
    filter_ = DateCheckFilter()
    assert filter_.get_month("I") == 1
    assert filter_.get_month("XII") == 12
    assert filter_.get_month("декабрь") == 12
    assert filter_.get_month("Декабрь") == 12
    assert filter_.get_month("ДЕКАБРЬ") == 12


# ---------------------------------------------------------------------------
# LanguageSpecificSpellcheckerTest.java -> SpellcheckerTest#runLanguageSpecificTest
# ---------------------------------------------------------------------------

def _load_word_list(path: Path) -> List[str]:
    """Reproduce ``CachingWordListLoader.loadWords`` for one resource file."""
    if not path.is_file():
        return []
    out: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line == "" or line.startswith("#"):
            continue
        out.append(line.strip().split("#")[0].strip())
    return out


def test_language_specific_spellchecker_word_lists() -> None:
    """LanguageSpecificSpellcheckerTest#testRules -> SpellcheckerTest#runLanguageSpecificTest.

    Executable guards for a single-language (Russian) classpath:

    1. the language set must not be empty;
    2. no word may appear in both ``spelling.txt`` and ``prohibit.txt``;
    3. the ``totalProhibited == 0`` guard only fires for more than five
       languages, so for the Russian module it is unreachable - the prohibited
       list is asserted non-empty here instead, which is strictly stronger.
    """
    hunspell = RESOURCE_DIR / "ru" / "hunspell"
    prohibited = _load_word_list(hunspell / "prohibit.txt")
    spelling = _load_word_list(hunspell / "spelling.txt")

    assert prohibited, "no words loaded from ru/hunspell/prohibit.txt"
    assert spelling, "no words loaded from ru/hunspell/spelling.txt"

    spelling_set = set(spelling)
    intersection = {w for w in prohibited if w in spelling_set}
    assert not intersection, (
        "Word(s) appear in both spelling.txt and prohibit.txt - "
        f"this doesn't make sense: {sorted(intersection)}"
    )


# ---------------------------------------------------------------------------
# RussianDashRuleTest.java
# ---------------------------------------------------------------------------

def _check_dash(engine: RussianJavaRulesEngine, expected_errors: int, text: str,
                expected_suggestions: List[str] | None = None) -> None:
    """Reproduce ``RussianDashRuleTest#check(int, String, String[])``."""
    matches = engine.check_rule(text, "RU_DASH_RULE")
    assert len(matches) == expected_errors, (
        f"Expected {expected_errors} errors, but got: "
        f"{[(m.from_pos, m.to_pos, list(m.suggestions)) for m in matches]}"
    )
    if expected_suggestions is None:
        return
    assert expected_errors == 1, "test case can only check suggestion if there's one rule match"
    assert list(matches[0].suggestions) == expected_suggestions


def test_russian_dash_rule(engine: RussianJavaRulesEngine) -> None:
    """RussianDashRuleTest#testRule - 5 ``check`` scenarios."""
    _check_dash(engine, 0, "Он вышел из-за забора.")
    _check_dash(engine, 0, "Ростов-на-Дону.")
    _check_dash(engine, 0, "ведром — работай")
    _check_dash(engine, 1, "из—за", ["из-за"])
    _check_dash(engine, 1, "Ростов — на — Дону", ["Ростов-на-Дону"])


# ---------------------------------------------------------------------------
# RussianSpecificCaseRuleTest.java
# ---------------------------------------------------------------------------

def _assert_case_good(engine: RussianJavaRulesEngine, text: str) -> None:
    assert len(engine.check_rule(text, "RU_SPECIFIC_CASE")) == 0


def _assert_case_bad(engine: RussianJavaRulesEngine, text: str):
    matches = engine.check_rule(text, "RU_SPECIFIC_CASE")
    assert len(matches) == 1
    return matches


def test_russian_specific_case_rule(engine: RussianJavaRulesEngine) -> None:
    """RussianSpecificCaseRuleTest#testRule - 9 scenario/assertion units."""
    _assert_case_good(engine, "Рытый Банк")
    _assert_case_good(engine, "Центральный банк РФ")
    _assert_case_bad(engine, "Рытый банк")
    _assert_case_bad(engine, "центральный банк РФ")

    matches1 = _assert_case_bad(engine, "I like air France.")
    assert matches1[0].from_pos == 7
    assert matches1[0].to_pos == 17
    assert list(matches1[0].suggestions) == ["Air France"]
    assert matches1[0].message == (
        "Для специальных наименований используйте начальную заглавную букву."
    )


# ---------------------------------------------------------------------------
# RussianUnpairedBracketsRuleTest.java
# ---------------------------------------------------------------------------

def test_russian_unpaired_brackets_rule(engine: RussianJavaRulesEngine) -> None:
    """RussianUnpairedBracketsRuleTest#testRuleRussian - 5 assertions."""
    def count(text: str) -> int:
        return len(engine.check_rule(text, "RU_UNPAIRED_BRACKETS"))

    assert count("(О жене и детях не беспокойся, я беру их на свои руки).") == 0
    assert count(
        "Позже выходит другая «южная поэма» «Бахчисарайский фонтан» (1824)."
    ) == 0
    assert count('А "б" Д.') == 0
    assert count("а), б), Д)..., ДД), аа) и 1а)") == 0
    assert count(
        "В таком ключе был начат в мае 1823 в Кишинёве роман в стихах 'Евгений Онегин."
    ) == 1


# ---------------------------------------------------------------------------
# RussianVerbConjugationRuleTest.java
# ---------------------------------------------------------------------------

RIGHT_SENTENCES = (
    "Я иду", "Она сидит", "Оно думает", "Они пишут", "Мы думаем", "Ты читаешь",
    "Он творит", "Вы идёте", "Я ходил", "Они ходили", "Мы ходили", "Она ходила",
    "Оно ходило", "Я ходила", "Я пойду", "Она пойдёт", "Оно пойдёт", "Мы пойдём",
    "Ты пойдёшь", "Я согласился на предложение.", "Джек и я согласились",
    "Ты может быть не помнишь.",
)

WRONG_SENTENCES = (
    "Я идёт", "Она сидят", "Оно думаешь", "Они идёте", "Мы думаю", "Ты читает",
    "Он творю", "Я ходили", "Они ходил", "Мы ходила", "Она ходил", "Оно ходила",
    "Я ходило", "Я пойдёт", "Она пойдут", "Оно пойдёте", "Мы пойдёшь", "Ты пойду",
    "Мы может поговорить здесь.",
)


@pytest.mark.parametrize("sentence", WRONG_SENTENCES)
def test_russian_verb_conjugation_rule_wrong(engine: RussianJavaRulesEngine, sentence: str) -> None:
    """RussianVerbConjugationRuleTest#testRussianVerbConjugationRule - wrong vector (19)."""
    assert len(engine.check_rule(sentence, "RU_VERB_CONJUGATION")) == 1, (
        f"Expected error in sentence: {sentence}"
    )


@pytest.mark.parametrize("sentence", RIGHT_SENTENCES)
def test_russian_verb_conjugation_rule_right(engine: RussianJavaRulesEngine, sentence: str) -> None:
    """RussianVerbConjugationRuleTest#testRussianVerbConjugationRule - right vector (22)."""
    assert len(engine.check_rule(sentence, "RU_VERB_CONJUGATION")) == 0, (
        f"Did not expect error in sentence: {sentence}"
    )


def test_russian_verb_conjugation_vectors_match_pinned_source() -> None:
    """The pinned vectors are ``ImmutableSet``s: 22 + 19 distinct scenarios."""
    assert len(set(RIGHT_SENTENCES)) == 22
    assert len(set(WRONG_SENTENCES)) == 19


# ---------------------------------------------------------------------------
# RussianTaggerTest.java
# ---------------------------------------------------------------------------

def _java_str(value) -> str:
    """Java string concatenation renders ``null`` where Python renders ``None``."""
    return "null" if value is None else str(value)


def _my_assert(text: str) -> str:
    """Reproduce ``TestTools.myAssert(input, expected, tokenizer, tagger)``.

    Whitespace-only tokens are dropped, every token is tagged, each token's
    readings are rendered as ``token/[lemma]POS`` and sorted, readings are
    joined with ``|`` and tokens with `` -- ``.
    """
    tokens = [t for t in RussianWordTokenizer().tokenize(text)
              if any(ch.isalpha() or ch.isdigit() for ch in t)]
    rendered = []
    for reading in RussianTagger.get_instance().tag(tokens):
        parts = sorted(
            f"{_java_str(r.token)}/[{_java_str(r.lemma)}]{_java_str(r.pos_tag)}"
            for r in reading.readings
        )
        rendered.append("|".join(parts))
    return " -- ".join(rendered)


TAGGER_CASES = [
    (
        "Все счастливые семьи похожи друг на друга,  каждая  несчастливая  семья "
        "несчастлива по-своему.",
        "Все/[весь]ADJ:MPR:PL:Nom|Все/[весь]ADJ:MPR:PL:V|Все/[все]PNN:PL:Nom|"
        "Все/[все]PNN:PL:V|Все/[все]PNN:Sin:Nom|Все/[все]PNN:Sin:V -- "
        "счастливые/[счастливый]ADJ:Posit:PL:Nom|счастливые/[счастливый]ADJ:Posit:PL:V -- "
        "семьи/[семья]NN:Inanim:Fem:PL:Nom|семьи/[семья]NN:Inanim:Fem:PL:V|"
        "семьи/[семья]NN:Inanim:Fem:Sin:R -- похожи/[похожий]ADJ:Short:PL -- "
        "друг/[друг]NN:Anim:Masc:Sin:Nom -- на/[на]PREP -- "
        "друга/[друг]NN:Anim:Masc:Sin:R|друга/[друг]NN:Anim:Masc:Sin:V -- "
        "каждая/[каждый]ADJ:MPR:Fem:Nom -- несчастливая/[несчастливый]ADJ:Posit:Fem:Nom -- "
        "семья/[семья]NN:Inanim:Fem:Sin:Nom -- несчастлива/[несчастливый]ADJ:Short:Fem -- "
        "по-своему/[по-своему]ADV",
    ),
    (
        "Все смешалось в доме Облонских.",
        "Все/[весь]ADJ:MPR:PL:Nom|Все/[весь]ADJ:MPR:PL:V|Все/[все]PNN:PL:Nom|"
        "Все/[все]PNN:PL:V|Все/[все]PNN:Sin:Nom|Все/[все]PNN:Sin:V -- "
        "смешалось/[смешаться]VB:Past:INTR:PFV:Neut -- в/[в]PREP -- "
        "доме/[дом]NN:Inanim:Masc:Sin:P -- Облонских/[null]null",
    ),
    ("Абдуллаевы", "Абдуллаевы/[абдуллаев]NN:Fam:PL:Nom"),
    ("блукать", "блукать/[блукать]VB:INF:"),
]


@pytest.mark.parametrize("text,expected", TAGGER_CASES)
def test_russian_tagger_exact_readings(text: str, expected: str) -> None:
    """RussianTaggerTest#testTagger - 4 exact ``TestTools.myAssert`` scenarios."""
    assert _my_assert(text) == expected


TAGGER_DICTIONARY_SWEEP_LIMIT = 50_000


def test_russian_tagger_dictionary() -> None:
    """RussianTaggerTest#testDictionary -> ``TestTools.testDictionary``.

    Upstream opens the tagger dictionary, iterates every ``WordData`` entry and
    *warns* (it never fails) about entries lacking a POS tag, so the executable
    contract is: the packaged dictionary loads and a full iteration completes.

    The exhaustive 7,176,385-entry sweep takes minutes in Python and is run by
    ``tools/audit_tagger_dictionary_0013.py``; its committed result is asserted
    by ``tests/unit/test_upstream_test_inventory_0013.py``.  This test performs
    the load and a bounded deterministic prefix sweep of the same FSA.
    """
    dictionary = MorfologikDictionary.open(
        RESOURCE_DIR / "ru" / "russian.dict",
        RESOURCE_DIR / "ru" / "russian.info",
    )
    separator = dictionary.separator_byte
    entries = 0
    untagged = 0
    for sequence in dictionary.fsa.get_sequences():
        entries += 1
        first = sequence.find(separator)
        second = sequence.find(separator, first + 1)
        if first <= 0 or second == -1 or second == len(sequence) - 1:
            untagged += 1
        if entries >= TAGGER_DICTIONARY_SWEEP_LIMIT:
            break
    assert entries == TAGGER_DICTIONARY_SWEEP_LIMIT
    assert untagged == 0, f"{untagged} dictionary entries lack a POS tag"
    assert dictionary.lookup("семья"), "known word missing from the tagger dictionary"


# ---------------------------------------------------------------------------
# RussianConcurrencyTest.java -> AbstractLanguageConcurrencyTest
# ---------------------------------------------------------------------------

CONCURRENCY_SAMPLE = "Материал из Википедии — свободной энциклопедии"
CONCURRENCY_CONTAMINATION_TEXT = (
    "Абсолютный нуль.\n\nСовсем недостижим. И ноль по шкале Кельвина."
)

# Upstream uses availableProcessors()*10 threads and 100 runs, but the pinned
# method carries @Ignore("too slow to run every time") and therefore never
# executes at the pin.  This port executes on every run at a stress level sized
# for the Python runtime; see reports/0013_complete_upstream_russian_test_parity.md.
CONCURRENCY_THREADS = 12
CONCURRENCY_RUNS = 3


def _fingerprint(matches) -> tuple:
    return tuple(
        (m.rule_id, m.offset, m.length, m.message, tuple(m.replacements))
        for m in matches
    )


def test_concurrency_fresh_instance_per_run() -> None:
    """AbstractLanguageConcurrencyTest#testSpellCheckerFailure sharing model.

    Every worker builds its own pipeline instance and checks the pinned sample
    text, exactly as the upstream ``TestRunner`` does.  No worker may raise and
    every result must be identical.
    """
    baseline = _fingerprint(LanguageToolRU().check(CONCURRENCY_SAMPLE))
    barrier = threading.Barrier(CONCURRENCY_THREADS)

    def worker() -> List[tuple]:
        barrier.wait(timeout=120)
        out = []
        for _ in range(CONCURRENCY_RUNS):
            result = LanguageToolRU().check(CONCURRENCY_SAMPLE)
            assert result is not None
            out.append(_fingerprint(result))
        return out

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY_THREADS) as pool:
        futures = [pool.submit(worker) for _ in range(CONCURRENCY_THREADS)]
        results = [f.result() for f in futures]

    assert len(results) == CONCURRENCY_THREADS
    for per_thread in results:
        assert len(per_thread) == CONCURRENCY_RUNS
        for fingerprint in per_thread:
            assert fingerprint == baseline


def test_concurrency_shared_instance_and_state_isolation() -> None:
    """Task 0013 section 34: shared native components stay race- and state-free.

    The text list deliberately exercises the two pieces of mutable per-attempt
    state carried by cached compiled variants: feature unification (the
    ``Unify_*`` rules reached by the coherency/repeat texts) and the single
    pinned Russian antipattern that uses a token-level ``<match>`` reference
    (``Multiple_missing_commas_VB[1]``).
    """
    tool = LanguageToolRU()
    texts = [
        CONCURRENCY_SAMPLE,
        CONCURRENCY_CONTAMINATION_TEXT,
        "Повтор слов в повтор предложении.",
        "Свиньи все подохли остался один баран.",
        "Свиньи все подохли, остался один баран.",
        "Все счастливые семьи похожи друг на друга, каждя несчастливая семья несчастлива по-своему.",
    ]
    baseline = [_fingerprint(tool.check(t)) for t in texts]

    tagger_before = RussianTagger.get_instance()
    disambiguator_before = RussianHybridDisambiguator.get_instance()
    synthesizer_before = RussianSynthesizer.get_instance()
    grammar_before = RussianGrammarEngine.get_instance()

    barrier = threading.Barrier(CONCURRENCY_THREADS)

    def worker(index: int) -> List[tuple]:
        barrier.wait(timeout=120)
        out = []
        for _ in range(CONCURRENCY_RUNS):
            for text in texts:
                out.append(_fingerprint(tool.check(text)))
        return out

    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY_THREADS) as pool:
        results = [f.result() for f in
                   [pool.submit(worker, i) for i in range(CONCURRENCY_THREADS)]]

    expected = baseline * CONCURRENCY_RUNS
    for per_thread in results:
        assert per_thread == expected

    # Shared singletons must be the very same objects afterwards.
    assert RussianTagger.get_instance() is tagger_before
    assert RussianHybridDisambiguator.get_instance() is disambiguator_before
    assert RussianSynthesizer.get_instance() is synthesizer_before
    assert RussianGrammarEngine.get_instance() is grammar_before

    # And sequential results must be unchanged after the concurrent load.
    assert [_fingerprint(tool.check(t)) for t in texts] == baseline
