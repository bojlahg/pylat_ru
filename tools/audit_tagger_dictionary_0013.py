"""Exhaustive packaged-tagger-dictionary audit (Task 0013).

Reproduces ``TestTools.testDictionary`` for the whole packaged Russian tagger
dictionary: read the dictionary, iterate every ``WordData`` entry and count the
entries that lack a POS tag (upstream prints a warning for each such entry).

The sweep takes several minutes in Python, so it is a development command; its
result is recorded in ``compat/upstream_test_inventory_0013.json`` and asserted
by ``tests/unit/test_upstream_test_inventory_0013.py``.

Usage::

    python -m tools.audit_tagger_dictionary_0013
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from pylat_ru.morfologik.dictionary import MorfologikDictionary

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "src" / "pylat_ru" / "resources" / "ru"


def audit() -> dict:
    dict_path = RESOURCE_DIR / "russian.dict"
    info_path = RESOURCE_DIR / "russian.info"
    dictionary = MorfologikDictionary.open(dict_path, info_path)
    separator = dictionary.separator_byte

    started = time.time()
    entries = 0
    untagged = 0
    for sequence in dictionary.fsa.get_sequences():
        entries += 1
        first = sequence.find(separator)
        second = sequence.find(separator, first + 1)
        if first <= 0 or second == -1 or second == len(sequence) - 1:
            untagged += 1
    return {
        "dictionary_path": dict_path.relative_to(ROOT).as_posix(),
        "dictionary_sha256": hashlib.sha256(dict_path.read_bytes()).hexdigest(),
        "dictionary_size_bytes": dict_path.stat().st_size,
        "entries_total": entries,
        "entries_without_pos_tag": untagged,
        "elapsed_seconds": round(time.time() - started, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="print the raw audit record")
    args = parser.parse_args()
    record = audit()
    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"entries: {record['entries_total']}")
        print(f"entries without a POS tag: {record['entries_without_pos_tag']}")
        print(f"elapsed: {record['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
