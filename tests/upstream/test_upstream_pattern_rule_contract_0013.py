"""Task 0013 - ``RussianPatternRuleTest#testRules`` decomposed into its contracts.

``RussianPatternRuleTest`` declares a single ``@Test`` method that delegates to
``PatternRuleTest#runGrammarRulesFromXmlTest()``.  At the pin that helper chain
resolves, for Russian, to::

    runGrammarRulesFromXmlTest()
      -> runGrammarRuleForLanguage(ru)
        -> runTestForLanguage(ru)
             validatePatternFile
             validateRemoteRulesFile
             validateRuleIds                (+ RuleIdValidator#validateUniqueness)
             validateSentenceStartNotInMarker      (warning-only)
             validateUnifyIgnoreAtTheStartOfUnify
             validateParenthesisInSynthesisMatches
             getAllPatternRules
             testRegexSyntax                       (warning-only)
             testMessages
             testGrammarRulesFromXML

Each executable sub-contract is reproduced below.  The example-sentence
contract (``testGrammarRulesFromXML``) is executed by the pre-existing
2446-example suite in ``test_russian_grammar_examples.py``; the checks that
suite does not already make are added here.
"""

from __future__ import annotations

import re
from typing import Iterable, List

import pytest

from pylat_ru.chunking.russian import RussianChunker
from pylat_ru.disambiguation.hybrid import RussianHybridDisambiguator
from pylat_ru.grammar.engine import RussianGrammarEngine
from pylat_ru.grammar.model import GrammarRule, MatchReference
from pylat_ru.native_rules import RussianJavaRulesEngine


@pytest.fixture(scope="module")
def engine() -> RussianGrammarEngine:
    return RussianGrammarEngine.get_instance()


@pytest.fixture(scope="module")
def rules(engine: RussianGrammarEngine) -> List[GrammarRule]:
    return list(engine.get_runnable_rules())


@pytest.fixture(scope="module")
def disambiguator() -> RussianHybridDisambiguator:
    return RussianHybridDisambiguator.get_instance()


@pytest.fixture(scope="module")
def chunker() -> RussianChunker:
    return RussianChunker()


def _raw_text(elements: Iterable) -> str:
    """Render a message/suggestion template the way upstream stores it in XML."""
    out = []
    for element in elements:
        out.append(element if isinstance(element, str) else "\\" + str(element.no))
    return "".join(out)


# ---------------------------------------------------------------------------
# validatePatternFile
# ---------------------------------------------------------------------------

def test_validate_pattern_file(engine: RussianGrammarEngine, rules: List[GrammarRule]) -> None:
    """PatternRuleTest#validatePatternFile - grammar.xml must load and validate.

    Upstream validates ``ru/grammar.xml`` against ``rules.xsd``.  The Python
    loader is fail-closed on unknown elements/attributes (project rule 5.1), so
    the equivalent contract is that the pinned grammar file loads completely:
    892 source rules and 907 compiled physical variants.
    """
    assert len(rules) == 892
    compiled = sum(len(engine._compiled_variants[r.full_id]) for r in rules)
    assert compiled == 907


def test_validate_remote_rules_file_not_applicable() -> None:
    """PatternRuleTest#validateRemoteRulesFile - not applicable to Russian.

    ``validateRemoteRulesFile`` only validates when
    ``<rulesDir>/ru/remote-rule-filters.xml`` exists.  At the pin the Russian
    rules directory contains exactly ``bitext.xml``, ``coherency.txt``,
    ``grammar.xml``, ``replace.txt`` and ``wordrootrep.txt``; there is no
    remote-rule filter file, so ``xmlStream`` is null and the method is a no-op.
    """
    from pylat_ru.resources.rules import ru as ru_rules

    packaged = {p.name for p in __import__("pathlib").Path(ru_rules.__file__).parent.iterdir()
                if p.is_file() and not p.name.endswith(".py")}
    assert "remote-rule-filters.xml" not in packaged


# ---------------------------------------------------------------------------
# validateRuleIds  +  RuleIdValidator#validateUniqueness
# ---------------------------------------------------------------------------

def test_validate_rule_ids(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#validateRuleIds - 4 failing conditions on every rule id."""
    for rule in rules:
        rule_id = rule.id
        assert not rule_id.startswith("DB_"), (
            f"Rule ID must not start with 'DB_', this prefix is reserved: {rule_id}"
        )
        assert "[" not in rule_id and "]" not in rule_id, (
            f"Rule ID must not contain '[...]': {rule_id}"
        )
        assert " " not in rule_id, f"Rule ID must not contain a space: '{rule_id}'"
        assert len(rule_id) <= 79, f"Rule ID too long, keep it <= 79 chars: {rule_id}"


def test_rule_id_uniqueness(rules: List[GrammarRule]) -> None:
    """RuleIdValidator#validateUniqueness - XML ids may not collide with Java ids.

    Upstream collects every non-pattern (Java) rule id first and then every
    ``<rule>``/``<rulegroup>`` id declared in the language's rule files, and
    throws if an id is seen twice.  Ids declared by members of one rulegroup are
    the rulegroup id and therefore not duplicates.
    """
    java_ids = {rule.rule_id for rule in RussianJavaRulesEngine().rules}
    xml_ids = {rule.id for rule in rules}
    collisions = sorted(xml_ids & java_ids)
    assert not collisions, f"id(s) found at least twice: {collisions}"

    full_ids = [rule.full_id for rule in rules]
    assert len(full_ids) == len(set(full_ids)), "duplicate compiled rule identity"


def test_validate_category_ids(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#validateRuleIds - category id shape (upstream warns only)."""
    offending = sorted({r.category_id for r in rules
                        if not re.fullmatch(r"[A-Z0-9_-]+", r.category_id)})
    assert offending == [], f"category ids not matching [A-Z0-9_-]+: {offending}"


# ---------------------------------------------------------------------------
# validateUnifyIgnoreAtTheStartOfUnify
# ---------------------------------------------------------------------------

def test_validate_unify_ignore_not_at_start_of_unify(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#validateUnifyIgnoreAtTheStartOfUnify."""
    failures = []
    for rule in rules:
        for token in rule.pattern.tokens:
            if not token.is_unify:
                continue
            if token.is_unify_neutral:
                failures.append(rule.full_id)
            break
    assert not failures, (
        "<ignore-unify> at the start of <unify> - please move the token outside "
        f"of <unify>: {failures}"
    )


# ---------------------------------------------------------------------------
# validateParenthesisInSynthesisMatches
# ---------------------------------------------------------------------------

def _max_back_reference(text: str) -> int:
    """Upstream ``getMaxBackReferenceNo``: back references are never above 9."""
    numbers = [int(m[1:]) for m in re.findall(r"\$[0-9]", text)]
    return max(numbers) if numbers else -1


def test_validate_parenthesis_in_synthesis_matches(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#validateParenthesisInSynthesisMatches."""
    failures = []
    for rule in rules:
        references = [element
                      for template in list(rule.suggestions) + [rule.message_template]
                      for element in template.elements
                      if isinstance(element, MatchReference)]
        for reference in references:
            if reference.postag is None or reference.postag_replace is None:
                continue
            if reference.postag.count("(") < _max_back_reference(reference.postag_replace):
                failures.append(rule.full_id)
    assert not failures, (
        "Back reference number is greater than existing number of parenthesis: "
        f"{failures}"
    )


# ---------------------------------------------------------------------------
# testMessages
# ---------------------------------------------------------------------------

def test_messages(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#testMessages - 5 failing conditions (3 apply to ``ru``).

    The ``did you mean`` warning and the trailing-``!``/final-punctuation checks
    are guarded upstream by ``lang.getShortCode()`` tests that exclude ``ru``.
    """
    for rule in rules:
        message = _raw_text(rule.message_template.elements).strip()
        assert message, f"Empty message of rule {rule.full_id}"
        if rule.default_off:
            continue
        assert message.lower() not in ("todo", "lorem ipsum"), (
            f"Unfinished message of rule {rule.full_id}: '{message}'"
        )
        assert "tbd" not in message.lower(), (
            f"Unfinished message (contains 'tbd') of rule {rule.full_id}: '{message}'"
        )


# ---------------------------------------------------------------------------
# shortMessageIsLongerThanErrorMessage (inherited AbstractPatternRuleTest @Test)
# ---------------------------------------------------------------------------

def test_short_message_sweep(rules: List[GrammarRule]) -> None:
    """AbstractPatternRuleTest#shortMessageIsLongerThanErrorMessage.

    Upstream only prints warnings, so the executable contract is that every
    pattern rule exposes a readable ``<short>``/``<message>`` pair.  The count of
    rules whose ``<short>`` is not shorter than ``<message>`` is asserted so a
    regression in the loader cannot pass unnoticed.
    """
    not_shorter = []
    with_short = 0
    for rule in rules:
        if rule.short_message is None:
            continue
        with_short += 1
        message = _raw_text(rule.message_template.elements)
        if len(rule.short_message) >= len(message):
            not_shorter.append(rule.full_id)
    assert with_short > 0
    assert not_shorter == [], f"<short> not shorter than <message>: {not_shorter}"


# ---------------------------------------------------------------------------
# testGrammarRulesFromXML - checks not already made by the 2446-example suite
# ---------------------------------------------------------------------------

def test_every_rule_has_incorrect_examples(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#testBadSentences - 'No incorrect examples found.'"""
    missing = [r.full_id for r in rules if not any(e.is_incorrect for e in r.examples)]
    assert missing == [], f"No incorrect examples found for: {missing}"


def test_incorrect_examples_have_marker_and_non_empty_text(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#testBadSentences - marker markup and non-empty sentences."""
    no_marker = []
    empty = []
    for rule in rules:
        for example in rule.examples:
            if example.is_incorrect:
                if not example.marker_spans:
                    no_marker.append(rule.full_id)
                if not example.text.strip():
                    empty.append(rule.full_id)
            elif not example.text.strip():
                empty.append(rule.full_id)
    assert no_marker == [], f"No error position markup in bad example: {no_marker}"
    assert empty == [], f"Empty example sentence after cleaning/trimming: {empty}"


def test_suggestions_do_not_create_errors(
    engine: RussianGrammarEngine,
    rules: List[GrammarRule],
    disambiguator: RussianHybridDisambiguator,
    chunker: RussianChunker,
) -> None:
    """PatternRuleTest#testBadSentences / #assertSuggestionsDoNotCreateErrors.

    Applying any suggested replacement to an incorrect example must not make the
    same rule fire again.
    """
    def check(full_id: str, text: str):
        sentence = disambiguator.disambiguate_text(text)
        sentence.text = text
        chunker.chunk(sentence)
        return engine.check_rule(sentence, full_id)

    checked = 0
    failures = []
    for rule in rules:
        for example in rule.examples:
            if not example.is_incorrect:
                continue
            matches = check(rule.full_id, example.text)
            if not matches or not matches[0].suggestions:
                continue
            match = matches[0]
            for replacement in match.suggestions:
                fixed = example.text[:match.from_pos] + replacement + example.text[match.to_pos:]
                checked += 1
                if check(rule.full_id, fixed):
                    failures.append(
                        f"[{rule.full_id}] correction triggered an error itself: "
                        f"{example.text!r} -> {fixed!r}"
                    )
    assert checked > 900, f"suggestion re-check corpus looks truncated: {checked}"
    assert failures == [], "\n".join(failures)


def test_no_error_triggering_examples_at_the_pin(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#testErrorTriggeringSentences - no ``triggers_error`` in ru.

    The pinned ``ru/grammar.xml`` declares no ``triggers_error`` example, so the
    loop body never executes for Russian.
    """
    from pylat_ru.resources.rules import ru as ru_rules
    from pathlib import Path

    grammar = Path(ru_rules.__file__).parent / "grammar.xml"
    assert "triggers_error" not in grammar.read_text(encoding="utf-8")


def test_run_grammar_rules_from_xml_aggregate(rules: List[GrammarRule]) -> None:
    """PatternRuleTest#runGrammarRulesFromXmlTest / #runGrammarRuleForLanguage /
    #runTestForLanguage - the aggregate entry points.

    Upstream loops over ``Languages.get()``; the Russian module classpath holds
    exactly one non-variant language, so the chain runs ``runTestForLanguage``
    once for Russian.  The executable content of that single run is the set of
    sub-contract tests in this module plus the example suite in
    ``test_russian_grammar_examples.py``.
    """
    assert rules, "no Russian pattern rules were loaded"
    assert all(not r.full_id.startswith("ru-") for r in rules), (
        "no country variant rules exist for Russian at the pin"
    )
