"""tests/unit/test_morfologik_sequence_encoder.py

Unit tests for Morfologik SUFFIX sequence encoder and decoder.
"""

import pytest

from pylat_ru.morfologik.errors import MalformedSequenceError
from pylat_ru.morfologik.sequence_encoder import TrimSuffixEncoder


def test_suffix_decode_examples():
    """Verify Morfologik Javadoc examples for TrimSuffixEncoder."""
    encoder = TrimSuffixEncoder()

    # src: foo, encoded: Abar -> foobar (cut 0 bytes, append 'bar')
    res1 = encoder.decode(b"foo", b"Abar")
    assert res1 == b"foobar"

    # src: foo, encoded: Dbar -> bar (cut 3 bytes ('D' - 'A' = 3), append 'bar')
    res2 = encoder.decode(b"foo", b"Dbar")
    assert res2 == b"bar"

    # src: testing, encoded: B -> testin (cut 1 byte ('B' - 'A' = 1), append '')
    res3 = encoder.decode(b"testing", b"B")
    assert res3 == b"testin"


def test_suffix_encode_decode_roundtrip():
    """Verify encode followed by decode returns the target bytes exactly."""
    encoder = TrimSuffixEncoder()

    pairs = [
        (b"foo", b"foobar"),
        (b"foo", b"bar"),
        (b"walked", b"walk"),
        (b"running", b"run"),
        (b"abc", b"abc"),
        (b"", b"hello"),
        (b"hello", b""),
        ("семьи".encode("koi8-r"), "семья".encode("koi8-r")),
        ("счастливые".encode("koi8-r"), "счастливый".encode("koi8-r")),
    ]

    for src, dst in pairs:
        encoded = encoder.encode(src, dst)
        decoded = encoder.decode(src, encoded)
        assert decoded == dst, f"Failed roundtrip for {src} -> {dst}"


def test_suffix_remove_everything():
    """Verify trim code corresponding to 255 removes the full source."""
    encoder = TrimSuffixEncoder()
    # 255 + ord('A') = 320 -> byte value (320 & 0xFF) = 64 ('@') or encoded with REMOVE_EVERYTHING (255)
    # If trimCode - 'A' == 255:
    trim_code = (255 + ord("A")) & 0xFF
    encoded = bytes([trim_code]) + b"replacement"
    decoded = encoder.decode(b"arbitrary_long_word", encoded)
    assert decoded == b"replacement"


def test_malformed_sequence_errors():
    """Verify malformed transformation instructions raise MalformedSequenceError."""
    encoder = TrimSuffixEncoder()

    # Empty encoded sequence
    with pytest.raises(MalformedSequenceError, match="empty"):
        encoder.decode(b"word", b"")

    # Trim code asking to trim 10 bytes from a 3-byte word: 'K' - 'A' = 10
    with pytest.raises(MalformedSequenceError, match="attempts to truncate 10 bytes from source of length 3"):
        encoder.decode(b"abc", b"Ksuffix")
