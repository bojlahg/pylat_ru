"""tests/unit/test_morfologik_fsa.py

Unit tests for Morfologik FSA reader, traversal, and sequence ordering (CFSA2).
"""

from pathlib import Path
import pytest

from pylat_ru.morfologik.errors import CorruptedFSAError, UnsupportedFSAFormatError
from pylat_ru.morfologik.fsa import CFSA2, ByteSequenceIterator, read_fsa

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
RU_RESOURCE_DIR = (
    REPO_ROOT
    / "third_party"
    / "languagetool"
    / "languagetool-language-modules"
    / "ru"
    / "src"
    / "main"
    / "resources"
    / "org"
    / "languagetool"
    / "resource"
    / "ru"
)


def test_read_real_russian_fsa():
    """Verify opening real russian.dict produces a valid CFSA2 instance."""
    dict_path = RU_RESOURCE_DIR / "russian.dict"
    fsa = read_fsa(dict_path)
    assert isinstance(fsa, CFSA2)
    assert fsa.get_root_node() > 0
    assert len(fsa.arcs) > 1_000_000


def test_read_real_russian_synth_fsa():
    """Verify opening real russian_synth.dict produces a valid CFSA2 instance."""
    synth_path = RU_RESOURCE_DIR / "russian_synth.dict"
    fsa = read_fsa(synth_path)
    assert isinstance(fsa, CFSA2)
    assert fsa.get_root_node() > 0


def test_invalid_magic_header():
    """Verify invalid magic header raises UnsupportedFSAFormatError."""
    corrupt_data = b"XYZ!\xc6\x00\x07 \x00" + b"\x00" * 32
    with pytest.raises(UnsupportedFSAFormatError, match="Invalid FSA magic header"):
        read_fsa(corrupt_data)


def test_unsupported_fsa_version():
    """Verify unsupported version (e.g. FSA5 0x05 or CFSA v1 0xC5) raises UnsupportedFSAFormatError."""
    # FSA5 version 0x05
    data_v5 = b"\\fsa\x05\x00\x07 \x00" + b"\x00" * 32
    with pytest.raises(UnsupportedFSAFormatError, match="Unsupported FSA version 0x05"):
        read_fsa(data_v5)

    # CFSA v1 version 0xC5
    data_vc5 = b"\\fsa\xc5\x00\x07 \x00" + b"\x00" * 32
    with pytest.raises(UnsupportedFSAFormatError, match="Unsupported FSA version 0xc5"):
        read_fsa(data_vc5)


def test_unsupported_and_invalid_fsa_flags():
    """Verify NUMBERS (0x0008) and other unsupported/unknown flags raise UnsupportedFSAFormatError."""
    # Flag with NUMBERS bit (0x0008)
    data_numbers = b"\\fsa\xc6\x00\x0f\x00"  # flags 0x000F (0x0007 | 0x0008)
    with pytest.raises(UnsupportedFSAFormatError, match="NUMBERS.*unsupported"):
        read_fsa(data_numbers + b"\x00" * 10)

    # Flag with unknown/unsupported bit (0x0010)
    data_unknown = b"\\fsa\xc6\x00\x17\x00"  # flags 0x0017
    with pytest.raises(UnsupportedFSAFormatError, match="Unsupported FSA flags"):
        read_fsa(data_unknown + b"\x00" * 10)

    # Direct constructor check
    with pytest.raises(UnsupportedFSAFormatError, match="NUMBERS.*unsupported"):
        CFSA2(arcs=b"\x00"*10, flags=0x000F, label_mapping=b"", source_name="test_numbers")

    with pytest.raises(UnsupportedFSAFormatError, match="Unsupported FSA flags"):
        CFSA2(arcs=b"\x00"*10, flags=0x8000, label_mapping=b"", source_name="test_unknown")


def test_truncated_fsa_header():
    """Verify truncated data raises CorruptedFSAError."""
    with pytest.raises(CorruptedFSAError, match="Truncated FSA"):
        read_fsa(b"\\fs")

    with pytest.raises(CorruptedFSAError, match="Truncated FSA label mapping table"):
        read_fsa(b"\\fsa\xc6\x00\x07\x20\x00\x01\x02")  # claims 32 mapping size, only provides 3 bytes


def test_fsa_out_of_bounds_arc():
    """Verify reading out of bounds arc raises CorruptedFSAError."""
    mapping = b"\x00" * 32
    # Flag: 0x20 (FINAL), goto: points to offset 99999 (out of bounds)
    arcs = bytes([0x20, ord('a'), 0xFF, 0xFF, 0x05])
    with pytest.raises(CorruptedFSAError, match="out of bounds"):
        CFSA2(arcs=arcs, flags=0x0007, label_mapping=mapping, source_name="test_corrupt")


def test_synthetic_fsa_traversal_order():
    """Verify exact Morfologik ByteSequenceIterator DFS traversal order (distinguishing sibling vs final vs child).

    Tree structure:
    Root -> Arc 'a' (FINAL, goto State 2) -> Arc 'c' (FINAL, LAST, goto 0 / terminal)
    State 2 (child of 'a') -> Arc 'b' (FINAL, LAST, goto 0 / terminal)

    Expected Morfologik DFS sequence:
    1. 'a' (root arc 1 is final)
    2. 'ab' (descends to child of 'a' before sibling 'c')
    3. 'c' (sibling arc 2 processed after child subtree of 'a' is exhausted)
    """
    mapping = b""
    arcs = bytes([
        0xC0, ord("_"),        # offset 0: epsilon arc -> target next (offset 2)
        0x20, ord("a"), 0x08,  # offset 2: arc 'a' (final, goto offset 8)
        0x60, ord("c"), 0x00,  # offset 5: arc 'c' (final, last, terminal goto 0)
        0x60, ord("b"), 0x00,  # offset 8: arc 'b' (final, last, terminal goto 0)
    ])

    fsa = CFSA2(arcs=arcs, flags=0x0007, label_mapping=mapping, source_name="synthetic_order_test")
    seqs = [s.decode("ascii") for s in fsa.get_sequences()]
    assert seqs == ["a", "ab", "c"], f"Expected ['a', 'ab', 'c'], got {seqs}"
