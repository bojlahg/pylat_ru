"""Task 0013 - ``RussianTest#testLanguage`` decomposed into its contracts.

``RussianTest`` declares a single ``@Test`` method that calls
``LanguageSpecificTest#testDemoText`` and then ``LanguageSpecificTest#runTests``.
At the pin ``runTests(lang)`` resolves, for Russian, to::

    new WordListValidatorTest("").testWordListValidity(ru)   -> returns immediately for "ru"
    testNoLineBreaksEtcInMessage(ru)                         -> warning-only
    testNoQuotesAroundSuggestion(ru)
    testJavaRules(null)
    testConfusionSetLoading()                                -> language-model rule
    countTempOffRules(ru)                                    -> warning-only
    testCoherencyBaseformIsOtherForm(ru)
    testReplaceRuleReplacements(ru)                          -> warning-only
    new DisambiguationRuleTest().testDisambiguationRulesFromXML()

Each executable sub-contract is reproduced below, except the disambiguation
example suite, which is already executed by
``tests/upstream/test_russian_disambiguation_parity.py``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.analysis import AnalyzedToken
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.native_rules import RussianJavaRulesEngine
from pylat_ru.synthesis import RussianSynthesizer

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_DIR = REPO_ROOT / "src" / "pylat_ru" / "resources" / "rules" / "ru"
RESOURCE_DIR = REPO_ROOT / "src" / "pylat_ru" / "resources" / "ru"
VENDORED_TESTS = (
    REPO_ROOT / "third_party" / "languagetool" / "languagetool-core"
    / "src" / "test" / "java" / "org" / "languagetool"
)


@pytest.fixture(scope="module")
def java_rules() -> RussianJavaRulesEngine:
    return RussianJavaRulesEngine()


def _clean_markers(text: str) -> str:
    return text.replace("<marker>", "").replace("</marker>", "")


# ---------------------------------------------------------------------------
# LanguageSpecificTest#testDemoText
# ---------------------------------------------------------------------------

DEMO_TEXT = (
    "Вставьте ваш текст сюда .. или проверьте этот текстт. "
    "Релиз LanguageTool 4.7 состоялся в четверг 28 сентября 2019 года."
)
DEMO_EXPECTED_RULE_IDS = [
    "DOUBLE_PUNCTUATION",
    "UPPERCASE_SENTENCE_START",
    "MORFOLOGIK_RULE_RU_RU",
    "DATE_WEEKDAY1",
]


def test_demo_text() -> None:
    """RussianTest#testLanguage -> LanguageSpecificTest#testDemoText.

    The demo text must produce exactly these specific rule ids, in this order.
    """
    matches = LanguageToolRU().check(DEMO_TEXT)
    assert [m.rule_id for m in matches] == DEMO_EXPECTED_RULE_IDS


# ---------------------------------------------------------------------------
# WordListValidatorTest#testWordListValidity
# ---------------------------------------------------------------------------

def test_word_list_validator_skips_russian() -> None:
    """WordListValidatorTest#testWordListValidity - not applicable to Russian.

    The pinned source opens with an unconditional early return for ``ru``
    because Cyrillic characters are not part of the validation character class,
    so no word list is ever validated for the Russian module.
    """
    source = (VENDORED_TESTS / "rules" / "WordListValidatorTest.java").read_text(encoding="utf-8")
    guard = source.split("public void testWordListValidity(Language lang) {", 1)[1]
    head = guard[:guard.index("Set<String> checked")]
    assert 'lang.getShortCode().equals("ru")' in head
    assert "return;" in head


# ---------------------------------------------------------------------------
# LanguageSpecificTest#testNoQuotesAroundSuggestion
# ---------------------------------------------------------------------------

def test_no_quotes_around_suggestion() -> None:
    """LanguageSpecificTest#testNoQuotesAroundSuggestion.

    Upstream inspects the loaded ``<message>`` of every pattern rule, including
    the inline ``<suggestion>`` markup, so this check runs against the pinned
    grammar source rather than the parsed message template.
    """
    grammar = (RULES_DIR / "grammar.xml").read_text(encoding="utf-8")
    messages = re.findall(r"<message>(.*?)</message>", grammar, re.S)
    assert len(messages) > 0
    offending = [
        m for m in messages
        if re.match(r".*['\"«»“”’]<suggestion.*", m, re.S)
        and re.match(r".*</suggestion>['\"«»“”’].*", m, re.S)
    ]
    assert offending == [], (
        "rule uses quotes around <suggestion>...</suggestion> in its <message>: "
        f"{offending}"
    )


# ---------------------------------------------------------------------------
# LanguageSpecificTest#testJavaRules  (+ assertId*/testExamples helpers)
# ---------------------------------------------------------------------------

def test_java_rules_id_and_description_validity(java_rules: RussianJavaRulesEngine) -> None:
    """LanguageSpecificTest#assertIdValidity / #assertIdAndDescriptionValidity."""
    for rule in java_rules.rules:
        assert rule.rule_id.strip(), "empty rule id"
        assert rule.description.strip(), f"empty rule description for rule: {rule.rule_id}"
        assert re.fullmatch(r"[A-Z_][A-Z0-9_]+", rule.rule_id), (
            f"Invalid character in rule id: '{rule.rule_id}', only [A-Z0-9_] are "
            "allowed and the first character must be in [A-Z_]"
        )


def test_java_rules_id_uniqueness(java_rules: RussianJavaRulesEngine) -> None:
    """LanguageSpecificTest#assertIdUniqueness."""
    ids = [rule.rule_id for rule in java_rules.rules]
    assert len(ids) == len(set(ids)), "Rule id occurs more than once"
    assert len(ids) == 23, f"expected the 23 pinned ordinary Java rules, got {len(ids)}"


def test_java_rules_examples(java_rules: RussianJavaRulesEngine) -> None:
    """LanguageSpecificTest#testExamples -> #testCorrectExamples / #testIncorrectExamples.

    With only the rule under test enabled, every incorrect example must produce
    exactly one match and every correct example none.  ``idToExpectedMatches``
    holds no Russian id at the pin, so the expected count is always 1.
    """
    checked = 0
    for rule in java_rules.rules:
        for example in rule.incorrect_examples:
            matches = java_rules.check_rule(_clean_markers(example), rule.rule_id)
            assert len(matches) == 1, (
                "Did not get the expected rule match for the incorrect example "
                f"sentence:\nText: {example}\nRule: {rule.rule_id}\nMatches: {matches}"
            )
            checked += 1
        for example in rule.correct_examples:
            matches = java_rules.check_rule(_clean_markers(example), rule.rule_id)
            assert len(matches) == 0, (
                "Got unexpected rule match for correct example sentence:\n"
                f"Text: {example}\nRule: {rule.rule_id}\nMatches: {matches}"
            )
            checked += 1
    assert checked == 24, f"expected 12 pinned example pairs, got {checked} examples"


# ---------------------------------------------------------------------------
# LanguageSpecificTest#testConfusionSetLoading
# ---------------------------------------------------------------------------

def test_confusion_set_loading_is_language_model_deferred() -> None:
    """LanguageSpecificTest#testConfusionSetLoading - language-model deferred.

    The confusion set file is loaded only when
    ``getRelevantLanguageModelRules()`` returns rules.  For Russian that list
    holds exactly ``RussianConfusionProbabilityRule``, which Task 0013 keeps
    deferred, so ``ru/confusion_sets.txt`` is not a packaged runtime resource
    and no ordinary rule depends on it.
    """
    packaged = {p.name for p in RESOURCE_DIR.iterdir() if p.is_file()}
    assert "confusion_sets.txt" not in packaged
    rule_ids = {rule.rule_id for rule in RussianJavaRulesEngine().rules}
    assert "RU_CONFUSION_RULE" not in rule_ids
    assert not any("CONFUSION" in rid for rid in rule_ids)


# ---------------------------------------------------------------------------
# LanguageSpecificTest#testCoherencyBaseformIsOtherForm
# ---------------------------------------------------------------------------

def _coherency_keys() -> List[str]:
    keys: List[str] = []
    for line in (RULES_DIR / "coherency.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keys.extend(line.split(";"))
    return keys


def test_coherency_baseform_is_other_form(java_rules: RussianJavaRulesEngine) -> None:
    """LanguageSpecificTest#testCoherencyBaseformIsOtherForm.

    Upstream synthesises every form of every ``coherency.txt`` key and checks it
    with ``TestTools.disableAllRulesExcept(lt, "EN_WORD_COHERENCY")``.  Russian
    has no rule with that id, so upstream disables *all* rules and the check is
    vacuous.  Both readings are asserted here: the faithful one (nothing is
    enabled, so nothing may match) and the strengthened one that uses the actual
    Russian coherency rule id.
    """
    synthesizer = RussianSynthesizer.get_instance()
    keys = _coherency_keys()
    assert len(keys) == 34

    forms = []
    for key in keys:
        forms.extend(
            synthesizer.synthesize(AnalyzedToken(token=key, lemma=key, pos_tag="fake"), ".*", True)
        )
    forms = sorted(set(forms))
    assert len(forms) == 337, f"coherency form corpus changed: {len(forms)}"

    # Faithful reading: no rule carries the id the pinned test enables.
    rule_ids = {rule.rule_id for rule in java_rules.rules}
    rule_ids |= {rule.id for rule in RussianGrammarEngine.get_instance().get_runnable_rules()}
    assert "EN_WORD_COHERENCY" not in rule_ids

    # Strengthened reading: the Russian coherency rule must not fire on any form.
    invalid = [f for f in forms if java_rules.check_rule(f, "RU_WORD_COHERENCY")]
    assert invalid == [], (
        "These words trigger the rule because their base form is one of the "
        f"forms in coherency.txt, giving false alarms: {invalid}"
    )


# ---------------------------------------------------------------------------
# LanguageSpecificTest#runTests aggregate
# ---------------------------------------------------------------------------

def test_run_tests_aggregate(java_rules: RussianJavaRulesEngine) -> None:
    """LanguageSpecificTest#runTests(Language) - the aggregate entry point.

    ``runTests(lang)`` widens to ``runTests(lang, lang, null, "")`` and then
    calls the nine sub-contracts listed in this module's docstring.  This test
    asserts the preconditions those sub-contracts share: exactly one Russian
    language surface with the pinned rule inventory.
    """
    assert len(java_rules.rules) == 23
    assert len(RussianGrammarEngine.get_instance().get_runnable_rules()) == 892
    # countTempOffRules only warns above 20 default-off pattern rules.
    temp_off = [r.full_id for r in RussianGrammarEngine.get_instance().get_runnable_rules()
                if r.default_off]
    assert isinstance(temp_off, list)
