"""Unit tests for license and upstream metadata integrity."""

import hashlib
import json
from pathlib import Path
import pytest


# license_inventory.json is generated local provenance metadata, not an
# immutable upstream source asset.  It is intentionally validated by the
# dedicated structure/license test below instead of by a self-referential
# byte hash stored inside UPSTREAM.json.
LOCAL_GENERATED_METADATA = {"license_inventory.json"}


def test_upstream_json_structure_and_hashes(third_party_dir: Path):
    """Verify UPSTREAM.json contains valid metadata and pinned source hashes."""
    upstream_json = third_party_dir / "UPSTREAM.json"
    assert upstream_json.is_file()

    data = json.loads(upstream_json.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
    assert data["pinned_tag"] == "v6.8"
    assert data["pinned_commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"
    assert data["selection_rationale"] is not None
    assert data["vendored_files_count"] == 155
    assert len(data["files"]) == 155
    assert LOCAL_GENERATED_METADATA <= set(data["files"])

    # Verify byte-exact hashes for immutable upstream assets.  Generated
    # provenance metadata cannot validate its own hash without creating a
    # circular dependency, so it is checked structurally below instead.
    verified_source_files = 0
    for rel_path, file_meta in data["files"].items():
        assert "\\" not in rel_path, f"Non-POSIX path separator in UPSTREAM.json: {rel_path}"
        full_path = third_party_dir / rel_path
        assert full_path.is_file(), f"Vendored file missing: {rel_path}"

        if rel_path in LOCAL_GENERATED_METADATA:
            continue

        with open(full_path, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        assert actual_sha == file_meta["sha256"], f"SHA-256 mismatch for {rel_path}"
        verified_source_files += 1

    assert verified_source_files == len(data["files"]) - len(LOCAL_GENERATED_METADATA)


def test_license_inventory_platform_independence_and_no_blocked(third_party_dir: Path):
    """Verify license_inventory.json uses POSIX paths and contains 0 BLOCKED_LICENSE_REVIEW items."""
    license_inv_path = third_party_dir / "license_inventory.json"
    assert license_inv_path.is_file()

    data = json.loads(license_inv_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
    assert data["status_summary"]["BLOCKED_LICENSE_REVIEW"] == 0
    assert data["total_vendored_files"] == 155
    assert data["status_summary"]["VERIFIED_LGPL"] == 155

    for item in data["items"]:
        assert "\\" not in item["path"], f"Non-POSIX path in license_inventory.json: {item['path']}"
        assert item["status"] == "VERIFIED_LGPL"
        assert item["license"] == "LGPL-2.1-or-later"
        assert len(item["sha256"]) == 64
        assert item["vendored"] is True
