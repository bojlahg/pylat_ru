"""Build, audit, and clean-install Task 0015 release artifacts without publishing."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_WHEEL = (
    "tools/", "tasks/", "reports/", "tests/", "corpora/", "test_corpora/",
    ".oracle_cache/", "oracle_downloads/", "third_party/", ".git/",
)
FORBIDDEN_SDIST = (
    ".oracle_cache/", "oracle_downloads/", "corpora/", "test_corpora/",
    ".venv/", ".pytest_cache/", "dist/", "build/", ".env",
)
FORBIDDEN_SUFFIXES = (".jar", ".class", ".pyc")


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def archive_members(path: Path) -> dict[str, tuple[int, str]]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return {info.filename: (info.file_size, hashlib.sha256(archive.read(info)).hexdigest()) for info in archive.infolist()}
    with tarfile.open(path, "r:gz") as archive:
        result = {}
        for member in archive.getmembers():
            if member.isfile():
                stream = archive.extractfile(member)
                assert stream is not None
                data = stream.read()
                result[member.name] = (len(data), hashlib.sha256(data).hexdigest())
        return result


def forbidden(names: list[str], patterns: tuple[str, ...]) -> list[str]:
    lowered = [(name, name.lower()) for name in names]
    return sorted(
        name for name, low in lowered
        if (any(part in low for part in patterns) or low.endswith(FORBIDDEN_SUFFIXES))
        and "/licenses/third_party/" not in low
    )


def python_in(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def smoke_install(artifact: Path, label: str) -> None:
    with tempfile.TemporaryDirectory(prefix=f"pylat-0015-{label}-") as raw:
        base = Path(raw)
        environment = base / "venv"
        outside = base / "outside"
        outside.mkdir()
        venv.EnvBuilder(with_pip=True).create(environment)
        python = python_in(environment)
        env = dict(os.environ)
        env["PIP_CACHE_DIR"] = str(base / "pip-cache")
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
        run([str(python), "-m", "pip", "install", str(artifact)], cwd=outside, env=env)
        run([str(python), "-m", "pip", "check"], cwd=outside, env=env)
        run([str(python), "-I", str(ROOT / "tools/installed_smoke_0015.py"), "--expected-prefix", str(environment)], cwd=outside, env=env)


def build_into(outdir: Path) -> tuple[Path, Path]:
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = "1700000000"
    run([sys.executable, "-m", "build", "--outdir", str(outdir)], env=env)
    wheels = list(outdir.glob("*.whl"))
    sdists = list(outdir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise AssertionError(f"expected one wheel and sdist, got {wheels!r}, {sdists!r}")
    return wheels[0], sdists[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "compat/package_contents_0015.json")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--keep-dist", type=Path)
    parser.add_argument("--skip-install", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="pylat-build-0015-") as raw:
        base = Path(raw)
        first, second = base / "build-a", base / "build-b"
        first.mkdir(); second.mkdir()
        wheel, sdist = build_into(first)
        wheel2, sdist2 = build_into(second)
        run([sys.executable, "-m", "twine", "check", str(wheel), str(sdist)])

        wheel_members = archive_members(wheel)
        sdist_members = archive_members(sdist)
        wheel_forbidden = forbidden(list(wheel_members), FORBIDDEN_WHEEL)
        sdist_forbidden = forbidden(list(sdist_members), FORBIDDEN_SDIST)
        assert not wheel_forbidden, wheel_forbidden
        assert not sdist_forbidden, sdist_forbidden
        required = (
            "pylat_ru/py.typed", "pylat_ru/resources/rules/ru/grammar.xml",
            "pylat_ru/resources/ru/russian.dict", "pylat_ru/resources/ru/russian_synth.dict",
            "pylat_ru/resources/ru/disambiguation.xml",
        )
        assert all(any(name.endswith(item) for name in wheel_members) for item in required)
        assert any("licenses/LICENSE" in name for name in wheel_members)
        assert any(name.endswith("/COPYING.txt") and "/licenses/" in name for name in wheel_members)

        wheel2_members, sdist2_members = archive_members(wheel2), archive_members(sdist2)
        wheel_same = wheel_members == wheel2_members
        sdist_normalized = {name.split("/", 1)[-1]: value for name, value in sdist_members.items()}
        sdist2_normalized = {name.split("/", 1)[-1]: value for name, value in sdist2_members.items()}
        sdist_same = sdist_normalized == sdist2_normalized
        assert wheel_same and sdist_same, "two clean builds differ in member content"

        if not args.skip_install:
            smoke_install(wheel, "wheel")
            smoke_install(sdist, "sdist")

        package_files = sorted(name for name in wheel_members if name.startswith("pylat_ru/"))
        resource_names = [name for name in package_files if "/resources/" in name]
        license_inventory = json.loads((ROOT / "third_party/languagetool/license_inventory.json").read_text(encoding="utf-8"))
        inventory_entries = license_inventory["items"]
        provenance = {}
        for packaged in required[1:]:
            upstream_suffix = packaged.removeprefix("pylat_ru/resources")
            matches = [entry for entry in inventory_entries if entry["path"].endswith(upstream_suffix)]
            if len(matches) != 1:
                raise AssertionError(f"cannot reconcile {packaged} to license inventory: {len(matches)} matches")
            archive_name = next(name for name in wheel_members if name.endswith(packaged))
            entry = matches[0]
            assert wheel_members[archive_name][1] == entry["sha256"]
            assert not entry["status"].startswith("BLOCKED")
            provenance[packaged] = {"sha256": wheel_members[archive_name][1], "inventory_path": entry["path"],
                                    "license": entry["license"], "status": entry["status"]}
        largest = sorted(
            ({"path": name, "size_bytes": size} for name, (size, _digest) in wheel_members.items()),
            key=lambda item: item["size_bytes"], reverse=True,
        )[:20]
        evidence = {
            "schema_version": "1.0", "task": "0015", "package_version": "0.1.0a0",
            "wheel": {"filename": wheel.name, "size_bytes": wheel.stat().st_size,
                      "file_count": len(wheel_members), "package_files": package_files,
                      "largest_files": largest, "forbidden_file_matches": wheel_forbidden},
            "sdist": {"filename": sdist.name, "size_bytes": sdist.stat().st_size,
                      "file_count": len(sdist_members), "forbidden_file_matches": sdist_forbidden},
            "runtime_resource_totals": {"file_count": len(resource_names),
                      "size_bytes": sum(wheel_members[name][0] for name in resource_names)},
            "critical_resource_provenance": provenance,
            "reproducibility": {"comparison_mode": "two clean SOURCE_DATE_EPOCH builds",
                      "byte_identical": {"wheel": sha256(wheel) == sha256(wheel2), "sdist": sha256(sdist) == sha256(sdist2)},
                      "member_set_identical": wheel_members.keys() == wheel2_members.keys() and sdist_normalized.keys() == sdist2_normalized.keys(),
                      "member_content_identical": wheel_same and sdist_same, "differences": []},
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        manifest = {"source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                    "package_version": "0.1.0a0", "wheel": {"filename": wheel.name, "sha256": sha256(wheel), "size_bytes": wheel.stat().st_size},
                    "sdist": {"filename": sdist.name, "sha256": sha256(sdist), "size_bytes": sdist.stat().st_size},
                    "metadata_validation": "PASS", "content_audit": "PASS"}
        if args.manifest:
            args.manifest.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        if args.keep_dist:
            args.keep_dist.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wheel, args.keep_dist / wheel.name); shutil.copy2(sdist, args.keep_dist / sdist.name)
        print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
