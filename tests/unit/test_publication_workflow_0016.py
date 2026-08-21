from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/release.yml"


def load_workflow() -> dict[str, object]:
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_release_identity_and_evidence_contract() -> None:
    workflow = load_workflow()
    assert workflow["on"]["push"]["tags"] == ["v*"]
    recovery = workflow["on"]["workflow_dispatch"]["inputs"]
    assert set(recovery) == {"release_tag", "release_sha"}
    assert all(value["required"] == "true" for value in recovery.values())
    evidence = json.loads((ROOT / "compat/publication_0016.json").read_text(encoding="utf-8"))
    assert evidence["release_version"] == "0.1.0a0"
    assert evidence["release_tag"] == "v0.1.0a0"
    assert evidence["trusted_publishing"] == {
        "owner": "bojlahg", "repository": "pylat_ru", "workflow": "release.yml",
        "testpypi_environment": "testpypi", "pypi_environment": "pypi",
        "permanent_token_required": False,
    }


def test_every_source_checkout_uses_the_immutable_release_tag() -> None:
    workflow = load_workflow()
    checkout_refs = [
        step["with"]["ref"]
        for job in workflow["jobs"].values()
        for step in job["steps"]
        if step.get("uses") == "actions/checkout@v4"
    ]
    assert checkout_refs
    assert set(checkout_refs) == {"${{ env.RELEASE_TAG }}"}
    verification = "\n".join(
        str(step.get("run", "")) for step in workflow["jobs"]["verify-source"]["steps"]
    )
    assert 'git rev-list -n 1 "$RELEASE_TAG"' in verification
    assert 'git rev-parse HEAD' in verification


def test_publish_jobs_are_ordered_and_oidc_is_scoped() -> None:
    workflow = load_workflow()
    jobs = workflow["jobs"]
    assert workflow["permissions"] == {"contents": "read"}
    assert jobs["build-and-validate"]["needs"] == "verify-source"
    assert jobs["publish-testpypi"]["needs"] == "build-and-validate"
    assert jobs["verify-testpypi"]["needs"] == "publish-testpypi"
    assert jobs["publish-pypi"]["needs"] == "verify-testpypi"
    assert jobs["verify-pypi"]["needs"] == "publish-pypi"
    assert jobs["github-prerelease"]["needs"] == "verify-pypi"
    oidc_jobs = {name for name, job in jobs.items() if job.get("permissions", {}).get("id-token") == "write"}
    assert oidc_jobs == {"publish-testpypi", "publish-pypi"}


def test_indexes_and_environments_cannot_cross_publish() -> None:
    jobs = load_workflow()["jobs"]
    test_job = jobs["publish-testpypi"]
    prod_job = jobs["publish-pypi"]
    assert test_job["environment"]["name"] == "testpypi"
    assert prod_job["environment"]["name"] == "pypi"
    test_with = test_job["steps"][-1]["with"]
    prod_with = prod_job["steps"][-1]["with"]
    assert test_with["repository-url"] == "https://test.pypi.org/legacy/"
    assert "repository-url" not in prod_with
    assert test_with["packages-dir"] == prod_with["packages-dir"] == "release/dist/"


def test_validation_precedes_every_publication() -> None:
    jobs = load_workflow()["jobs"]
    build_steps = "\n".join(str(step) for step in jobs["build-and-validate"]["steps"])
    assert "release_preflight_0015" in build_steps
    assert "verify_release_0016" in build_steps
    assert "twine" not in str(jobs["publish-testpypi"])
    assert jobs["github-prerelease"]["permissions"] == {"contents": "write"}
    release_command = jobs["github-prerelease"]["steps"][-1]["run"]
    assert "--prerelease" in release_command
    assert "*.whl" in release_command and "*.tar.gz" in release_command
