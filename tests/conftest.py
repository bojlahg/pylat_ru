"""Shared pytest fixtures for pylat_ru test suite."""

import json
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def third_party_dir() -> Path:
    return REPO_ROOT / "third_party" / "languagetool"


@pytest.fixture
def compat_dir() -> Path:
    return REPO_ROOT / "compat"


@pytest.fixture
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"
