"""Confirm that the immutable Task-0016 release version is not already consumed."""

from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen


VERSION = "0.1.0a0"
INDEXES = {
    "TestPyPI": "https://test.pypi.org/pypi/pylat-ru/json",
    "PyPI": "https://pypi.org/pypi/pylat-ru/json",
}


def main() -> int:
    for label, url in INDEXES.items():
        try:
            with urlopen(Request(url, headers={"User-Agent": "pylat-ru-release-0016"}), timeout=30) as response:
                payload = json.load(response)
        except HTTPError as error:
            if error.code == 404:
                print(f"{label}: normalized project namespace is currently unoccupied")
                continue
            raise
        releases = payload.get("releases", {})
        if VERSION in releases:
            raise SystemExit(f"{label}: pylat-ru {VERSION} already exists; refusing overwrite")
        raise SystemExit(
            f"{label}: normalized project namespace is already occupied without {VERSION}; "
            "stop for explicit ownership/name review"
        )
    print("INDEX_NAMESPACE_AND_VERSION_AVAILABLE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
