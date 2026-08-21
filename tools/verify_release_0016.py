"""Fail-closed release identity checks for Task 0016."""

from __future__ import annotations

import argparse
from email.parser import BytesParser
import json
from pathlib import Path
import re
import tarfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "0.1.0a0"
EXPECTED_TAG = f"v{EXPECTED_VERSION}"


def source_versions() -> tuple[str, str]:
    project_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_block = re.search(r"(?ms)^\[project\]\s*$.*?(?=^\[|\Z)", project_text)
    if not project_block:
        raise AssertionError("pyproject.toml [project] table not found")
    project_match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', project_block.group(), re.MULTILINE)
    if not project_match:
        raise AssertionError("pyproject.toml project.version not found")
    project_version = project_match.group(1)
    init_text = (ROOT / "src/pylat_ru/__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', init_text, re.MULTILINE)
    if not match:
        raise AssertionError("pylat_ru.__version__ assignment not found")
    return project_version, match.group(1)


def metadata_version(artifact: Path) -> str:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
            if len(names) != 1:
                raise AssertionError(f"expected one wheel METADATA file, got {names}")
            raw = archive.read(names[0])
    else:
        with tarfile.open(artifact, "r:gz") as archive:
            members = [member for member in archive.getmembers() if member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")]
            if len(members) != 1:
                raise AssertionError(f"expected one root sdist PKG-INFO, got {members}")
            stream = archive.extractfile(members[0])
            assert stream is not None
            raw = stream.read()
    return str(BytesParser().parsebytes(raw)["Version"])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", required=True)
    parser.add_argument("--dist", type=Path)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()

    project_version, import_version = source_versions()
    values = {"expected": EXPECTED_VERSION, "tag": args.tag.removeprefix("v"),
              "pyproject": project_version, "import": import_version}
    if set(values.values()) != {EXPECTED_VERSION} or args.tag != EXPECTED_TAG:
        raise AssertionError(f"release identity mismatch: {values}; tag={args.tag!r}")

    if args.dist:
        wheels = list(args.dist.glob("*.whl"))
        sdists = list(args.dist.glob("*.tar.gz"))
        if len(wheels) != 1 or len(sdists) != 1:
            raise AssertionError(f"expected exactly one wheel and sdist: {wheels}, {sdists}")
        artifact_versions = {"wheel": metadata_version(wheels[0]), "sdist": metadata_version(sdists[0])}
        if set(artifact_versions.values()) != {EXPECTED_VERSION}:
            raise AssertionError(f"artifact version mismatch: {artifact_versions}")
        if not wheels[0].name.endswith("-py3-none-any.whl"):
            raise AssertionError(f"wheel is not pure Python py3-none-any: {wheels[0].name}")
        if args.manifest:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            if manifest["tag"] != args.tag or manifest["package_version"] != EXPECTED_VERSION:
                raise AssertionError("artifact manifest release identity mismatch")
    print("RELEASE_IDENTITY_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
