"""src/pylat_ru/morfologik/sequence_encoder.py

Morfologik sequence encoders/decoders (SUFFIX, etc.).
"""

from __future__ import annotations

from typing import Protocol

from pylat_ru.morfologik.errors import MalformedSequenceError


class SequenceEncoder(Protocol):
    """Protocol for Morfologik sequence encoders/decoders."""

    def prefix_bytes(self) -> int:
        """Return the number of leading instruction/prefix bytes before the tag."""
        ...

    def decode(self, source: bytes, encoded: bytes) -> bytes:
        """Decode target/stem bytes given the inflected source bytes and encoded transformation bytes."""
        ...

    def encode(self, source: bytes, target: bytes) -> bytes:
        """Encode transformation bytes to turn source bytes into target bytes."""
        ...


class TrimSuffixEncoder:
    """Morfologik SUFFIX sequence encoder/decoder.

    Encodes `target` relative to `source` by trimming whatever non-equal suffix `source` has.
    The encoded format is:
        {trimCode}{suffix}
    where (trimCode - 'A') bytes should be trimmed from the end of `source`, and then
    `suffix` is appended to the resulting byte sequence.
    If trimCode - 'A' == 255 (or 0xFF), the entire source is removed.
    """

    REMOVE_EVERYTHING = 255

    def prefix_bytes(self) -> int:
        return 1

    def decode(self, source: bytes, encoded: bytes) -> bytes:
        if not encoded:
            raise MalformedSequenceError("Encoded sequence is empty; expected at least 1 trim code byte.")

        trim_code = encoded[0]
        truncate_bytes = (trim_code - ord("A")) & 0xFF
        if truncate_bytes == self.REMOVE_EVERYTHING:
            truncate_bytes = len(source)
        elif truncate_bytes > len(source):
            raise MalformedSequenceError(
                f"Invalid trim code 0x{trim_code:02x} ('{chr(trim_code) if 32 <= trim_code <= 126 else '?'}'): "
                f"attempts to truncate {truncate_bytes} bytes from source of length {len(source)}"
            )

        keep_len = len(source) - truncate_bytes
        return source[:keep_len] + encoded[1:]

    def encode(self, source: bytes, target: bytes) -> bytes:
        # Find shared prefix length
        max_prefix = min(len(source), len(target))
        shared = 0
        while shared < max_prefix and source[shared] == target[shared]:
            shared += 1

        truncate_bytes = len(source) - shared
        if truncate_bytes >= self.REMOVE_EVERYTHING:
            truncate_bytes = self.REMOVE_EVERYTHING
            shared = 0

        trim_code = (truncate_bytes + ord("A")) & 0xFF
        return bytes([trim_code]) + target[shared:]


def get_sequence_encoder(encoder_name: str) -> SequenceEncoder:
    """Retrieve sequence encoder instance by name."""
    upper = encoder_name.strip().upper()
    if upper == "SUFFIX":
        return TrimSuffixEncoder()
    raise ValueError(f"Unknown sequence encoder: '{encoder_name}'")
