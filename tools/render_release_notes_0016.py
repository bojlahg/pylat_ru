"""Render immutable release notes with hashes from the CI artifact manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    text = f"""# pylat-ru 0.1.0a0

First public alpha of the native Python Russian LanguageTool-compatible checker.

- No Java/JRE is required at runtime.
- Python 3.10 or newer is required.
- LanguageTool 6.8 is pinned at `e807fcde6a6506191e1470744d2345da28c26be6`.
- Ordinary/non-language-model Russian compatibility passes the committed conformance evidence with zero unexplained discrepancies.
- `RussianConfusionProbabilityRule` remains `LANGUAGE_MODEL_DEFERRED`; this release does not claim language-model parity.

Install with `python -m pip install pylat-ru==0.1.0a0`.

PyPI: https://pypi.org/project/pylat-ru/0.1.0a0/

Artifact SHA-256:

- `{manifest['wheel']['filename']}`: `{manifest['wheel']['sha256']}`
- `{manifest['sdist']['filename']}`: `{manifest['sdist']['sha256']}`
"""
    args.output.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
