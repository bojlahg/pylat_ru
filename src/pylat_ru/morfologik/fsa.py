"""src/pylat_ru/morfologik/fsa.py

Native Python finite state automaton (FSA) reader and traversal engine.
Implements Morfologik CFSA2 (Compact Finite State Automaton version 2, magic '\\fsa', version 0xc6).
"""

from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Iterator, List, Optional, Tuple, Union

from pylat_ru.morfologik.errors import CorruptedFSAError, UnsupportedFSAFormatError

# FSA File Header Magic: '\' 'f' 's' 'a' (0x5c, 0x66, 0x73, 0x61)
FSA_MAGIC = b"\\fsa"

# Match result kinds (matching Morfologik MatchResult)
NO_MATCH = 0
EXACT_MATCH = 1
AUTOMATON_HAS_PREFIX = 2
SEQUENCE_IS_A_PREFIX = 3

# Supported FSA flags for CFSA2
FLAG_FLEXIBLE = 1 << 0  # 0x0001
FLAG_STOPBIT = 1 << 1   # 0x0002
FLAG_NEXTBIT = 1 << 2   # 0x0004
FLAG_NUMBERS = 1 << 3   # 0x0008 (intentionally unsupported)
SUPPORTED_FLAGS = FLAG_FLEXIBLE | FLAG_STOPBIT | FLAG_NEXTBIT  # 0x0007


class FSA(ABC):
    """Abstract base class for Finite State Automata."""

    @abstractmethod
    def get_root_node(self) -> int:
        """Return the root node offset of the automaton."""
        ...

    @abstractmethod
    def get_first_arc(self, node: int) -> int:
        """Return the first outgoing arc offset for a given node, or 0 if none."""
        ...

    @abstractmethod
    def get_next_arc(self, arc: int) -> int:
        """Return the next sibling arc offset for a given arc, or 0 if this is the last arc."""
        ...

    @abstractmethod
    def get_arc(self, node: int, label: int) -> int:
        """Return the arc labeled with `label` leaving `node`, or 0 if not found."""
        ...

    @abstractmethod
    def get_arc_label(self, arc: int) -> int:
        """Return the byte label (0-255) of an arc."""
        ...

    @abstractmethod
    def is_arc_final(self, arc: int) -> bool:
        """Return True if this arc corresponds to a sequence ending (accepting transition)."""
        ...

    @abstractmethod
    def is_arc_terminal(self, arc: int) -> bool:
        """Return True if this arc has no destination node representation."""
        ...

    @abstractmethod
    def get_end_node(self, arc: int) -> int:
        """Return the destination node offset for an arc."""
        ...

    @abstractmethod
    def get_sequences(self, node: Optional[int] = None) -> Iterator[bytes]:
        """Iterate over all suffix byte sequences reachable from a node in Morfologik DFS order."""
        ...


class ByteSequenceIterator(Iterator[bytes]):
    """Traverse all suffix sequences reachable from a node in exact Morfologik DFS order."""

    def __init__(self, fsa: FSA, node: Optional[int] = None) -> None:
        self.fsa = fsa
        self.arcs: List[int] = []
        self.buffer = bytearray()
        self.position = 0
        start = fsa.get_root_node() if node is None else node
        if start != 0 and fsa.get_first_arc(start) != 0:
            self._push_node(start)

    def _push_node(self, node: int) -> None:
        first_arc = self.fsa.get_first_arc(node)
        if self.position == len(self.arcs):
            self.arcs.append(first_arc)
            self.buffer.append(0)
        else:
            self.arcs[self.position] = first_arc
        self.position += 1

    def __iter__(self) -> Iterator[bytes]:
        return self

    def __next__(self) -> bytes:
        while self.position > 0:
            last_index = self.position - 1
            arc = self.arcs[last_index]

            if arc == 0:
                self.position -= 1
                continue

            self.arcs[last_index] = self.fsa.get_next_arc(arc)

            if last_index >= len(self.buffer):
                self.buffer.extend([0] * (last_index - len(self.buffer) + 1))
            self.buffer[last_index] = self.fsa.get_arc_label(arc)

            if not self.fsa.is_arc_terminal(arc):
                self._push_node(self.fsa.get_end_node(arc))

            if self.fsa.is_arc_final(arc):
                return bytes(self.buffer[:last_index + 1])

        raise StopIteration


class CFSA2(FSA):
    """Compact Finite State Automaton version 2 implementation (0xC6).

    Features:
    - 31 most frequent labels mapped into arc flags byte.
    - Variable-byte encoded (v-int) goto offsets.
    - Compact arc representation.
    """

    VERSION = 0xC6

    BIT_TARGET_NEXT = 1 << 7  # 0x80
    BIT_LAST_ARC = 1 << 6     # 0x40
    BIT_FINAL_ARC = 1 << 5    # 0x20
    LABEL_INDEX_MASK = (1 << 5) - 1  # 0x1F (31)

    def __init__(
        self,
        arcs: bytes,
        flags: int,
        label_mapping: bytes,
        source_name: str = "<memory>",
    ) -> None:
        # Validate flags explicitly against supported boundary
        if (flags & FLAG_NUMBERS) != 0:
            raise UnsupportedFSAFormatError(
                f"FSA flag NUMBERS (0x0008, perfect hashing) in {source_name} is unsupported."
            )
        if flags != SUPPORTED_FLAGS:
            raise UnsupportedFSAFormatError(
                f"Unsupported FSA flags 0x{flags:04x} in {source_name}. Supported flags: 0x{SUPPORTED_FLAGS:04x}."
            )

        self.arcs = arcs
        self.flags = flags
        self.label_mapping = label_mapping
        self.source_name = source_name
        self._arcs_len = len(arcs)
        self._root_node = self._init_root_node()

    def _init_root_node(self) -> int:
        if self._arcs_len == 0:
            return 0
        first_arc = self.get_first_arc(0)
        return self.get_destination_node_offset(first_arc)

    def get_root_node(self) -> int:
        return self._root_node

    def _check_bounds(self, offset: int, length: int = 1) -> None:
        if offset < 0 or (offset + length) > self._arcs_len:
            raise CorruptedFSAError(
                f"FSA arc offset out of bounds in {self.source_name}: offset={offset}, "
                f"len={length}, total_arcs={self._arcs_len}"
            )

    def _read_vint(self, offset: int) -> Tuple[int, int]:
        """Read a variable-length integer starting at `offset`.

        Returns:
            (value, next_offset)
        """
        self._check_bounds(offset, 1)
        b = self.arcs[offset]
        val = b & 0x7F
        shift = 7
        curr = offset + 1
        while b & 0x80:
            self._check_bounds(curr, 1)
            b = self.arcs[curr]
            val |= (b & 0x7F) << shift
            shift += 7
            curr += 1
            if shift > 35:
                raise CorruptedFSAError(
                    f"Corrupted v-int encoding at offset {offset} in {self.source_name}"
                )
        return val, curr

    def _skip_vint(self, offset: int) -> int:
        """Skip a variable-length integer starting at `offset` and return the offset right after it."""
        self._check_bounds(offset, 1)
        curr = offset
        while self.arcs[curr] & 0x80:
            curr += 1
            self._check_bounds(curr, 1)
        return curr + 1

    def get_first_arc(self, node: int) -> int:
        return node

    def is_arc_last(self, arc: int) -> bool:
        self._check_bounds(arc, 1)
        return bool(self.arcs[arc] & self.BIT_LAST_ARC)

    def is_next_set(self, arc: int) -> bool:
        self._check_bounds(arc, 1)
        return bool(self.arcs[arc] & self.BIT_TARGET_NEXT)

    def is_arc_final(self, arc: int) -> bool:
        self._check_bounds(arc, 1)
        return bool(self.arcs[arc] & self.BIT_FINAL_ARC)

    def is_arc_terminal(self, arc: int) -> bool:
        return self.get_destination_node_offset(arc) == 0

    def get_arc_label(self, arc: int) -> int:
        self._check_bounds(arc, 1)
        flag = self.arcs[arc]
        idx = flag & self.LABEL_INDEX_MASK
        if idx > 0:
            if idx >= len(self.label_mapping):
                raise CorruptedFSAError(
                    f"Invalid label index {idx} >= {len(self.label_mapping)} at arc {arc} in {self.source_name}"
                )
            return self.label_mapping[idx]
        self._check_bounds(arc + 1, 1)
        return self.arcs[arc + 1]

    def _skip_arc(self, offset: int) -> int:
        self._check_bounds(offset, 1)
        flag = self.arcs[offset]
        curr = offset + 1
        # Explicit label follows if index is 0
        if (flag & self.LABEL_INDEX_MASK) == 0:
            curr += 1
        # Explicit goto follows if TARGET_NEXT is not set
        if (flag & self.BIT_TARGET_NEXT) == 0:
            curr = self._skip_vint(curr)
        self._check_bounds(curr, 0)
        return curr

    def get_next_arc(self, arc: int) -> int:
        if self.is_arc_last(arc):
            return 0
        return self._skip_arc(arc)

    def get_destination_node_offset(self, arc: int) -> int:
        self._check_bounds(arc, 1)
        if self.is_next_set(arc):
            # Target node follows the last arc of this state
            curr = arc
            while not self.is_arc_last(curr):
                curr = self.get_next_arc(curr)
                if curr == 0:
                    raise CorruptedFSAError(f"Unexpected end of arc chain at arc {arc} in {self.source_name}")
            return self._skip_arc(curr)
        else:
            # Target node address is v-int encoded
            flag = self.arcs[arc]
            vint_offset = arc + (1 if (flag & self.LABEL_INDEX_MASK) > 0 else 2)
            dest, _ = self._read_vint(vint_offset)
            if dest != 0 and dest >= self._arcs_len:
                raise CorruptedFSAError(
                    f"Destination node offset {dest} out of bounds (len={self._arcs_len}) at arc {arc}"
                )
            return dest

    def get_end_node(self, arc: int) -> int:
        dest = self.get_destination_node_offset(arc)
        if dest == 0:
            raise CorruptedFSAError(f"Cannot follow terminal arc at offset {arc}")
        return dest

    def get_arc(self, node: int, label: int) -> int:
        """Find the arc leaving `node` with the given `label` (0-255)."""
        arc = self.get_first_arc(node)
        while arc != 0:
            if self.get_arc_label(arc) == label:
                return arc
            arc = self.get_next_arc(arc)
        return 0

    def match(
        self,
        sequence: bytes,
        start_node: Optional[int] = None,
    ) -> Tuple[int, int, int]:
        """Match a sequence of bytes against the automaton starting at `start_node`.

        Returns:
            (match_kind, matched_length, last_node)
        """
        node = self._root_node if start_node is None else start_node
        if node == 0:
            return NO_MATCH, 0, node

        seq_len = len(sequence)
        for i in range(seq_len):
            arc = self.get_arc(node, sequence[i])
            if arc != 0:
                if i + 1 == seq_len and self.is_arc_final(arc):
                    return EXACT_MATCH, i + 1, node
                if self.is_arc_terminal(arc):
                    return AUTOMATON_HAS_PREFIX, i + 1, node
                node = self.get_destination_node_offset(arc)
            else:
                if i > 0:
                    return AUTOMATON_HAS_PREFIX, i, node
                return NO_MATCH, 0, node

        return SEQUENCE_IS_A_PREFIX, seq_len, node

    def get_sequences(self, node: Optional[int] = None) -> Iterator[bytes]:
        """Iterate over all suffix sequences reachable from `node` in exact Morfologik DFS order."""
        return ByteSequenceIterator(self, node)


def read_fsa(source: Union[bytes, BinaryIO, Path, str]) -> FSA:
    """Factory function to read and instantiate an FSA from bytes, a binary stream, or file path."""
    data: bytes
    source_name = "<bytes>"
    if isinstance(source, (str, Path)):
        source_path = Path(source)
        source_name = str(source_path)
        if not source_path.is_file():
            raise CorruptedFSAError(f"FSA dictionary file not found: {source_path}")
        with open(source_path, "rb") as f:
            data = f.read()
    elif hasattr(source, "read"):
        source_name = getattr(source, "name", "<stream>")
        data = source.read()
    elif isinstance(source, bytes):
        data = source
    else:
        raise TypeError(f"Unsupported source type for read_fsa: {type(source)}")

    # Header check: at least 8 bytes for magic + version + flags + mapping size
    if len(data) < 8:
        raise CorruptedFSAError(f"Truncated FSA file {source_name}: size {len(data)} < 8 bytes header")

    if data[:4] != FSA_MAGIC:
        raise UnsupportedFSAFormatError(
            f"Invalid FSA magic header in {source_name}: expected {FSA_MAGIC!r}, got {data[:4]!r}"
        )

    version = data[4]
    if version != CFSA2.VERSION:
        raise UnsupportedFSAFormatError(
            f"Unsupported FSA version 0x{version:02x} in {source_name}. Supported version: 0x{CFSA2.VERSION:02x} (CFSA2)"
        )

    flags = struct.unpack(">H", data[5:7])[0]
    mapping_size = data[7]
    if len(data) < 8 + mapping_size:
        raise CorruptedFSAError(
            f"Truncated FSA label mapping table in {source_name}: expected {mapping_size} bytes"
        )

    label_mapping = data[8:8 + mapping_size]
    arcs = data[8 + mapping_size:]

    return CFSA2(
        arcs=arcs,
        flags=flags,
        label_mapping=label_mapping,
        source_name=source_name,
    )
