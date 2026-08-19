"""Unit tests for CombiningTagger addition precedence, dictionary fallback, and removal semantics."""

from pylat_ru.tagging.word_tagger import CombiningTagger, ManualTagger, TaggedWord, WordTagger


class DummyWordTagger:
    """Mock word tagger for testing CombiningTagger in isolation."""

    def __init__(self, mapping: dict[str, list[TaggedWord]]) -> None:
        self.mapping = mapping

    def tag(self, word: str) -> tuple[TaggedWord, ...]:
        return tuple(self.mapping.get(word, ()))


def test_combining_tagger_addition_order_and_merging():
    """Verify manual additions come before binary dictionary readings."""
    # tagger1 = base / binary tagger
    base_tagger = DummyWordTagger({
        "тест": [
            TaggedWord(lemma="тест", pos_tag="TAG_BASE_1"),
            TaggedWord(lemma="тест", pos_tag="TAG_BASE_2"),
        ]
    })
    # tagger2 = manual additions
    manual_additions = DummyWordTagger({
        "тест": [
            TaggedWord(lemma="тест", pos_tag="TAG_MANUAL_1"),
        ]
    })

    combining = CombiningTagger(
        tagger1=base_tagger,
        tagger2=manual_additions,
        removal_tagger=None,
        overwrite_with_second=False,
    )

    readings = combining.tag("тест")
    assert len(readings) == 3
    # Manual additions first!
    assert readings[0] == TaggedWord(lemma="тест", pos_tag="TAG_MANUAL_1")
    assert readings[1] == TaggedWord(lemma="тест", pos_tag="TAG_BASE_1")
    assert readings[2] == TaggedWord(lemma="тест", pos_tag="TAG_BASE_2")


def test_combining_tagger_exact_removals():
    """Verify exact (lemma, pos_tag) removals eliminate matching entries from either source."""
    base_tagger = DummyWordTagger({
        "слово": [
            TaggedWord(lemma="слово", pos_tag="TAG_KEEP"),
            TaggedWord(lemma="слово", pos_tag="TAG_REMOVE"),
        ]
    })
    manual_additions = DummyWordTagger({
        "слово": [
            TaggedWord(lemma="база_доп", pos_tag="TAG_EXTRA"),
        ]
    })
    manual_removals = DummyWordTagger({
        "слово": [
            TaggedWord(lemma="слово", pos_tag="TAG_REMOVE"),
        ]
    })

    combining = CombiningTagger(
        tagger1=base_tagger,
        tagger2=manual_additions,
        removal_tagger=manual_removals,
        overwrite_with_second=False,
    )

    readings = combining.tag("слово")
    # TAG_REMOVE is eliminated; TAG_EXTRA and TAG_KEEP survive
    assert readings == (
        TaggedWord(lemma="база_доп", pos_tag="TAG_EXTRA"),
        TaggedWord(lemma="слово", pos_tag="TAG_KEEP"),
    )


def test_combining_tagger_no_silent_deduplication():
    """Verify duplicate readings originating from sources are not silently dropped."""
    base_tagger = DummyWordTagger({
        "слово": [
            TaggedWord(lemma="слово", pos_tag="TAG_A"),
            TaggedWord(lemma="слово", pos_tag="TAG_A"),
        ]
    })
    combining = CombiningTagger(tagger1=base_tagger)
    readings = combining.tag("слово")
    assert len(readings) == 2
    assert readings[0] == readings[1]


def test_combining_tagger_overwrite_flag():
    """Verify overwrite_with_second=True suppresses base tagger if additions are present."""
    base_tagger = DummyWordTagger({
        "слово": [TaggedWord(lemma="слово", pos_tag="TAG_BASE")],
        "другое": [TaggedWord(lemma="другое", pos_tag="TAG_BASE_2")],
    })
    manual_additions = DummyWordTagger({
        "слово": [TaggedWord(lemma="слово", pos_tag="TAG_MANUAL")],
    })

    combining = CombiningTagger(
        tagger1=base_tagger,
        tagger2=manual_additions,
        overwrite_with_second=True,
    )

    # For 'слово', manual exists, so base is overwritten
    assert combining.tag("слово") == (TaggedWord(lemma="слово", pos_tag="TAG_MANUAL"),)
    # For 'другое', manual is empty, so base is returned
    assert combining.tag("другое") == (TaggedWord(lemma="другое", pos_tag="TAG_BASE_2"),)
