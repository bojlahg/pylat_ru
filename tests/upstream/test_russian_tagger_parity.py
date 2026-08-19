"""Upstream parity tests for RussianTagger comparing against Java LanguageTool v6.8."""

import json
from pathlib import Path
import pytest

from pylat_ru.tagging.russian import RussianTagger
from pylat_ru.tokenization.word import RussianWordTokenizer


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_PATH = REPO_ROOT / "tests" / "fixtures" / "oracle_russian_tagger.json"


def test_upstream_russian_tagger_test_suite():
    """Port of LanguageTool RussianTaggerTest.java unit test cases."""
    tagger = RussianTagger()
    tokenizer = RussianWordTokenizer()

    # Case 1: Tolstoy quote
    text1 = "Все счастливые семьи похожи друг на друга,  каждая  несчастливая  семья несчастлива по-своему."
    tokens1 = [t for t in tokenizer.tokenize(text1) if t.strip()]
    atrs1 = tagger.tag(tokens1)
    
    # Check readings for each word
    token_map = {atr.token: atr for atr in atrs1}
    
    assert token_map["Все"].has_lemma("весь")
    assert token_map["Все"].has_lemma("все")
    assert token_map["Все"].has_pos_tag("ADJ:MPR:PL:Nom")
    assert "MayMissingYO" in token_map["Все"].chunk_tags

    assert token_map["счастливые"].has_lemma("счастливый")
    assert token_map["счастливые"].has_pos_tag("ADJ:Posit:PL:Nom")

    assert token_map["семьи"].has_lemma("семья")
    assert len(token_map["семьи"].readings) == 3

    assert token_map["похожи"].has_lemma("похожий")
    assert token_map["похожи"].has_pos_tag("ADJ:Short:PL")

    assert token_map["друг"].has_lemma("друг")
    assert token_map["друг"].has_pos_tag("NN:Anim:Masc:Sin:Nom")

    assert token_map["на"].has_pos_tag("PREP")

    assert token_map["друга"].has_lemma("друг")
    assert len(token_map["друга"].readings) == 2

    assert token_map["каждая"].has_lemma("каждый")
    assert token_map["каждая"].has_pos_tag("ADJ:MPR:Fem:Nom")

    assert token_map["несчастливая"].has_lemma("несчастливый")
    assert token_map["несчастливая"].has_pos_tag("ADJ:Posit:Fem:Nom")

    assert token_map["семья"].has_lemma("семья")
    assert token_map["семья"].has_pos_tag("NN:Inanim:Fem:Sin:Nom")

    assert token_map["несчастлива"].has_lemma("несчастливый")
    assert token_map["несчастлива"].has_pos_tag("ADJ:Short:Fem")

    assert token_map["по-своему"].has_lemma("по-своему")
    assert token_map["по-своему"].has_pos_tag("ADV")

    # Case 2: Oblonsky quote
    text2 = "Все смешалось в доме Облонских."
    tokens2 = [t for t in tokenizer.tokenize(text2) if t.strip()]
    atrs2 = tagger.tag(tokens2)
    token_map2 = {atr.token: atr for atr in atrs2}

    assert token_map2["смешалось"].has_lemma("смешаться")
    assert token_map2["смешалось"].has_pos_tag("VB:Past:INTR:PFV:Neut")
    assert token_map2["в"].has_pos_tag("PREP")
    assert token_map2["доме"].has_lemma("дом")
    assert token_map2["доме"].has_pos_tag("NN:Inanim:Masc:Sin:P")
    assert token_map2["Облонских"].is_pos_tag_unknown is True

    # Case 3: Abdullaevy (manual additions)
    atrs3 = tagger.tag(["Абдуллаевы"])
    assert len(atrs3) == 1
    assert atrs3[0].token == "Абдуллаевы"
    assert atrs3[0].has_lemma("абдуллаев")
    assert atrs3[0].has_pos_tag("NN:Fam:PL:Nom")

    # Case 4: Blukat (trailing colon VB:INF:)
    atrs4 = tagger.tag(["блукать"])
    assert len(atrs4) == 1
    assert atrs4[0].token == "блукать"
    assert atrs4[0].has_lemma("блукать")
    assert atrs4[0].has_pos_tag("VB:INF:")


def test_oracle_russian_tagger_fixture_exact_parity():
    """Verify 100% exact parity against all committed Java LanguageTool oracle tagger cases."""
    assert FIXTURE_PATH.is_file(), f"Missing fixture: {FIXTURE_PATH}"
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    tagger = RussianTagger()

    for case in fixture["cases"]:
        cid = case["id"]
        input_tokens = case["input_tokens"]
        expected_tokens = case["expected_tokens"]

        actual_atrs = tagger.tag(input_tokens)
        assert len(actual_atrs) == len(expected_tokens), (
            f"Case {cid}: token count mismatch {len(actual_atrs)} != {len(expected_tokens)}"
        )

        for i, (actual, expected) in enumerate(zip(actual_atrs, expected_tokens)):
            # 1. UTF-16 start position parity
            assert actual.start_pos == expected["start_pos_utf16"], (
                f"Case {cid}[{i}]: start_pos {actual.start_pos} != {expected['start_pos_utf16']}"
            )

            # 2. Chunk tags parity
            assert list(actual.chunk_tags) == expected["chunk_tags"], (
                f"Case {cid}[{i}]: chunk_tags {actual.chunk_tags} != {expected['chunk_tags']}"
            )

            # 3. Readings count parity
            assert len(actual.readings) == len(expected["readings"]), (
                f"Case {cid}[{i}] ({actual.token}): readings count {len(actual.readings)} != {len(expected['readings'])}"
            )

            # 4. Exact reading field parity (token, lemma, raw pos_tag) and exact sequence order
            for r_idx, (r_act, r_exp) in enumerate(zip(actual.readings, expected["readings"])):
                assert r_act.token == r_exp["token"], (
                    f"Case {cid}[{i}].readings[{r_idx}]: token {r_act.token} != {r_exp['token']}"
                )
                assert r_act.lemma == r_exp["lemma"], (
                    f"Case {cid}[{i}].readings[{r_idx}]: lemma {r_act.lemma} != {r_exp['lemma']}"
                )
                assert r_act.pos_tag == r_exp["pos_tag"], (
                    f"Case {cid}[{i}].readings[{r_idx}]: pos_tag {r_act.pos_tag} != {r_exp['pos_tag']}"
                )


def test_real_resource_manual_addition_and_removal():
    """Verify specific manual additions and removals from real pinned added.txt and removed.txt."""
    tagger = RussianTagger()

    # Manual addition: 'обозревателей' from added.txt
    res_add = tagger.tag_word("обозревателей")
    assert any(r.lemma == "обозреватель" and r.pos_tag == "NN:Inanim:Masc:PL:R" for r in res_add.readings)
    assert any(r.lemma == "обозреватель" and r.pos_tag == "NN:Inanim:Masc:PL:V" for r in res_add.readings)

    # Manual removal: in removed.txt 'неуверена' has removal entry 'неуверена\tнеуверенный\tADJ:Short:Fem'
    res_rem = tagger.tag_word("неуверена")
    # Must not contain the removed short-form reading
    assert not any(r.lemma == "неуверенный" and r.pos_tag == "ADJ:Short:Fem" for r in res_rem.readings)
