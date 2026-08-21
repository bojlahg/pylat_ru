"""Verify index artifact identity and run a clean installed-package smoke."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0a0"
INDEXES = {
    "testpypi": ("https://test.pypi.org/pypi/pylat-ru/json", "https://test.pypi.org/simple/"),
    "pypi": ("https://pypi.org/pypi/pylat-ru/json", "https://pypi.org/simple/"),
}


def run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch_release(url: str, attempts: int) -> dict[str, object]:
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(Request(url, headers={"User-Agent": "pylat-ru-release-0016"}), timeout=30) as response:
                payload = json.load(response)
            if VERSION in payload.get("releases", {}) and len(payload["releases"][VERSION]) == 2:
                return payload
        except HTTPError as error:
            if error.code != 404:
                raise
        if attempt < attempts:
            time.sleep(10)
    raise AssertionError(f"published release {VERSION} did not become complete at {url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", choices=INDEXES, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=18)
    args = parser.parse_args()
    api_url, simple_url = INDEXES[args.index]
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    payload = fetch_release(api_url, args.attempts)
    info = payload["info"]
    if info["version"] != VERSION or "native Python" not in info.get("description", ""):
        raise AssertionError("project version or rendered README description is incorrect")
    files = payload["releases"][VERSION]
    public_hashes = {item["filename"]: item["digests"]["sha256"] for item in files}
    expected_hashes = {manifest[k]["filename"]: manifest[k]["sha256"] for k in ("wheel", "sdist")}
    if public_hashes != expected_hashes:
        raise AssertionError(f"public artifact identity mismatch: {public_hashes} != {expected_hashes}")

    with tempfile.TemporaryDirectory(prefix=f"pylat-0016-{args.index}-") as raw:
        base = Path(raw)
        environment, downloads, outside = base / "venv", base / "downloads", base / "outside"
        downloads.mkdir(); outside.mkdir()
        run([sys.executable, "-m", "venv", str(environment)], cwd=outside, env=dict(os.environ))
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        env = dict(os.environ, PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONPATH="")
        run([str(python), "-m", "pip", "install", "regex>=2024.5.15,<=2026.7.19"], cwd=outside, env=env)
        run([str(python), "-m", "pip", "download", "--no-deps", "--only-binary", ":all:",
             "--index-url", simple_url, "--dest", str(downloads), f"pylat-ru=={VERSION}"], cwd=outside, env=env)
        wheels = list(downloads.glob("*.whl"))
        if len(wheels) != 1 or wheels[0].name != manifest["wheel"]["filename"] or sha256(wheels[0]) != manifest["wheel"]["sha256"]:
            raise AssertionError(f"downloaded wheel identity mismatch: {wheels}")
        run([str(python), "-m", "pip", "install", "--no-deps", str(wheels[0])], cwd=outside, env=env)
        run([str(python), "-m", "pip", "check"], cwd=outside, env=env)
        run([str(python), "-I", str(ROOT / "tools/installed_smoke_0015.py"),
             "--expected-prefix", str(environment)], cwd=outside, env=env)
    print(f"{args.index.upper()}_PUBLICATION_SMOKE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
