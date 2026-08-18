"""Unit tests for license and upstream metadata integrity."""

import hashlib
import json
from pathlib import Path
import pytest


def test_upstream_json_structure_and_hashes(third_party_dir: Path):
    """Verify UPSTREAM.json contains valid metadata and matches file hashes on disk."""
    upstream_json = third_party_dir / "UPSTREAM.json"
    assert upstream_json.is_file()

    data = json.loads(upstream_json.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
    assert data["pinned_tag"] == "v6.8"
    assert data["pinned_commit"] == "e807fcde6a6506191e1470744d2345da28c26be6"
    assert data["selection_rationale"] is not None
    assert len(data["files"]) > 80

    # Verify hashes on disk
    for rel_path, file_meta in data["files"].items():
        full_path = third_party_dir / rel_path
        assert full_path.is_file(), f"Vendored file missing: {rel_path}"

        with open(full_path, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        assert actual_sha == file_meta["sha256"], f"SHA-256 mismatch for {rel_path}"


def test_license_inventory_no_blocked_items(third_party_dir: Path):
    """Verify license_inventory.json contains 0 BLOCKED_LICENSE_REVIEW items and valid entries."""
    license_inv_path = third_party_dir / "license_inventory.json"
    assert license_inv_path.is_file()

    data = json.loads(license_inv_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == "1.0.0"
    assert data["status_summary"]["BLOCKED_LICENSE_REVIEW"] == 0
    assert data["status_summary"]["VERIFIED_LGPL"] > 80

    for item in data["items"]:
        assert item["status"] == "VERIFIED_LGPL"
        assert item["license"] == "LGPL-2.1-or-later"
        assert len(item["sha256"]) == 64
        assert item["vendored"] is True
