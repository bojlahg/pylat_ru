"""Installed-artifact smoke for Task 0015; run from outside the repository."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import socket
import subprocess


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-prefix", required=True)
    args = parser.parse_args()

    import pylat_ru
    from pylat_ru import LanguageToolRU, LEVEL_DEFAULT, LEVEL_PICKY, RuleMatch, __version__

    package_path = Path(pylat_ru.__file__).resolve()
    expected = Path(args.expected_prefix).resolve()
    if not package_path.is_relative_to(expected):
        raise AssertionError(f"source-tree import: {package_path} is outside {expected}")
    assert __version__ == "0.1.0a0"
    print(f"installed_package={package_path}")

    original_socket = socket.socket
    original_popen = subprocess.Popen

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("checker attempted forbidden socket/subprocess access")

    socket.socket = forbidden  # type: ignore[assignment]
    subprocess.Popen = forbidden  # type: ignore[assignment]
    try:
        tool = LanguageToolRU()
        xml = tool.check("Ученик решил задать тест учителю.")
        assert any(m.rule_id == "zadat_test" for m in xml)
        assert all(isinstance(m, RuleMatch) for m in xml)

        native = tool.check("Это  тест.")
        assert any(m.rule_id == "WHITESPACE_RULE" for m in native)

        spelling = tool.check("Все семьи счастливы, но каждя семья уникальна.")
        assert any(m.rule_id == "MORFOLOGIK_RULE_RU_RU" for m in spelling)

        configured = LanguageToolRU(rule_config={"TOO_LONG_SENTENCE": {"maxWords": 4}})
        picky_text = "Один два три четыре пять."
        assert "TOO_LONG_SENTENCE" not in {m.rule_id for m in configured.check(picky_text, LEVEL_DEFAULT)}
        assert "TOO_LONG_SENTENCE" in {m.rule_id for m in configured.check(picky_text, LEVEL_PICKY)}

        non_bmp = "😀 Ученик решил задать тест учителю."
        match = next(m for m in tool.check(non_bmp) if m.rule_id == "zadat_test")
        assert non_bmp[match.offset:match.offset + match.length] == "задать тест"
        assert match.utf16_offset == match.offset + 1
    finally:
        socket.socket = original_socket
        subprocess.Popen = original_popen

    # The promise is deliberately narrow: distinct instances can check in parallel.
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: LanguageToolRU().check("Это  тест."), range(2)))
    assert all(any(m.rule_id == "WHITESPACE_RULE" for m in result) for result in results)
    print("INSTALLED_ARTIFACT_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
