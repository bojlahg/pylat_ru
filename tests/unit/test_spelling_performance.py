"""Deterministic performance and resource-safety sanity checks for native spelling.

These are architectural guards, not benchmarks: they prove the dictionary is
loaded once, that correct words are answered by indexed FSA lookups rather than
a dictionary scan, that suggestion caches stay bounded, and that no subprocess
or socket is used while checking.
"""

from __future__ import annotations

import socket
import subprocess
import time

import pytest

from pylat_ru import LanguageToolRU
from pylat_ru.spelling import (
    RussianSpeller,
    RussianYoSpeller,
    SpellerToken,
    load_binary_dictionary,
)


@pytest.fixture(scope="module")
def speller() -> RussianSpeller:
    rule = RussianSpeller()
    rule._init()
    return rule


def _tokens(words: list[str]) -> list[SpellerToken]:
    position = 0
    tokens = []
    for word in words:
        tokens.append(SpellerToken(token=word, clean_token=word, start_pos=position))
        position += len(word) + 1
    return tokens


def test_binary_dictionaries_are_loaded_once_and_shared() -> None:
    first = load_binary_dictionary("ru_RU")
    assert load_binary_dictionary("ru_RU") is first
    assert load_binary_dictionary("ru_RU_yo") is not first
    # Two rule instances must not reload the 1.8 MB automaton.
    assert RussianSpeller().speller1.spellers[0].dictionary is first
    assert RussianYoSpeller().speller1.spellers[0].dictionary is load_binary_dictionary("ru_RU_yo")


def test_long_correct_paragraph_is_fast(speller: RussianSpeller) -> None:
    tokens = _tokens(["слово"] * 400)
    started = time.perf_counter()
    assert speller.match(tokens) == []
    assert time.perf_counter() - started < 5.0


def test_repeated_checks_reuse_cached_state(speller: RussianSpeller) -> None:
    tokens = _tokens(["каждя", "превет"])
    first = speller.match(tokens)
    started = time.perf_counter()
    second = speller.match(_tokens(["каждя", "превет"]))
    elapsed = time.perf_counter() - started
    assert [m.suggestions for m in first] == [m.suggestions for m in second]
    assert elapsed < 1.0


def test_suggestion_generation_is_bounded(speller: RussianSpeller) -> None:
    started = time.perf_counter()
    matches = speller.match(_tokens(["ыфвацйщшгн"]))
    assert time.perf_counter() - started < 30.0
    assert len(matches) == 1


def test_default_suggestion_cache_does_not_grow_without_bound(speller: RussianSpeller) -> None:
    multi = speller.speller1
    for index in range(2100):
        multi.get_suggestions_from_default_dicts(f"ыфв{index}")
    assert len(multi._default_suggestion_cache) <= 2000


def test_speller_state_is_not_shared_across_configurations() -> None:
    default = RussianSpeller(conf_ru_value=0)
    latin = RussianSpeller(conf_ru_value=1)
    tokens = _tokens(["wordd"])
    assert default.match(tokens) == []
    assert len(latin.match(_tokens(["wordd"]))) == 1
    # The first rule must not have been affected by the second one's config.
    assert default.match(_tokens(["wordd"])) == []


def test_check_uses_no_subprocess_or_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("production check must not spawn processes or sockets")

    monkeypatch.setattr(subprocess, "run", _forbidden)
    monkeypatch.setattr(subprocess, "Popen", _forbidden)
    monkeypatch.setattr(socket, "socket", _forbidden)
    monkeypatch.setattr(socket, "create_connection", _forbidden)

    tool = LanguageToolRU()
    matches = tool.check("каждя несчастливая семья.")
    assert any(m.rule_id == "MORFOLOGIK_RULE_RU_RU" for m in matches)
