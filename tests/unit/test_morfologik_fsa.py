"""tests/unit/test_morfologik_fsa.py

Unit tests for Morfologik FSA reader and traversal (CFSA2).
"""

from pathlib import Path
import pytest

from pylat_ru.morfologik.errors import CorruptedFSAError, UnsupportedFSAFormatError
from pylat_ru.morfologik.fsa import CFSA2, read_fsa

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


def test_truncated_fsa_header():
    """Verify truncated data raises CorruptedFSAError."""
    with pytest.raises(CorruptedFSAError, match="Truncated FSA"):
        read_fsa(b"\\fs")

    with pytest.raises(CorruptedFSAError, match="Truncated FSA label mapping table"):
        read_fsa(b"\\fsa\xc6\x00\x07\x20\x00\x01\x02")  # claims 32 mapping size, only provides 3 bytes


def test_fsa_out_of_bounds_arc():
    """Verify reading out of bounds arc raises CorruptedFSAError."""
    # Construct a minimal CFSA2 with invalid arc goto
    mapping = b"\x00" * 32
    # Flag: 0x20 (FINAL), goto: points to offset 99999 (out of bounds)
    arcs = bytes([0x20, ord('a'), 0xFF, 0xFF, 0x05])
    with pytest.raises(CorruptedFSAError, match="out of bounds"):
        CFSA2(arcs=arcs, flags=0x0007, label_mapping=mapping, source_name="test_corrupt")

