from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name: str) -> dict:
    return json.loads((ROOT / "compat" / name).read_text(encoding="utf-8"))


def test_package_content_evidence_arithmetic_and_policy() -> None:
    evidence = load("package_contents_0015.json")
    assert evidence["schema_version"] == "1.0" and evidence["task"] == "0015"
    assert evidence["wheel"]["file_count"] >= len(evidence["wheel"]["package_files"])
    assert evidence["runtime_resource_totals"]["file_count"] == sum(
        "/resources/" in name for name in evidence["wheel"]["package_files"]
    )
    assert evidence["wheel"]["forbidden_file_matches"] == []
    assert evidence["sdist"]["forbidden_file_matches"] == []
    assert "pylat_ru/py.typed" in evidence["wheel"]["package_files"]
    assert evidence["reproducibility"]["member_set_identical"] is True
    assert evidence["reproducibility"]["member_content_identical"] is True


def test_shipped_critical_resources_reconcile_to_verified_provenance() -> None:
    provenance = load("package_contents_0015.json")["critical_resource_provenance"]
    assert len(provenance) == 4
    for packaged_path, entry in provenance.items():
        assert packaged_path.startswith("pylat_ru/resources/")
        assert len(entry["sha256"]) == 64
        assert entry["license"] == "LGPL-2.1-or-later"
        assert entry["status"] == "VERIFIED_LGPL"


def test_release_readiness_consistency() -> None:
    release = load("release_readiness_0015.json")
    package = load("package_contents_0015.json")
    performance = load("performance_baseline_0015.json")
    public = load("public_api_0015.json")
    assert release["package"]["version"] == package["package_version"] == public["package_version"]
    assert release["wheel_audit"]["forbidden_files"] == len(package["wheel"]["forbidden_file_matches"])
    assert release["sdist_audit"]["forbidden_files"] == len(package["sdist"]["forbidden_file_matches"])
    assert performance["bounded_soak"]["result"] == release["performance"]["bounded_soak"] == "PASS"
    assert release["ordinary_unexplained_discrepancies"] == 0
    assert release["language_model_rule"]["status"] == "LANGUAGE_MODEL_DEFERRED"
    assert release["publication"] == "NOT PUBLISHED"
