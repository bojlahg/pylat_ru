"""src/pylat_ru/morfologik/fsa.py

Native Python finite state automaton (FSA) reader and traversal engine.
Implements Morfologik CFSA2 (Compact Finite State Automaton version 2, magic '\fsa', version 0xc6).
"""

from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO, Iterator, List, Optional, Set, Tuple, Union

from pylat_ru.morfologik.errors import CorruptedFSAError, UnsupportedFSAFormatError

# FSA File Header Magic: '\' 'f' 's' 'a' (0x5c, 0x66, 0x73, 0x61)
FSA_MAGIC = b"\\fsa"

# Match result kinds (matching Morfologik MatchResult)
NO_MATCH = 0
EXACT_MATCH = 1
AUTOMATON_HAS_PREFIX = 2
SEQUENCE_IS_A_PREFIX = 3


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
        """Iterate over all suffix byte sequences reachable from a node."""
        ...


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
        self.arcs = arcs
        self.flags = flags
        self.label_mapping = label_mapping
        self.source_name = source_name
        self.has_numbers = bool(flags & 0x0008)
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
        if self.has_numbers:
            return self._skip_vint(node)
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
        """Iterate over all suffix sequences reachable from `node` in deterministic order."""
        start = self._root_node if node is None else node
        if start == 0:
            return

        # Stack contains tuples of (arc, current_path_buffer)
        # We pre-allocate or manage DFS stack efficiently
        stack: List[Tuple[int, bytes]] = []
        first_arc = self.get_first_arc(start)
        if first_arc != 0:
            stack.append((first_arc, b""))

        while stack:
            arc, path = stack.pop()
            if arc == 0:
                continue

            # Collect all sibling arcs of the current node to maintain left-to-right order
            curr_arc = arc
            sibling_arcs: List[int] = []
            while curr_arc != 0:
                sibling_arcs.append(curr_arc)
                curr_arc = self.get_next_arc(curr_arc)

            # Push sibling arcs in reverse order so the first arc is popped and processed first
            for a in reversed(sibling_arcs):
                lbl = self.get_arc_label(a)
                new_path = path + bytes([lbl])
                if self.is_arc_final(a):
                    yield new_path
                dest = self.get_destination_node_offset(a)
                if dest != 0:
                    dest_first = self.get_first_arc(dest)
                    if dest_first != 0:
                        stack.append((dest_first, new_path))


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
